"""Composition root: builds the conversation stack from settings in one place.

`create_app` asks for a ready conversation service instead of constructing generators,
intent ports and the routing graph itself, so construction policy changes here only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from clinical_risk_agent.ai import (
    HybridIntentPort,
    PromptGuardIntentPort,
    ProtectedConversationOrchestrator,
    PrototypeIntentPort,
    PrototypeLanguagePort,
    PrototypeSafetyPort,
    RoutingGraph,
    create_generator,
)

from .settings import BackendSettings


def build_generators(settings: BackendSettings) -> tuple[Any | None, Any | None]:
    """Create the chat and judge generators, or (None, None) without LLM settings."""
    if not (settings.llm_provider and settings.llm_model and settings.llm_api_key):
        return None, None
    generator = create_generator(settings.llm_provider, settings.llm_api_key,
                                 settings.llm_model)
    judge = create_generator(settings.llm_provider, settings.llm_api_key,
                             settings.llm_judge_model or settings.llm_model)
    return generator, judge


def build_intent_port(settings: BackendSettings):
    """Create the configured intent port: semantic or rules, optionally behind Prompt Guard."""
    port = (HybridIntentPort.from_root(settings.root)
            if settings.intent_router == "semantic" else PrototypeIntentPort())
    if settings.prompt_guard:
        port = PromptGuardIntentPort.from_root(port, settings.root)
    return port


def build_conversation(settings: BackendSettings, research: Any,
                       observer: Callable[[Any], None] | None = None):
    """Assemble the protected conversation orchestrator; return it with its intent port."""
    generator, judge = build_generators(settings)
    intent_port = build_intent_port(settings)
    router = RoutingGraph(PrototypeSafetyPort(), PrototypeLanguagePort(), intent_port,
                          observer=observer)
    return ProtectedConversationOrchestrator(router, research, generator, judge=judge), intent_port
