"""Fail-closed backend configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BackendSettings:
    root: Path
    session_signing_key: bytes
    allowed_origins: tuple[str, ...]
    llm_provider: str | None = None
    llm_model: str | None = None
    llm_api_key: str | None = field(default=None, repr=False)
    deployment_mode: str = "prototype_demo"
    session_ttl_seconds: int = 1800
    request_timeout_seconds: float = 55.0
    max_request_bytes: int = 4096
    max_active_sessions: int = 50
    max_http_concurrency: int = 50
    max_model_concurrency: int = 8
    model_turns_per_hour: int = 10
    model_turns_per_day: int = 25
    assessment_submissions_per_day: int = 3
    global_model_operations_per_day: int = 1000
    session_creations_per_network_hour: int = 5

    def __post_init__(self) -> None:
        if self.deployment_mode != "prototype_demo":
            raise ValueError("Only prototype_demo is supported")
        if len(self.session_signing_key) < 32:
            raise ValueError("SESSION_SIGNING_KEY must contain at least 32 bytes")
        if not self.allowed_origins or any(not item.startswith(("http://", "https://"))
                                           for item in self.allowed_origins):
            raise ValueError("At least one explicit HTTP(S) origin is required")
        if "*" in self.allowed_origins:
            raise ValueError("Wildcard CORS is forbidden")
        if self.session_ttl_seconds != 1800:
            raise ValueError("The approved session TTL is exactly 30 minutes")
        llm_values = (self.llm_provider, self.llm_model, self.llm_api_key)
        if any(llm_values) and not all(value and value.strip() for value in llm_values):
            raise ValueError("LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY must be configured together")
        if self.llm_provider is not None:
            normalized_provider = self.llm_provider.strip().lower()
            if normalized_provider not in {"openai", "anthropic", "gemini"}:
                raise ValueError("LLM_PROVIDER must be openai, anthropic, or gemini")
            object.__setattr__(self, "llm_provider", normalized_provider)
            object.__setattr__(self, "llm_model", self.llm_model.strip())

    @classmethod
    def from_env(cls, *, root: Path | None = None) -> "BackendSettings":
        resolved_root = (root or Path(__file__).resolve().parents[3]).resolve()
        from dotenv import load_dotenv

        load_dotenv(resolved_root / ".env", override=False)
        secret = os.getenv("SESSION_SIGNING_KEY", "")
        origins = tuple(item.strip() for item in os.getenv(
            "ALLOWED_ORIGINS", "http://localhost:5173",
        ).split(",") if item.strip())
        return cls(
            root=resolved_root,
            session_signing_key=secret.encode("utf-8"),
            allowed_origins=origins,
            llm_provider=os.getenv("LLM_PROVIDER") or None,
            llm_model=os.getenv("LLM_MODEL") or None,
            llm_api_key=os.getenv("LLM_API_KEY") or None,
        )
