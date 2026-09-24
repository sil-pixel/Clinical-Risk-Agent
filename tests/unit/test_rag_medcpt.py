"""Adapter shape tests without downloading or approving any model artifact."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from clinical_risk_agent.rag.chunking import Passage  # noqa: E402
from clinical_risk_agent.rag.medcpt import MedCPTEncoder, MedCPTReranker  # noqa: E402


class FakeTokenizer:
    def __init__(self) -> None:
        self.last_input = None
        self.last_max_length = None

    def __call__(self, texts: object, **kwargs: object) -> dict[str, torch.Tensor]:
        self.last_input = texts
        self.last_max_length = kwargs["max_length"]
        return {"input_ids": torch.ones((len(texts), 2), dtype=torch.long)}

    def encode(self, text: str, *, add_special_tokens: bool) -> list[int]:
        return list(range(len(text.split())))


class FakeOutput:
    def __init__(self, count: int) -> None:
        self.last_hidden_state = torch.ones((count, 2, 3))
        self.logits = torch.ones((count, 1))


class FakeModel:
    def __init__(self) -> None:
        self.weight = torch.nn.Parameter(torch.ones(1))

    def parameters(self):
        return iter((self.weight,))

    def __call__(self, **kwargs: torch.Tensor) -> FakeOutput:
        return FakeOutput(kwargs["input_ids"].shape[0])


class MedCPTAdapterTests(unittest.TestCase):
    def test_query_article_and_cross_encoder_inputs(self) -> None:
        query_tokenizer = FakeTokenizer()
        article_tokenizer = FakeTokenizer()
        encoder = MedCPTEncoder(
            query_tokenizer, FakeModel(), article_tokenizer, FakeModel()
        )
        passage = Passage(
            "source-1", "parent-1", "chunk-1", "hierarchical", "abstract",
            "abstract:1", "Exact fixture text.", "Exact fixture text.", "Fixture title",
        )
        self.assertEqual(encoder.embed_query("fixture query"), (1.0, 1.0, 1.0))
        self.assertEqual(query_tokenizer.last_max_length, 64)
        self.assertEqual(encoder.embed_passages((passage,)), ((1.0, 1.0, 1.0),))
        self.assertEqual(article_tokenizer.last_input,
                         [["Fixture title", "Exact fixture text."]])
        self.assertEqual(article_tokenizer.last_max_length, 512)
        self.assertEqual(encoder.count_article_tokens("one two three"), 3)
        cross_tokenizer = FakeTokenizer()
        self.assertEqual(MedCPTReranker(cross_tokenizer, FakeModel()).score(
            "fixture query", passage), 1.0)
        self.assertEqual(cross_tokenizer.last_input,
                         [["fixture query", "Fixture title Exact fixture text."]])
        self.assertEqual(cross_tokenizer.last_max_length, 512)


if __name__ == "__main__":
    unittest.main()
