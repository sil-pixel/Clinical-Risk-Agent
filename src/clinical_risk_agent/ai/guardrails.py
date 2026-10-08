"""Prompt-injection guard: Meta's Llama Prompt Guard 2 in front of intent routing.

The classifier runs locally from checksum-pinned weights. Messages it scores as injection
or jailbreak attempts are routed to ``unsupported_or_unsafe`` before the intent router or
any external model sees them. Crisis and refusal rules in the safety port run earlier and
are unaffected.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

from clinical_risk_agent.rag.medcpt import _verified_artifact

from .routing import Intent, IntentDecision

PROMPT_GUARD_PIN_PATH = Path("agent_docs/PROMPT_GUARD_PIN.json")


class PromptGuardClassifier:
    """Local Prompt Guard 2 returning the probability that text is an attack."""

    def __init__(self, tokenizer: object, model: object) -> None:
        """Bind the tokenizer and sequence-classification model."""
        self.tokenizer = tokenizer
        self.model = model

    @classmethod
    def from_local(cls, model_dir: Path, *, sha256: str) -> PromptGuardClassifier:
        """Load checksum-verified local weights without network access."""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _verified_artifact(model_dir, sha256)
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_dir, local_files_only=True, use_safetensors=True
        ).eval()
        return cls(tokenizer, model)

    def score(self, text: str) -> float:
        """Return P(malicious) for one message; label 1 is the attack class."""
        import torch

        encoded = self.tokenizer(text, truncation=True, max_length=512, return_tensors="pt")
        with torch.inference_mode():
            logits = self.model(**encoded).logits[0]
        return float(torch.softmax(logits, dim=-1)[1])


class PromptGuardIntentPort:
    """Route injection attempts to unsupported; pass everything else to the wrapped port."""

    def __init__(self, base, classifier_factory, *, threshold: float,
                 model_id: str, model_sha256: str) -> None:
        """Wrap an intent port and defer loading the classifier until first use."""
        if not 0.0 < threshold < 1.0:
            raise ValueError("threshold must be between 0 and 1")
        self._base = base
        self._factory = classifier_factory
        self._classifier = None
        self._lock = threading.Lock()
        self.threshold = threshold
        self._provenance = (model_id, model_sha256)

    @classmethod
    def from_root(cls, base, root: Path) -> PromptGuardIntentPort:
        """Build the guard from the pinned model record under root."""
        pin = json.loads((root / PROMPT_GUARD_PIN_PATH).read_text(encoding="utf-8"))
        sha = pin["model_safetensors_sha256"]
        return cls(base, lambda: PromptGuardClassifier.from_local(root / pin["local_dir"],
                                                                  sha256=sha),
                   threshold=pin["threshold"], model_id=f"{pin['repo']}@{pin['revision']}",
                   model_sha256=sha)

    def _guard(self) -> PromptGuardClassifier:
        """Return the classifier, loading it once under a lock."""
        with self._lock:
            if self._classifier is None:
                self._classifier = self._factory()
            return self._classifier

    def warmup(self) -> None:
        """Load the guard and the wrapped port before the first request."""
        self._guard()
        warmup = getattr(self._base, "warmup", None)
        if warmup is not None:
            warmup()

    def classify(self, text: str) -> IntentDecision:
        """Return a certain unsupported decision for attacks, else the wrapped decision."""
        score = self._guard().score(text)
        if score >= self.threshold:
            model_id, sha = self._provenance
            return IntentDecision(Intent.UNSUPPORTED_OR_UNSAFE, 1.0, False, model_id, sha,
                                  f"prompt-guard-threshold-{self.threshold}",
                                  "prompt-guard-v1", "prompt_injection")
        return self._base.classify(text)
