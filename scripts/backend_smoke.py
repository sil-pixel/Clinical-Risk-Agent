"""Exercise the real FastAPI -> bounded RAG -> Qdrant path locally."""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clinical_risk_agent.backend import BackendSettings, create_app  # noqa: E402
from clinical_risk_agent.inference import questionnaire_requirements  # noqa: E402


def main() -> None:
    settings = BackendSettings(
        root=ROOT, session_signing_key=b"local-smoke-only-signing-key-32-bytes",
        allowed_origins=("http://localhost:5173",),
    )
    with TestClient(create_app(settings)) as client:
        origin = {"Origin": "http://localhost:5173"}
        ready = client.get("/health/ready", headers=origin)
        ready.raise_for_status()
        session = client.post("/v1/session", headers=origin)
        session.raise_for_status()
        auth = {**origin, "Authorization": f"Bearer {session.json()['session_token']}"}
        questions = client.get("/v1/research/questions", headers=auth)
        questions.raise_for_status()
        answer = client.post(
            "/v1/research/answers", headers=auth, json={"question_id": "rq_01"},
        )
        answer.raise_for_status()
        payload = answer.json()
        if (payload["response_kind"] != "curated_support_available"
                or payload["citations"][0]["pmid"] != "21382538"):
            raise AssertionError("Backend returned an invalid bounded answer")
        requirements = client.get("/v1/assessments/questionnaire", headers=auth)
        requirements.raise_for_status()
        contract = questionnaire_requirements()
        assessment = client.post(
            "/v1/assessments", headers=auth, json={
                "questionnaire_version": contract.version,
                "answers": {
                    item.question_id: item.option_ids[0] for item in contract.questions
                },
                "attestations": {
                    "age_18_or_over": True,
                    "self_assessment": True,
                    "research_only_consent": True,
                },
            },
        )
        assessment.raise_for_status()
        assessment_payload = assessment.json()
        if assessment_payload["response_kind"] != "ASSESSMENT_RESULT":
            raise AssertionError("Backend returned an invalid assessment result")
        reset = client.delete("/v1/session", headers=auth)
        reset.raise_for_status()
        print({
            "ready": ready.json()["status"],
            "question_count": len(questions.json()["questions"]),
            "answer_status": payload["response_kind"],
            "pmid": payload["citations"][0]["pmid"],
            "assessment_status": assessment_payload["status"],
            "reset": reset.json()["status"],
        })


if __name__ == "__main__":
    main()
