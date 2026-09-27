"""Exercise one non-user curated question through the configured LLM provider."""

from __future__ import annotations

import json
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
        events = []
        with client.stream(
            "POST", "/v1/messages:stream", headers=auth,
            json={"kind": "free_text", "text": CURATED_QUESTIONS[0].question},
        ) as response:
            response.raise_for_status()
            event_name = None
            for line in response.iter_lines():
                if line.startswith("event: "):
                    event_name = line[7:]
                elif line.startswith("data: ") and event_name:
                    events.append((event_name, json.loads(line[6:])))
                    event_name = None
        content = next(data for event, data in events if event == "validated_content")
        evidence = [data for event, data in events if event == "evidence"]
        done = next(data for event, data in events if event == "done")
        if (content["response_kind"] != "GROUNDED_ANSWER"
                or done["provider"] != settings.llm_provider
                or evidence[0]["pmid"] != "21382538"):
            raise AssertionError("Conversation path returned an invalid grounded response")
        client.delete("/v1/session", headers=auth).raise_for_status()
        print({
            "response_kind": content["response_kind"],
            "provider": done["provider"],
            "citation_count": len(evidence),
            "transport": "sse",
            "validated": True,
        })


if __name__ == "__main__":
    main()
