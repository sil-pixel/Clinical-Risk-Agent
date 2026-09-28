"""Local-only MedCPT adapters. Model artifacts must be provisioned and pinned offline."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path

from .chunking import Passage


def _verified_artifact(path: Path, expected_sha256: str) -> None:
    """Verify the local safetensors artifact against its pinned SHA-256 digest."""
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdef" for c in expected_sha256):
        raise ValueError("Expected a lowercase SHA-256 digest")
    artifact = path / "model.safetensors"
    if not artifact.is_file():
        raise ValueError("Local safetensors artifact is missing")
    digest = hashlib.sha256()
    with artifact.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("Local model checksum mismatch")


class MedCPTEncoder:
    """Separate query and article encoders using NLM's CLS representation."""

    def __init__(
        self, query_tokenizer: object, query_model: object,
        article_tokenizer: object, article_model: object,
    ) -> None:
        """Bind separate query and article tokenizers and embedding models."""
        self.query_tokenizer = query_tokenizer
        self.query_model = query_model
        self.article_tokenizer = article_tokenizer
        self.article_model = article_model

    @classmethod
    def from_local(
        cls, query_dir: Path, article_dir: Path, *,
        query_sha256: str, article_sha256: str,
    ) -> MedCPTEncoder:
        """Load tokenizer and model resources from checksum-verified local artifacts."""
        from transformers import AutoModel, AutoTokenizer

        _verified_artifact(query_dir, query_sha256)
        _verified_artifact(article_dir, article_sha256)
        query_tokenizer = AutoTokenizer.from_pretrained(query_dir, local_files_only=True)
        article_tokenizer = AutoTokenizer.from_pretrained(article_dir, local_files_only=True)
        query_model = AutoModel.from_pretrained(
            query_dir, local_files_only=True, use_safetensors=True
        ).eval()
        article_model = AutoModel.from_pretrained(
            article_dir, local_files_only=True, use_safetensors=True
        ).eval()
        return cls(query_tokenizer, query_model, article_tokenizer, article_model)

    @staticmethod
    def _encode(tokenizer: object, model: object, texts: Sequence[object],
                *, max_length: int) -> tuple[tuple[float, ...], ...]:
        """Encode a batch of texts using the model CLS representation."""
        import torch

        if not texts:
            return ()
        encoded = tokenizer(
            list(texts), truncation=True, padding=True,
            return_tensors="pt", max_length=max_length,
        )
        device = next(model.parameters()).device
        encoded = {key: value.to(device) for key, value in encoded.items()}
        with torch.inference_mode():
            vectors = model(**encoded).last_hidden_state[:, 0, :].cpu().tolist()
        return tuple(tuple(float(value) for value in row) for row in vectors)

    def embed_query(self, query: str) -> tuple[float, ...]:
        """Encode a query as a dense semantic-search vector."""
        return self._encode(self.query_tokenizer, self.query_model, (query,), max_length=64)[0]

    def embed_passages(self, passages: Sequence[Passage]) -> tuple[tuple[float, ...], ...]:
        """Encode passage title-text pairs as dense article vectors."""
        pairs = [list(passage.embedding_pair) for passage in passages]
        return self._encode(
            self.article_tokenizer, self.article_model, pairs, max_length=512
        )

    def count_article_tokens(self, text: str) -> int:
        """Count article tokens without adding tokenizer special tokens."""
        return len(self.article_tokenizer.encode(text, add_special_tokens=False))


class MedCPTReranker:
    """Local MedCPT cross-encoder logits; higher means more relevant."""

    def __init__(self, tokenizer: object, model: object) -> None:
        """Bind the tokenizer and cross-encoder used for passage relevance scoring."""
        self.tokenizer = tokenizer
        self.model = model

    @classmethod
    def from_local(cls, model_dir: Path, *, sha256: str) -> MedCPTReranker:
        """Load tokenizer and model resources from checksum-verified local artifacts."""
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        _verified_artifact(model_dir, sha256)
        tokenizer = AutoTokenizer.from_pretrained(model_dir, local_files_only=True)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_dir, local_files_only=True, use_safetensors=True
        ).eval()
        return cls(tokenizer, model)

    def score(self, query: str, passage: Passage) -> float:
        """Return the relevance score for one query-passage pair."""
        return self.score_many(query, (passage,))[0]

    def score_many(
        self, query: str, passages: Sequence[Passage], *, batch_size: int = 8
    ) -> tuple[float, ...]:
        """Return relevance scores for a batch of query-passage pairs."""
        import torch

        if batch_size < 1:
            raise ValueError("batch_size must be positive")
        device = next(self.model.parameters()).device
        scores: list[float] = []
        for start in range(0, len(passages), batch_size):
            pairs = [[query, f"{item.title} {item.exact_text}"]
                     for item in passages[start:start + batch_size]]
            encoded = self.tokenizer(
                pairs, truncation=True, padding=True,
                return_tensors="pt", max_length=512,
            )
            encoded = {key: value.to(device) for key, value in encoded.items()}
            with torch.inference_mode():
                scores.extend(float(value) for value in self.model(**encoded).logits.reshape(-1).cpu())
        return tuple(scores)
