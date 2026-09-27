# Backend integration and deployment handoff

Status: **local bounded conversational RAG API implemented and verified; cloud deployment not performed** (2026-09-27).

This is currently a deliberately narrow public prototype boundary. It exposes five reviewed research questions by opaque public ID and through a free-text chat route. The product direction is a chat-first conversational interface with the questionnaire available as an optional left-side workflow. The backend loads `LLM_PROVIDER`, `LLM_MODEL`, and `LLM_API_KEY` from the git-ignored root `.env`. Provider-neutral structured-output adapters support OpenAI, Anthropic, and Gemini. The chat path has deterministic prototype routing and is not production- or clinical-release approved.

## Implemented contract

| Operation | Route | Authentication | Behavior |
| --- | --- | --- | --- |
| Liveness | `GET /health/live` | None | Process-only liveness. |
| Readiness | `GET /health/ready` | None | Loads and verifies the corpus manifest, assertion catalog, encoder hashes, current source eligibility and Qdrant point count. |
| Create session | `POST /v1/session` | None | Returns a signed opaque credential with a 30-minute inactivity expiry. |
| List questions | `GET /v1/research/questions` | Bearer session | Returns five public IDs and fixed question wording. This static read does not renew inactivity. |
| Answer question | `POST /v1/research/answers` | Bearer session | Accepts only `{"question_id":"rq_01"}` through `rq_05`; retrieves through hierarchical Qdrant/BM25 and returns the claim-checked fixed answer or a typed safe failure. |
| Submit chat turn | `POST /v1/messages` | Bearer session | Accepts only `{"kind":"free_text","text":"..."}`. Runs safety, language, and intent preflight. Exact supported research questions use verified RAG, the configured provider, strict structured output, exact answer/citation validation, and one validation retry. |
| Reset | `DELETE /v1/session` | Bearer session | Idempotently removes the in-memory session state. |

The service derives authorization from the bearer credential, never from client-supplied booleans. It has narrow CORS, a 4 KiB body ceiling, multipart rejection, `Cache-Control: no-store`, generic validation errors, an exact 30-minute memory-only session TTL, five session creations/hour/transient one-way network digest, 10 research operations/hour/session, 25/day/session, 1,000/day/process, 50 HTTP requests, eight model-heavy operations and a 55-second application deadline. No request text, answer, evidence, credential, network address or session identifier is logged or persisted by application code.

The chat endpoint remains bounded: safety/refusal, language, clarification, assessment-redirection, greeting, and unsupported routes are deterministic and invoke no external provider. Only a routed scientific request reaches research; only an exact claim-verified question reaches generation. Broader scientific wording returns no adequate evidence, and the generator is forbidden from answering from pretrained knowledge. This boundary does not authorize questionnaire inference.

## Local verification

Install and exercise the actual FastAPI → RAG → Qdrant path:

```sh
.venv/bin/python -m pip install -e '.[rag,backend]'
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/backend_smoke.py
PYTHONPATH=src .venv/bin/python -m pytest tests/unit -q
```

After configuring `.env`, the following performs one real provider request with a fixed, non-user research fixture and prints no response content or secrets:

```sh
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/conversation_smoke.py
```

Set `LLM_PROVIDER` to `openai`, `anthropic`, or `gemini`, put the provider's exact model ID in `LLM_MODEL`, and paste its token into `LLM_API_KEY` in the root `.env`. Do not add the token to `frontend/`, a `VITE_` variable, source code, commands, logs, or screenshots. Only the selected provider's official SDK receives the key, inside the backend process.

To run a local development server, supply a random secret with at least 32 bytes and an explicit browser origin. Do not commit either value:

```sh
SESSION_SIGNING_KEY='<random-secret-at-least-32-bytes>' \
ALLOWED_ORIGINS='http://localhost:5173' \
HF_HUB_OFFLINE=1 \
PYTHONPATH=src \
.venv/bin/uvicorn clinical_risk_agent.backend.app:app_factory --factory --host 127.0.0.1 --port 8000 --no-access-log
```

## Modal preparation

[`deployment/modal_app.py`](../deployment/modal_app.py) uses the current `modal.asgi_app` path, CPU-only execution, `region="ap-south"`, `routing_region="ap-south"`, `min_containers=0`, one container, 50 concurrent ASGI inputs, a 60-second function timeout and a short scale-down window. It bakes only source code, the two pinned encoders, the Qdrant corpus, active manifest, claim catalog and model pin into the image. The Qdrant lock file is excluded. Modal documents ASGI web functions, regional routing and autoscaling at:

- https://modal.com/docs/guide/webhooks
- https://modal.com/docs/guide/region-selection
- https://modal.com/docs/guide/scale

Before deploying, create the `clinical-risk-agent-secrets` Modal secret with `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`, `SESSION_SIGNING_KEY`, and the exact production `ALLOWED_ORIGINS`. Then perform an ephemeral test before persistent deployment:

```sh
.venv/bin/python -m pip install -e '.[deploy]'
.venv/bin/modal serve deployment/modal_app.py
.venv/bin/modal deploy deployment/modal_app.py
```

Deployment is intentionally a manual owner action because it creates a public URL and consumes cloud credits. Before doing it, configure the Modal workspace spend limit to `$0` out of pocket and its usage budget no higher than available credits. Verify the provider's current payload handling and India-routing behavior. The application-level daily ceiling is process-local and resets on container restart; enforce the true global credit/budget ceiling at the Modal workspace until a privacy-approved shared counter exists.

## Release blockers and next integration

- Reverify all active source retraction metadata immediately before deployment. Readiness correctly fails once any check is older than 14 days.
- Add the Framer research-question component using only in-memory bearer state; never use browser storage or URLs for the token.
- Run a deployed cold/warm latency and concurrent-load check. The local smoke is functional evidence, not a cloud SLO.
- The deterministic safety/language/intent ports are demo scaffolding, not the evaluated release artifacts. Replace them with pinned, calibrated local artifacts and run the frozen safety/intent release suites before describing the chat route as production-ready.
- The current trusted claim router recognizes only the five reviewed questions. Expand it only with reviewed claim mappings and gold judgments; do not let the LLM assign claim IDs.
- Add validated SSE delivery; the present public chat route returns one validated JSON envelope and never streams raw model tokens.
- Questionnaire submission remains blocked pending the same safety release work and public API integration of the protected assessment graph.
- A single Modal container preserves the memory-only session boundary. Increasing `max_containers` requires approved session affinity; do not add a persistent shared session store.
