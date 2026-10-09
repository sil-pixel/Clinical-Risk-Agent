"""Public API contract tests use no user data or model dependencies."""

from __future__ import annotations

import unittest
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from clinical_risk_agent.backend import BackendSettings, create_app
from clinical_risk_agent.inference import questionnaire_feature_codes, questionnaire_requirements


class Clock:
    """Provide clock fixtures and assertions."""
    def __init__(self) -> None:
        """Initialize the synthetic test fixture and its observable state."""
        self.value = 1000.0

    def __call__(self) -> float:
        """Provide call behavior for synthetic test fixtures."""
        return self.value


class FakeResearch:
    """Provide fake research fixtures and assertions."""
    def __init__(self) -> None:
        """Initialize the synthetic test fixture and its observable state."""
        self.calls: list[str] = []
        self.closed = False

    def ready(self):
        """Check research readiness and report the loaded corpus version."""
        return True, "fixture-corpus"

    def answer(self, question_id: str):
        """Answer a supported research question using approved claim evidence."""
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
        """Answer a free-text research question through the bounded evidence workflow."""
        self.calls.append(question)
        return {
            "status": "no_adequate_evidence", "research_only": True,
            "answer": "No adequate evidence.", "limitation": "Research only.",
            "claim_id": None, "citations": [], "related_unverified_passages": [],
        }

    def search_general(self, question: str):
        """Retrieve broader corpus passages for a general research question."""
        self.calls.append(question)
        return {
            "status": "no_adequate_evidence", "answer": "No adequate evidence.",
            "limitation": "Research only.", "citations": [],
            "corpus_version": "fixture-corpus",
        }

    def close(self):
        """Release the owned runtime or provider resources."""
        self.closed = True


class FakeConversation:
    """Provide fake conversation fixtures and assertions."""
    def __init__(self) -> None:
        """Initialize the synthetic test fixture and its observable state."""
        self.calls = []

    def handle(self, text, *, deployment_mode, session_valid):
        """Run protected routing and return the appropriate public conversational outcome."""
        self.calls.append((text, deployment_mode, session_valid))
        return {
            "response_kind": "GROUNDED_ANSWER",
            "message": "Fixture answer [S1].",
            "citations": [{"citation_id": "S1", "pmid": "123"}],
            "limitation": "Research only.", "actions": [],
            "route": "scientific_retrieval", "provider": "gemini",
            "model": "fixture-model", "corpus_version": "fixture-corpus",
        }

    def explain_assessment(self, result):
        """Generate a plain-language explanation of validated research-model display values."""
        return {
            "message": (
                f"Separate fixture explanation for "
                f"{result['positive_symptom_research_probability']} and "
                f"{result['negative_symptom_research_probability']}."
            ),
            "provider": "gemini", "model": "fixture-model", "generated_by_llm": True,
        }


class FakeAssessment:
    """Provide fake assessment fixtures and assertions."""
    def __init__(self) -> None:
        """Initialize the synthetic test fixture and its observable state."""
        self.calls = []

    def requirements(self):
        """Return the public questionnaire version, questions and allowed options."""
        return {
            "questionnaire_version": "prototype_questionnaire_v1",
            "questions": [{"question_id": "q001", "option_ids": ["o01", "o02"]}],
        }

    def assess(self, version, answers, *, deployment_mode, timeout_seconds):
        """Run protected questionnaire validation and return separate research-model estimates."""
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
    """Provide backend apitests fixtures and assertions."""
    def setUp(self) -> None:
        """Prepare isolated fixtures before each test."""
        self.clock = Clock()
        self.service = FakeResearch()
        self.settings = BackendSettings(
            root=Path("."), session_signing_key=b"x" * 32,
            allowed_origins=("https://portfolio.example",),
            model_turns_per_hour=2, model_turns_per_day=3,
            global_model_operations_per_day=20, intent_router="rules", prompt_guard=False,
        )
        self.client_context = TestClient(create_app(
            self.settings, service=self.service, clock=self.clock,
        ))
        self.client = self.client_context.__enter__()
        self.origin = {"Origin": "https://portfolio.example"}

    def tearDown(self) -> None:
        """Release test resources and restore isolated state."""
        self.client_context.__exit__(None, None, None)
        self.assertTrue(self.service.closed)

    def session(self) -> str:
        """Provide session behavior for synthetic test fixtures."""
        response = self.client.post("/v1/session", headers=self.origin)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["cache-control"], "no-store")
        return response.json()["session_token"]

    def auth(self, token: str) -> dict[str, str]:
        """Provide auth behavior for synthetic test fixtures."""
        return {**self.origin, "Authorization": f"Bearer {token}"}

    def test_health_session_question_and_answer_flow(self) -> None:
        """Verify health session question and answer flow."""
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
        """Verify arbitrary text and extra fields never reach retrieval."""
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
        """Verify origin upload session and quota guards."""
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
        """Verify inactivity expiry is server authoritative."""
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
        """Verify tampered session is rejected without detail."""
        token = self.session()
        response = self.client.get(
            "/v1/research/questions", headers=self.auth(token + "tampered"),
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "SESSION_INVALID")

    def test_public_message_contract_uses_protected_conversation_service(self) -> None:
        """Verify public message contract uses protected conversation service."""
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
        """Verify sse emits only typed validated events."""
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

    def test_sse_generation_failure_is_error_not_validated_answer(self):
        """Verify sse generation failure is error not validated answer."""
        class UnavailableConversation(FakeConversation):
            """Provide unavailable conversation fixtures and assertions."""
            def handle(self, *args, **kwargs):
                """Run protected routing and return the appropriate public conversational outcome."""
                return {"response_kind": "GENERATION_UNAVAILABLE", "message": "Fixture failure"}
        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=UnavailableConversation())) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            response = client.post("/v1/messages:stream", headers=self.auth(token),
                                   json={"kind": "free_text", "text": "Fixture"})
            self.assertIn("event: error", response.text)
            self.assertIn("GENERATION_UNAVAILABLE", response.text)
            self.assertNotIn("event: validated_content", response.text)
            self.assertNotIn("event: done", response.text)

    def test_live_quality_runs_for_both_message_endpoints(self):
        """Verify live quality runs for both message endpoints."""
        class JudgedConversation(FakeConversation):
            """Provide judged conversation fixtures and assertions."""
            def evaluate_response(self, text, result):
                """Provide evaluate response behavior for synthetic test fixtures."""
                return {"groundedness": .7, "correctness": .9, "judge_model": "fixture"}
        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=JudgedConversation())) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            for endpoint in ("/v1/messages", "/v1/messages:stream"):
                client.post(endpoint, headers=self.auth(token),
                            json={"kind": "free_text", "text": "Fixture private question"})
                for _ in range(50):
                    quality = client.get("/v1/evaluations/dashboard").json()["live_quality"]
                    if quality["pending"] == 0:
                        break
                    time.sleep(.01)
            self.assertEqual(quality["evaluated"], 2)
            self.assertEqual(quality["correctness"]["mean"], .9)
            self.assertNotIn("Fixture private question", str(quality))

    def test_live_judge_failure_does_not_fail_chat(self):
        """Verify live judge failure does not fail chat."""
        class FailedJudge(FakeConversation):
            """Provide failed judge fixtures and assertions."""
            def evaluate_response(self, text, result):
                """Provide evaluate response behavior for synthetic test fixtures."""
                raise RuntimeError("Synthetic judge failure")
        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=FailedJudge())) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            response = client.post("/v1/messages", headers=self.auth(token),
                                   json={"kind": "free_text", "text": "Fixture"})
            self.assertEqual(response.status_code, 200)
            for _ in range(50):
                quality = client.get("/v1/evaluations/dashboard").json()["live_quality"]
                if quality["pending"] == 0:
                    break
                time.sleep(.01)
            self.assertEqual(quality["errors"], 1)
            self.assertIsNone(quality["correctness"]["mean"])

    def test_old_questionnaire_version_is_rejected_before_inference(self):
        """Verify obsolete submissions cannot be reinterpreted under a revised ID mapping."""
        class RevisedAssessment(FakeAssessment):
            """Expose a revised questionnaire contract for version-boundary tests."""

            def requirements(self):
                """Return the fixture questionnaire with the current version identifier."""
                return {**super().requirements(), "questionnaire_version": "prototype_questionnaire_v2"}

        assessment = RevisedAssessment()
        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=FakeConversation(), assessment=assessment)) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            response = client.post("/v1/assessments", headers=self.auth(token), json={
                "questionnaire_version": "prototype_questionnaire_v1",
                "answers": {"q001": "o01"},
                "attestations": {"age_18_or_over": True, "self_assessment": True,
                                 "research_only_consent": True},
            })
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["error"]["code"], "QUESTIONNAIRE_VERSION_UNSUPPORTED")
            self.assertEqual(assessment.calls, [])

    def test_chat_receives_session_result_after_assessment(self) -> None:
        """Verify chat calls get prior_result only once this session has a ready result."""
        conversation = FakeConversation()
        conversation.handle = lambda text, **kwargs: (
            conversation.calls.append((text, kwargs)) or FakeConversation().handle(
                text, deployment_mode=kwargs["deployment_mode"],
                session_valid=kwargs["session_valid"]))
        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=conversation,
                                   assessment=FakeAssessment())) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            client.post("/v1/messages", headers=self.auth(token),
                        json={"kind": "free_text", "text": "explain my result"})
            self.assertNotIn("prior_result", conversation.calls[-1][1])
            client.post("/v1/assessments", headers=self.auth(token), json={
                "questionnaire_version": "prototype_questionnaire_v1",
                "answers": {"q001": "o01"},
                "attestations": {"age_18_or_over": True, "self_assessment": True,
                                 "research_only_consent": True},
            })
            client.post("/v1/messages", headers=self.auth(token),
                        json={"kind": "free_text", "text": "explain my result"})
            prior = conversation.calls[-1][1]["prior_result"]
            self.assertEqual(prior["positive_symptom_research_probability"], "12.3%")

    def test_message_forwards_only_confirmable_intents(self) -> None:
        """Verify confirmed intents reach the conversation and unsafe ones are rejected."""
        conversation = FakeConversation()
        conversation.handle = lambda text, **kwargs: (
            conversation.calls.append((text, kwargs)) or FakeConversation().handle(
                text, deployment_mode=kwargs["deployment_mode"],
                session_valid=kwargs["session_valid"]))
        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=conversation)) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            ok = client.post("/v1/messages", headers=self.auth(token), json={
                "kind": "free_text", "text": "does poverty matter",
                "confirmed_intent": "scientific_question"})
            self.assertEqual(ok.status_code, 200)
            self.assertEqual(conversation.calls[-1][1]["confirmed_intent"], "scientific_question")
            client.post("/v1/messages", headers=self.auth(token),
                        json={"kind": "free_text", "text": "hello"})
            self.assertNotIn("confirmed_intent", conversation.calls[-1][1])
            unsafe = client.post("/v1/messages", headers=self.auth(token), json={
                "kind": "free_text", "text": "my dose",
                "confirmed_intent": "unsupported_or_unsafe"})
            self.assertEqual(unsafe.status_code, 422)

    def test_ready_assessment_records_aggregate_drift_inputs(self) -> None:
        """Verify ready assessments feed drift counters through the optional service hook."""
        class DriftAssessment(FakeAssessment):
            """Expose fixture feature codes for drift monitoring."""
            def drift_features(self, version, answers):
                """Return complete first-option feature codes for the fixture submission."""
                return questionnaire_feature_codes(
                    {item.question_id: "o01" for item in questionnaire_requirements().questions})

        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=FakeConversation(),
                                   assessment=DriftAssessment())) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            response = client.post("/v1/assessments", headers=self.auth(token), json={
                "questionnaire_version": "prototype_questionnaire_v1",
                "answers": {"q001": "o01"},
                "attestations": {"age_18_or_over": True, "self_assessment": True,
                                 "research_only_consent": True},
            })
            self.assertEqual(response.status_code, 200)
            drift = client.get("/v1/evaluations/dashboard").json()["input_drift"]
            self.assertEqual(drift["n"], 1)
            self.assertNotIn("features", drift)
            dashboard = client.get("/v1/evaluations/dashboard").json()
            self.assertEqual(dashboard["input_ood"]["n"], 1)
            self.assertNotIn("input_monitoring", str(dashboard["operations"]))

    def test_input_monitoring_failure_keeps_assessment_result(self) -> None:
        """Verify a drift or OOD scoring error is logged without failing the assessment."""
        class BrokenDriftAssessment(FakeAssessment):
            """Return incomplete feature codes that OOD scoring cannot use."""
            def drift_features(self, version, answers):
                """Return a partial code map that OOD scoring cannot use."""
                return {"SEX": 1}

        with TestClient(create_app(self.settings, service=self.service,
                                   conversation=FakeConversation(),
                                   assessment=BrokenDriftAssessment())) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            response = client.post("/v1/assessments", headers=self.auth(token), json={
                "questionnaire_version": "prototype_questionnaire_v1",
                "answers": {"q001": "o01"},
                "attestations": {"age_18_or_over": True, "self_assessment": True,
                                 "research_only_consent": True},
            })
            self.assertEqual(response.status_code, 200)
            operations = client.get("/v1/evaluations/dashboard").json()["operations"]
            self.assertIn("input_monitoring", [row["operation"] for row in operations])

    def test_public_questionnaire_contract_and_submission(self) -> None:
        """Verify public questionnaire contract and submission."""
        assessment = FakeAssessment()
        conversation = FakeConversation()
        with TestClient(create_app(
            self.settings, service=self.service, conversation=conversation,
            assessment=assessment, clock=self.clock,
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
            for _ in range(20):
                latest = client.get("/v1/assessments/latest", headers=self.auth(token)).json()
                if latest.get("explanation_status") != "pending":
                    break
                time.sleep(0.01)
            self.assertIn("12.3%", latest["explanation"])
            self.assertTrue(latest["explanation_generated_by_llm"])
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

    def test_explanation_timeout_preserves_scores_and_session_isolation(self):
        """Verify explanation timeout preserves scores and session isolation."""
        class SlowConversation(FakeConversation):
            """Provide slow conversation fixtures and assertions."""
            def explain_assessment(self, result):
                """Generate a plain-language explanation of validated research-model display values."""
                time.sleep(0.1)
                return super().explain_assessment(result)

        from dataclasses import replace
        assessment = FakeAssessment()
        with TestClient(create_app(
            replace(self.settings, request_timeout_seconds=0.03), service=self.service,
            assessment=assessment, conversation=SlowConversation(), clock=self.clock,
        )) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            response = client.post("/v1/assessments", headers=self.auth(token), json={
                "questionnaire_version": "prototype_questionnaire_v1", "answers": {"q001": "o01"},
                "attestations": {"age_18_or_over": True, "self_assessment": True,
                                 "research_only_consent": True},
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["explanation_status"], "pending")
            time.sleep(0.06)
            latest = client.get("/v1/assessments/latest", headers=self.auth(token)).json()
            self.assertEqual(latest["result"]["positive_symptom_research_probability"], "12.3%")
            self.assertEqual(latest["explanation_status"], "unavailable")
            retried = client.post("/v1/assessments/explanation", headers=self.auth(token))
            self.assertEqual(retried.status_code, 200)
            self.assertEqual(retried.json()["explanation_status"], "pending")
            self.assertEqual(len(assessment.calls), 1)
            other = client.post("/v1/session", headers=self.origin).json()["session_token"]
            self.assertEqual(client.get("/v1/assessments/latest", headers=self.auth(other)).status_code, 404)
            client.delete("/v1/session", headers=self.auth(token))
            self.assertEqual(client.get("/v1/assessments/latest", headers=self.auth(token)).status_code, 401)

    def test_dashboard_records_aggregates_without_request_text(self):
        """Verify dashboard records aggregates without request text."""
        with TestClient(create_app(self.settings, service=self.service,
                                  conversation=FakeConversation(), assessment=FakeAssessment())) as client:
            token = client.post("/v1/session", headers=self.origin).json()["session_token"]
            client.post("/v1/messages", headers=self.auth(token),
                        json={"kind": "free_text", "text": "Synthetic private fixture"})
            response = client.get("/v1/evaluations/dashboard")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["operations"][0]["count"], 1)
            self.assertNotIn("Synthetic private fixture", response.text)
            self.assertEqual(client.get("/v1/evaluations/dashboard",
                                        headers={"X-Forwarded-For": "203.0.113.1"}).status_code, 403)


class BackendSettingsTests(unittest.TestCase):
    """Provide backend settings tests fixtures and assertions."""
    def test_root_env_is_loaded_without_exposing_key(self) -> None:
        """Verify root env is loaded without exposing key."""
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
        """Verify partial or unknown llm configuration fails closed."""
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
        """Verify local session creation limit is configurable."""
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
