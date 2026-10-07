"""Hybrid intent routing: deterministic rules first, then embedding similarity to examples.

Exact-match rules keep their certain decisions (curated questions, explicit assessment or
result-explanation phrases, greetings). Every other message is embedded with a local,
checksum-pinned sentence encoder and compared with reviewed reference utterances; no model
is fine-tuned. A softmax temperature and a similarity floor are fitted on a held-out
calibration split, so confidence below the routing graph's threshold, or a message unlike
any reference, leads to clarification rather than a guess.
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np

from clinical_risk_agent.rag.medcpt import _verified_artifact

from .prototype_ports import PrototypeIntentPort
from .routing import Intent, IntentDecision

UTTERANCES_PATH = Path("agent_docs/INTENT_ROUTER_UTTERANCES.json")
CALIBRATION_PATH = Path("agent_docs/INTENT_ROUTER_CALIBRATION.json")
# Rule outcomes precise enough to bypass the semantic router.
CERTAIN_RULES = frozenset({"curated_question", "assessment_request", "result_explanation",
                           "greeting"})


def sha256_text(text: str) -> str:
    """Return the SHA-256 digest of UTF-8 text for artifact provenance."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class SentenceEncoder:
    """Local Hugging Face encoder returning L2-normalized sentence embeddings."""

    def __init__(self, tokenizer: object, model: object, pooling: str) -> None:
        """Bind tokenizer, model and the pooling the encoder was trained with."""
        if pooling not in {"mean", "cls"}:
            raise ValueError("pooling must be 'mean' or 'cls'")
        self.tokenizer = tokenizer
        self.model = model
        self.pooling = pooling

    @classmethod
    def from_local(cls, model_dir: Path, *, sha256: str, pooling: str) -> SentenceEncoder:
        """Load a checksum-verified local encoder without network access."""
        from transformers import AutoModel, AutoTokenizer

        _verified_artifact(model_dir, sha256)
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        model = AutoModel.from_pretrained(
            model_dir, local_files_only=True, use_safetensors=True
        ).eval()
        return cls(tokenizer, model, pooling)

    def embed(self, texts: Sequence[str]) -> np.ndarray:
        """Encode texts into unit-length vectors using the configured pooling."""
        import torch

        encoded = self.tokenizer(list(texts), truncation=True, padding=True,
                                 return_tensors="pt", max_length=128)
        with torch.inference_mode():
            hidden = self.model(**encoded).last_hidden_state
            if self.pooling == "cls":
                vectors = hidden[:, 0]
            else:
                mask = encoded["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                vectors = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            vectors = torch.nn.functional.normalize(vectors, dim=-1)
        return vectors.cpu().numpy()


class SemanticIntentRouter:
    """Nearest-example intent scoring with temperature-scaled confidence."""

    def __init__(self, encoder: object, utterances: Mapping[str, Sequence[str]], *,
                 temperature: float, min_similarity: float, top_k: int = 3,
                 model_id: str = "local-sentence-encoder", model_sha256: str = "unpinned",
                 calibration_version: str = "uncalibrated",
                 router_version: str = "semantic-intent-router-v1") -> None:
        """Embed reference utterances once and store calibrated decision settings."""
        if temperature <= 0 or top_k < 1:
            raise ValueError("temperature and top_k must be positive")
        self._encoder = encoder
        self._intents = tuple(Intent(name) for name in utterances)
        self._labels = np.array([index for index, name in enumerate(utterances)
                                 for _ in utterances[name]])
        texts = [text for name in utterances for text in utterances[name]]
        if not texts or any(not utterances[name] for name in utterances):
            raise ValueError("Every intent needs at least one reference utterance")
        self._references = encoder.embed(texts)
        self.temperature = temperature
        self.min_similarity = min_similarity
        self.top_k = top_k
        self._provenance = (model_id, model_sha256, calibration_version, router_version)

    def similarities(self, texts: Sequence[str]) -> np.ndarray:
        """Return per-intent scores: mean cosine similarity of the top-k references."""
        cosine = self._encoder.embed(texts) @ self._references.T
        scores = np.empty((len(texts), len(self._intents)))
        for index in range(len(self._intents)):
            group = np.sort(cosine[:, self._labels == index], axis=1)[:, ::-1]
            scores[:, index] = group[:, :self.top_k].mean(axis=1)
        return scores

    @property
    def intents(self) -> tuple[Intent, ...]:
        """Return the intents in score-column order."""
        return self._intents

    def decide(self, scores: np.ndarray) -> tuple[Intent, float, bool]:
        """Convert one row of intent scores into intent, confidence and clarification."""
        logits = scores / self.temperature
        probabilities = np.exp(logits - logits.max())
        probabilities /= probabilities.sum()
        best = int(np.argmax(probabilities))
        return (self._intents[best], float(probabilities[best]),
                bool(scores[best] < self.min_similarity))

    def classify(self, text: str) -> IntentDecision:
        """Classify one message by similarity to the reference utterances."""
        intent, confidence, unfamiliar = self.decide(self.similarities([text])[0])
        model_id, sha, calibration, router = self._provenance
        return IntentDecision(intent, confidence, unfamiliar, model_id, sha, calibration,
                              router, "semantic_unfamiliar" if unfamiliar else "semantic")


class HybridIntentPort:
    """Certain deterministic rules first; otherwise the lazily loaded semantic router."""

    def __init__(self, router_factory, rules: PrototypeIntentPort | None = None) -> None:
        """Defer loading the encoder until the first message that needs it."""
        self._rules = rules or PrototypeIntentPort()
        self._factory = router_factory
        self._router: SemanticIntentRouter | None = None
        self._lock = threading.Lock()

    @classmethod
    def from_root(cls, root: Path) -> HybridIntentPort:
        """Build the port from the pinned utterance and calibration artifacts under root."""
        return cls(lambda: load_semantic_router(root))

    def warmup(self) -> None:
        """Load the encoder and embed reference utterances before the first request."""
        self._semantic()

    def _semantic(self) -> SemanticIntentRouter:
        """Return the semantic router, loading it once under a lock."""
        with self._lock:
            if self._router is None:
                self._router = self._factory()
            return self._router

    def classify(self, text: str) -> IntentDecision:
        """Return a certain rule decision, or the semantic router's calibrated decision."""
        decision = self._rules.classify(text)
        if decision.rationale_code in CERTAIN_RULES:
            return decision
        return self._semantic().classify(text)


def load_semantic_router(root: Path) -> SemanticIntentRouter:
    """Load utterances, verify they match the calibration record, and build the router."""
    utterance_text = (root / UTTERANCES_PATH).read_text(encoding="utf-8")
    calibration = json.loads((root / CALIBRATION_PATH).read_text(encoding="utf-8"))
    if calibration["utterances_sha256"] != sha256_text(utterance_text):
        raise ValueError("Intent utterances changed since calibration; recalibrate")
    model = calibration["model"]
    encoder = SentenceEncoder.from_local(root / model["local_dir"],
                                         sha256=model["model_safetensors_sha256"],
                                         pooling=model["pooling"])
    settings = calibration["settings"]
    if not math.isfinite(settings["temperature"]):
        raise ValueError("Invalid calibration temperature")
    utterances = json.loads(utterance_text)
    return SemanticIntentRouter(
        encoder, utterances["intents"], temperature=settings["temperature"],
        min_similarity=settings["min_similarity"], top_k=settings["top_k"],
        model_id=f"{model['repo']}@{model['revision']}",
        model_sha256=model["model_safetensors_sha256"],
        calibration_version=calibration["calibration_version"],
        router_version=utterances["router_version"],
    )
