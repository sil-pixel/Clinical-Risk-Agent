"""Exercise one non-user curated question through the configured LLM provider."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_risk_agent.backend import BackendSettings, create_app  # noqa: E402
from clinical_risk_agent.rag.answering import CURATED_QUESTIONS  # noqa: E402


def main() -> None:
    settings = BackendSettings.from_env(root=ROOT)
    if not (settings.llm_provider and settings.llm_model and settings.llm_api_key):
        raise RuntimeError("LLM_PROVIDER, LLM_MODEL, and LLM_API_KEY are required")
    with TestClient(create_app(settings)) as client:
        origin = {"Origin": settings.allowed_origins[0]}
        session = client.post("/v1/session", headers=origin)
        session.raise_for_status()
        auth = {**origin, "Authorization": f"Bearer {session.json()['session_token']}"}
        response = client.post(
            "/v1/messages", headers=auth,
            json={"kind": "free_text", "text": CURATED_QUESTIONS[0].question},
        )
        response.raise_for_status()
        payload = response.json()
        if (payload["response_kind"] != "GROUNDED_ANSWER"
                or payload["provider"] != settings.llm_provider
                or payload["citations"][0]["pmid"] != "21382538"):
            raise AssertionError("Conversation path returned an invalid grounded response")
        client.delete("/v1/session", headers=auth).raise_for_status()
        print({
            "response_kind": payload["response_kind"],
            "provider": payload["provider"],
            "citation_count": len(payload["citations"]),
            "validated": True,
        })


if __name__ == "__main__":
    main()
