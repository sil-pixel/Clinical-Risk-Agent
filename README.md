# Bodhica

Research-only prototype combining a protected DCMFNet assessment adapter and a bounded scientific RAG corpus. It is not a diagnosis, medical advice, or an emergency service.

The local app supports conversation, corpus-backed research answers, an optional questionnaire, and an evaluation dashboard through signed, memory-only sessions. Install and verify it locally:

```sh
.venv/bin/python -m pip install -e '.[rag,backend]'
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/backend_smoke.py
```

See [the backend/deployment handoff](agent_docs/BACKEND_DEPLOYMENT_HANDOFF.md) for the API, local server command, Modal preparation and current release boundaries.

For local conversational-generation configuration, select `openai`, `anthropic`, or `gemini` with `LLM_PROVIDER`, set that provider's exact model ID in `LLM_MODEL`, and put its key in `LLM_API_KEY` in the git-ignored root `.env`. Set `LLM_JUDGE_MODEL` to a separate model from the same provider for live evaluation. The key is backend-only and must never be placed in `frontend/` or a `VITE_` variable. `.env.example` documents the contract. The intended UI is chat-first, with the questionnaire available as an optional left-side assessment workflow. The Evaluations tab includes the [100-response human judge-review workflow](agent_docs/LLM_JUDGE_CALIBRATION.md).

`POST /v1/messages` accepts `{"kind":"free_text","text":"..."}` under an authenticated ephemeral session. Research questions use the local appraised corpus. Broad educational questions can fall back to clearly labeled general knowledge. Safety and assessment routing still run before generation. After configuring `.env`, run `PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/conversation_smoke.py` to make one live-provider request using a non-user curated fixture.

For the local browser experience, run the API and Vite UI in separate terminals:

```sh
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/uvicorn clinical_risk_agent.backend.app:app_factory --factory --host 127.0.0.1 --port 8000 --no-access-log
cd frontend && npm run dev -- --host localhost --port 5173
```

Open `http://localhost:5173`. Chat uses validated SSE events from `POST /v1/messages:stream`; the optional questionnaire uses `GET /v1/assessments/questionnaire` and `POST /v1/assessments` with memory-only session authorization.

Assessment scores return before LLM explanation generation. The browser polls the session's cached result and can retry the explanation without repeating inference. Models preload during backend startup.

Open **Evaluations**, or `http://localhost:5173/?view=evaluation`, for background live-chat groundedness/correctness estimates, individual score records, and aggregate latency/error monitoring. Archived benchmark scores are not displayed; live ML accuracy requires observed outcome labels. See [evaluation monitoring](agent_docs/BODHICA_EVALUATION_MONITOR.md) for score provenance and offline evaluation commands.
