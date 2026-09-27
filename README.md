# Clinical-Risk-Agent

Research-only prototype combining a protected DCMFNet assessment adapter and a bounded scientific RAG corpus. It is not a diagnosis, medical advice, or an emergency service.

The current runnable HTTP slice exposes five reviewed research questions through signed, memory-only sessions. Install and verify it locally:

```sh
.venv/bin/python -m pip install -e '.[rag,backend]'
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/backend_smoke.py
```

See [the backend/deployment handoff](agent_docs/BACKEND_DEPLOYMENT_HANDOFF.md) for the API, local server command, Modal preparation and current release boundaries.

For local conversational-generation configuration, select `openai`, `anthropic`, or `gemini` with `LLM_PROVIDER`, set that provider's exact model ID in `LLM_MODEL`, and put its key in `LLM_API_KEY` in the git-ignored root `.env`. The key is backend-only and must never be placed in `frontend/` or a `VITE_` variable. `.env.example` documents the contract. The intended UI is chat-first, with the questionnaire available as an optional left-side assessment workflow.

`POST /v1/messages` now provides the bounded conversational path. It accepts `{"kind":"free_text","text":"..."}` under an authenticated ephemeral session. Only the five claim-verified research questions can produce generated scientific answers; broader questions abstain, and safety/refusal/assessment routes use fixed local content without invoking the LLM. After configuring `.env`, run `PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/conversation_smoke.py` to make one live-provider request using a non-user curated fixture.
