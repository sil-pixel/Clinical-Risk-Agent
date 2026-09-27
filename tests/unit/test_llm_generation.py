"""Provider adapters are tested without network requests or real credentials."""

from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from clinical_risk_agent.ai.generation import (
    AnthropicGenerator,
    GenerationRequest,
    GeminiGenerator,
    LLMProvider,
    OpenAIGenerator,
    create_generator,
)


PAYLOAD = {
    "response_kind": "grounded_answer",
    "text": "Synthetic supported statement [S1].",
    "citation_ids": ["S1"],
}


class FakeModels:
    def __init__(self, payload: dict | None = None, *, parsed=None) -> None:
        self.payload = payload or PAYLOAD
        self.parsed = parsed
        self.call = None

    def generate_content(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(text=json.dumps(self.payload), parsed=self.parsed)


class FakeResponses:
    def __init__(self, parsed=PAYLOAD) -> None:
        self.parsed = parsed
        self.call = None

    def parse(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(output_parsed=self.parsed)


class FakeMessages:
    def __init__(self, parsed=PAYLOAD) -> None:
        self.parsed = parsed
        self.call = None

    def parse(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(parsed_output=self.parsed)


class LLMGenerationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = GenerationRequest(
            "Use only supplied evidence.", "What does it show?", "[S1] Synthetic evidence.",
        )

    def test_gemini_uses_common_schema(self) -> None:
        port = FakeModels()
        generator = GeminiGenerator("fixture-secret", "explicit-model", models=port)
        result = generator.generate(self.request)
        self.assertEqual(generator.provider, LLMProvider.GEMINI)
        self.assertEqual(result.citation_ids, ["S1"])
        self.assertIn("Verified evidence", port.call["contents"])

    def test_gemini_accepts_sdk_parsed_output(self) -> None:
        port = FakeModels(parsed=PAYLOAD)
        result = GeminiGenerator("fixture", "model", models=port).generate(self.request)
        self.assertEqual(result.text, PAYLOAD["text"])

    def test_openai_uses_responses_structured_parse(self) -> None:
        port = FakeResponses()
        generator = OpenAIGenerator("fixture-secret", "explicit-model", responses=port)
        result = generator.generate(self.request)
        self.assertEqual(generator.provider, LLMProvider.OPENAI)
        self.assertEqual(result.citation_ids, ["S1"])
        self.assertEqual(port.call["text_format"].__name__, "AssistantDraft")

    def test_anthropic_uses_messages_structured_parse(self) -> None:
        port = FakeMessages()
        generator = AnthropicGenerator("fixture-secret", "explicit-model", messages=port)
        result = generator.generate(self.request)
        self.assertEqual(generator.provider, LLMProvider.ANTHROPIC)
        self.assertEqual(result.citation_ids, ["S1"])
        self.assertEqual(port.call["output_format"].__name__, "AssistantDraft")

    def test_sensitive_request_fields_are_not_in_repr(self) -> None:
        rendered = repr(self.request)
        self.assertNotIn("What does it show", rendered)
        self.assertNotIn("Synthetic evidence", rendered)

    def test_configuration_and_invalid_output_fail_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "LLM_API_KEY"):
            OpenAIGenerator("", "explicit-model", responses=FakeResponses())
        with self.assertRaisesRegex(ValueError, "LLM_MODEL"):
            AnthropicGenerator("fixture", "", messages=FakeMessages())
        with self.assertRaisesRegex(RuntimeError, "no structured output"):
            OpenAIGenerator("fixture", "model", responses=FakeResponses(None)).generate(
                self.request,
            )
        invalid = {**PAYLOAD, "citation_ids": ["S1", "S2", "S3", "S4", "S5", "S6"]}
        with self.assertRaises(ValueError):
            AnthropicGenerator("fixture", "model", messages=FakeMessages(invalid)).generate(
                self.request,
            )

    def test_factory_uses_provider_not_model_name(self) -> None:
        with (
            patch("clinical_risk_agent.ai.generation.OpenAIGenerator") as openai_factory,
            patch("clinical_risk_agent.ai.generation.AnthropicGenerator") as anthropic_factory,
            patch("clinical_risk_agent.ai.generation.GeminiGenerator") as gemini_factory,
        ):
            for provider, factory in (
                ("OPENAI", openai_factory),
                ("anthropic", anthropic_factory),
                (" gemini ", gemini_factory),
            ):
                with self.subTest(provider=provider):
                    create_generator(provider, "fixture-secret", "model-name-is-opaque")
                    factory.assert_called_once_with("fixture-secret", "model-name-is-opaque")
                    factory.reset_mock()
        with self.assertRaisesRegex(ValueError, "Unsupported LLM_PROVIDER"):
            create_generator("unknown", "fixture", "model")

    def test_factory_accepts_provider_enum(self) -> None:
        with patch("clinical_risk_agent.ai.generation.OpenAIGenerator") as factory:
            create_generator(LLMProvider.OPENAI, "fixture", "model")
            factory.assert_called_once_with("fixture", "model")

    def test_injected_ports_need_no_client_close(self) -> None:
        GeminiGenerator("fixture", "model", models=FakeModels()).close()
        OpenAIGenerator("fixture", "model", responses=FakeResponses()).close()
        AnthropicGenerator("fixture", "model", messages=FakeMessages()).close()


if __name__ == "__main__":
    unittest.main()
