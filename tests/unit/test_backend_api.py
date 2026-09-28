"""Public API contract tests use no user data or model dependencies."""

from __future__ import annotations

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from clinical_risk_agent.backend import BackendSettings, create_app


class Clock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value


class FakeResearch:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.closed = False

    def ready(self):
        return True, "fixture-corpus"

    def answer(self, question_id: str):
        self.calls.append(question_id)
        return {
            "status": "curated_support_available", "research_only": True,
            "answer": "Fixture finding [S1].", "limitation": "Research only.",
            "claim_id": "fixture", "retrieval_mode": "keyword_fallback",
            "corpus_version": "fixture-corpus",
            "citations": [{"citation_id": "S1", "pmid": "123",
                           "exact_matched_text": "Fixture exact text."}],
            "related_unverified_passages": [],
        }

    def answer_text(self, question: str):
        self.calls.append(question)
        return {
            "status": "no_adequate_evidence", "research_only": True,
            "answer": "No adequate evidence.", "limitation": "Research only.",
            "claim_id": None, "citations": [], "related_unverified_passages": [],
        }

    def close(self):
        self.closed = True


class FakeConversation:
    def __init__(self) -> None:
        self.calls = []

    def handle(self, text, *, deployment_mode, session_valid):
        self.calls.append((text, deployment_mode, session_valid))
        return {
            "response_kind": "GROUNDED_ANSWER",
            "message": "Fixture answer [S1].",
            "citations": [{"citation_id": "S1", "pmid": "123"}],
            "limitation": "Research only.", "actions": [],
            "route": "scientific_retrieval", "provider": "gemini",
            "model": "fixture-model", "corpus_version": "fixture-corpus",
        }


class FakeAssessment:
    def __init__(self) -> None:
        self.calls = []

    def requirements(self):
        return {
            "questionnaire_version": "prototype_questionnaire_v1",
            "questions": [{"question_id": "q001", "option_ids": ["o01", "o02"]}],
        }

    def assess(self, version, answers, *, deployment_mode, timeout_seconds):
        self.calls.append((version, answers, deployment_mode, timeout_seconds))
        return {
            "response_kind": "ASSESSMENT_RESULT", "status": "assessment_ready",
            "result": {
                "positive_symptom_research_probability": "12.3%",
                "negative_symptom_research_probability": "45.6%",
                "generic_profile_version": "generic_genetic_profile_v1",
                "synthetic_training_data": True,
            },
            "prediction_note": "Fixture prediction-only note.",
            "limitation": "Fixture research-only limitation.",
        }


class BackendAPITests(unittest.TestCase):
    def setUp(self) -> None:
        self.clock = Clock()
        self.service = FakeResearch()
        self.settings = BackendSettings(
            root=Path("."), session_signing_key=b"x" * 32,
            allowed_origins=("https://portfolio.example",),
            model_turns_per_hour=2, model_turns_per_day=3,
            global_model_operations_per_day=20,
        )
        self.client_context = TestClient(create_app(
            self.settings, service=self.service, clock=self.clock,
        ))
        self.client = self.client_context.__enter__()
        self.origin = {"Origin": "https://portfolio.example"}

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.assertTrue(self.service.closed)

    def session(self) -> str:
        response = self.client.post("/v1/session", headers=self.origin)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()["session_token"]

    def auth(self, token: str) -> dict[str, str]:
        return {**self.origin, "Authorization": f"Bearer {token}"}

    def test_health_session_question_and_answer_flow(self) -> None:
        self.assertEqual(self.client.get("/health/live").json()["status"], "live")
        self.assertEqual(self.client.get("/health/ready").json()["corpus_version"],
                         "fixture-corpus")
        token = self.session()
        questions = self.client.get("/v1/research/questions", headers=self.auth(token))
        self.assertEqual(questions.status_code, 200)
        self.assertEqual(len(questions.json()["questions"]), 5)
        response = self.client.post(
            "/v1/research/answers", headers=self.auth(token), json={"question_id": "rq_01"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["response_kind"], "curated_support_available")
        self.assertEqual(response.json()["citations"][0]["citation_id"], "S1")
        self.assertEqual(self.service.calls, ["rq_01"])
        cleared = self.client.delete("/v1/session", headers=self.auth(token))
        self.assertEqual(cleared.status_code, 200)
        self.assertEqual(self.client.get(
            "/v1/research/questions", headers=self.auth(token),
        ).status_code, 401)

    def test_arbitrary_text_and_extra_fields_never_reach_retrieval(self) -> None:
        token = self.session()
        for payload in (
            {"question": "Tell me what medication to take"},
            {"question_id": "rq_99"},
            {"question_id": "rq_01", "session_valid": True},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(
                    "/v1/research/answers", headers=self.auth(token), json=payload,
                )
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.json()["error"]["code"], "INVALID_REQUEST")
        self.assertEqual(self.service.calls, [])

    def test_origin_upload_session_and_quota_guards(self) -> None:
        denied = self.client.post("/v1/session", headers={"Origin": "https://evil.example"})
        self.assertEqual(denied.status_code, 403)
        upload = self.client.post(
            "/v1/session", headers={**self.origin, "Content-Type": "multipart/form-data"},
        )
        self.assertEqual(upload.status_code, 415)
        missing = self.client.get("/v1/research/questions", headers=self.origin)
        self.assertEqual(missing.status_code, 401)

        token = self.session()
        for _ in range(2):
            self.assertEqual(self.client.post(
                "/v1/research/answers", headers=self.auth(token),
                json={"question_id": "rq_01"},
            ).status_code, 200)
        limited = self.client.post(
            "/v1/research/answers", headers=self.auth(token),
            json={"question_id": "rq_01"},
        )
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.json()["error"]["code"], "SESSION_QUOTA_EXHAUSTED")

    def test_inactivity_expiry_is_server_authoritative(self) -> None:
        token = self.session()
        self.clock.value += 1700.0
        self.assertEqual(self.client.get(
            "/v1/research/questions", headers=self.auth(token),
        ).status_code, 200)
        # Reading static content is polling, not explicit activity.
        self.clock.value += 100.0
        response = self.client.get("/v1/research/questions", headers=self.auth(token))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "SESSION_INVALID")

    def test_tampered_session_is_rejected_without_detail(self) -> None:
        token = self.session()
        response = self.client.get(
            "/v1/research/questions", headers=self.auth(token + "tampered"),
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "SESSION_INVALID")

    def test_public_message_contract_uses_protected_conversation_service(self) -> None:
        conversation = FakeConversation()
        with TestClient(create_app(
            self.settings, service=self.service, conversation=conversation, clock=self.clock,
        )) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            response = client.post(
                "/v1/messages", headers=self.auth(token),
                json={"kind": "free_text", "text": "Fixture research question?"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["response_kind"], "GROUNDED_ANSWER")
            self.assertEqual(conversation.calls, [
                ("Fixture research question?", "prototype_demo", True),
            ])
            invalid = client.post(
                "/v1/messages", headers=self.auth(token),
                json={"kind": "free_text", "text": "hello", "session_valid": True},
            )
            self.assertEqual(invalid.status_code, 422)

    def test_sse_emits_only_typed_validated_events(self) -> None:
        conversation = FakeConversation()
        with TestClient(create_app(
            self.settings, service=self.service, conversation=conversation, clock=self.clock,
        )) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            with client.stream(
                "POST", "/v1/messages:stream", headers=self.auth(token),
                json={"kind": "free_text", "text": "Fixture research question?"},
            ) as response:
                body = "".join(response.iter_text())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers["content-type"].split(";")[0],
                             "text/event-stream")
            self.assertIn("event: status", body)
            self.assertIn("event: validated_content", body)
            self.assertIn("event: evidence", body)
            self.assertIn("event: done", body)
            self.assertNotIn("event: token", body)

    def test_public_questionnaire_contract_and_submission(self) -> None:
        assessment = FakeAssessment()
        with TestClient(create_app(
            self.settings, service=self.service, assessment=assessment, clock=self.clock,
        )) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            requirements = client.get(
                "/v1/assessments/questionnaire", headers=self.auth(token),
            )
            self.assertEqual(requirements.status_code, 200)
            self.assertEqual(requirements.json()["questions"][0]["question_id"], "q001")
            response = client.post(
                "/v1/assessments", headers=self.auth(token), json={
                    "questionnaire_version": "prototype_questionnaire_v1",
                    "answers": {"q001": "o01"},
                    "attestations": {
                        "age_18_or_over": True,
                        "self_assessment": True,
                        "research_only_consent": True,
                    },
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["response_kind"], "ASSESSMENT_RESULT")
            self.assertEqual(response.json()["result"][
                "positive_symptom_research_probability"
            ], "12.3%")
            self.assertEqual(len(assessment.calls), 1)
            forged = client.post(
                "/v1/assessments", headers=self.auth(token), json={
                    "questionnaire_version": "prototype_questionnaire_v1",
                    "answers": {"q001": "o01"},
                    "attestations": {
                        "age_18_or_over": False,
                        "self_assessment": True,
                        "research_only_consent": True,
                    },
                },
            )
            self.assertEqual(forged.status_code, 422)


class BackendSettingsTests(unittest.TestCase):
    def test_root_env_is_loaded_without_exposing_key(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "LLM_PROVIDER=anthropic\n"
                "LLM_MODEL=fixture-model\n"
                "LLM_API_KEY=fixture-provider-key\n"
                "SESSION_SIGNING_KEY=fixture-session-signing-key-32-bytes\n"
                "ALLOWED_ORIGINS=http://localhost:5173\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                settings = BackendSettings.from_env(root=root)
            self.assertEqual(settings.llm_provider, "anthropic")
            self.assertEqual(settings.llm_model, "fixture-model")
            self.assertEqual(settings.llm_api_key, "fixture-provider-key")
            self.assertNotIn("fixture-provider-key", repr(settings))

    def test_partial_or_unknown_llm_configuration_fails_closed(self) -> None:
        base = {
            "root": Path("."),
            "session_signing_key": b"x" * 32,
            "allowed_origins": ("https://portfolio.example",),
        }
        with self.assertRaisesRegex(ValueError, "configured together"):
            BackendSettings(**base, llm_provider="openai")
        with self.assertRaisesRegex(ValueError, "must be openai"):
            BackendSettings(
                **base, llm_provider="unknown", llm_model="model", llm_api_key="key",
            )

    def test_local_session_creation_limit_is_configurable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".env").write_text(
                "SESSION_SIGNING_KEY=fixture-session-signing-key-32-bytes\n"
                "ALLOWED_ORIGINS=http://localhost:5173\n"
                "SESSION_CREATIONS_PER_NETWORK_HOUR=25\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                settings = BackendSettings.from_env(root=root)
            self.assertEqual(settings.session_creations_per_network_hour, 25)


if __name__ == "__main__":
    unittest.main()
