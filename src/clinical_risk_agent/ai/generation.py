"""Provider-neutral structured generation adapters.

These adapters have no tool authority and are not exposed by the public API.
Callers must apply the approved privacy, safety, intent, evidence, and response
validation gates before invoking any provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class AssistantDraft(BaseModel):
    """Common draft schema returned by every provider adapter."""

    model_config = ConfigDict(extra="forbid", strict=True)
    response_kind: Literal["conversation", "grounded_answer", "refusal"]
    text: str = Field(min_length=1, max_length=4000)
    citation_ids: list[str] = Field(default_factory=list, max_length=5)


@dataclass(frozen=True, slots=True)
class GenerationRequest:
    system_instruction: str
    user_text: str = field(repr=False)
    evidence_context: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if not self.system_instruction.strip():
            raise ValueError("System instruction is required")
        if not 1 <= len(self.user_text.strip()) <= 4000:
            raise ValueError("User text must be 1 to 4000 characters")
        if self.evidence_context is not None and len(self.evidence_context) > 20000:
            raise ValueError("Evidence context is too large")


class StructuredGenerator(Protocol):
    @property
    def provider(self) -> LLMProvider: ...

    @property
    def model(self) -> str: ...

    def generate(self, request: GenerationRequest) -> AssistantDraft: ...

    def close(self) -> None: ...


class ModelsPort(Protocol):
    def generate_content(self, **kwargs: Any) -> Any: ...


class ResponsesPort(Protocol):
    def parse(self, **kwargs: Any) -> Any: ...


class MessagesPort(Protocol):
    def parse(self, **kwargs: Any) -> Any: ...


def _validate_configuration(api_key: str, model: str) -> None:
    if not api_key.strip():
        raise ValueError("LLM_API_KEY is not configured")
    if not model.strip():
        raise ValueError("LLM_MODEL is not configured")


def _user_content(request: GenerationRequest) -> str:
    if request.evidence_context:
        return (
            f"User message:\n{request.user_text}\n\n"
            f"Verified evidence:\n{request.evidence_context}"
        )
    return request.user_text


class GeminiGenerator:
    def __init__(self, api_key: str, model: str, *, models: ModelsPort | None = None) -> None:
        _validate_configuration(api_key, model)
        self._model = model.strip()
        self._client = None
        if models is None:
            from google import genai

            from google.genai import types

            self._client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
                timeout=45000, retry_options=types.HttpRetryOptions(attempts=1),
            ))
            models = self._client.models
        self._models = models

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.GEMINI

    @property
    def model(self) -> str:
        return self._model

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def generate(self, request: GenerationRequest) -> AssistantDraft:
        from google.genai import types

        # Gemini's response_schema dialect does not accept Pydantic's
        # additionalProperties keyword. Keep the transport schema minimal and
        # apply the full strict Pydantic contract after receipt.
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "response_kind": {
                    "type": "STRING",
                    "enum": ["conversation", "grounded_answer", "refusal"],
                },
                "text": {"type": "STRING"},
                "citation_ids": {"type": "ARRAY", "items": {"type": "STRING"}},
            },
            "required": ["response_kind", "text", "citation_ids"],
        }
        response = self._models.generate_content(
            model=self._model,
            contents=_user_content(request),
            config=types.GenerateContentConfig(
                system_instruction=request.system_instruction,
                max_output_tokens=1200,
                response_mime_type="application/json",
                response_schema=response_schema,
            ),
        )
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return AssistantDraft.model_validate(parsed)
        if not isinstance(response.text, str):
            raise RuntimeError("LLM provider returned no structured output")
        return AssistantDraft.model_validate_json(response.text)


class OpenAIGenerator:
    def __init__(
        self, api_key: str, model: str, *, responses: ResponsesPort | None = None,
    ) -> None:
        _validate_configuration(api_key, model)
        self._model = model.strip()
        self._client = None
        if responses is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=api_key, timeout=45.0, max_retries=0)
            responses = self._client.responses
        self._responses = responses

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.OPENAI

    @property
    def model(self) -> str:
        return self._model

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def generate(self, request: GenerationRequest) -> AssistantDraft:
        response = self._responses.parse(
            model=self._model,
            input=[
                {"role": "system", "content": request.system_instruction},
                {"role": "user", "content": _user_content(request)},
            ],
            text_format=AssistantDraft,
        )
        if response.output_parsed is None:
            raise RuntimeError("LLM provider returned no structured output")
        return AssistantDraft.model_validate(response.output_parsed)


class AnthropicGenerator:
    def __init__(
        self, api_key: str, model: str, *, messages: MessagesPort | None = None,
    ) -> None:
        _validate_configuration(api_key, model)
        self._model = model.strip()
        self._client = None
        if messages is None:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=api_key, timeout=45.0, max_retries=0)
            messages = self._client.messages
        self._messages = messages

    @property
    def provider(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC

    @property
    def model(self) -> str:
        return self._model

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def generate(self, request: GenerationRequest) -> AssistantDraft:
        response = self._messages.parse(
            model=self._model,
            max_tokens=1200,
            system=request.system_instruction,
            messages=[{"role": "user", "content": _user_content(request)}],
            output_format=AssistantDraft,
        )
        if response.parsed_output is None:
            raise RuntimeError("LLM provider returned no structured output")
        return AssistantDraft.model_validate(response.parsed_output)


def create_generator(provider: str | LLMProvider, api_key: str, model: str) -> StructuredGenerator:
    """Construct the explicitly selected provider without inspecting the model name."""

    try:
        selected = provider if isinstance(provider, LLMProvider) else LLMProvider(
            provider.strip().lower(),
        )
    except ValueError as exc:
        supported = ", ".join(item.value for item in LLMProvider)
        raise ValueError(f"Unsupported LLM_PROVIDER; expected one of: {supported}") from exc

    factories = {
        LLMProvider.OPENAI: OpenAIGenerator,
        LLMProvider.ANTHROPIC: AnthropicGenerator,
        LLMProvider.GEMINI: GeminiGenerator,
    }
    return factories[selected](api_key, model)
