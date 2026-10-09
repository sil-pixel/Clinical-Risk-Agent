"""Modal ASGI deployment adapter for the bounded research API.

Deploy only after creating the named secret with LLM_PROVIDER, LLM_MODEL,
LLM_API_KEY, SESSION_SIGNING_KEY and ALLOWED_ORIGINS. This file does not deploy
anything when imported locally.
"""

from __future__ import annotations

from pathlib import Path

import modal

LOCAL_ROOT = Path(__file__).resolve().parents[1]
REMOTE_ROOT = "/opt/clinical-risk-agent"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_pyproject(
        str(LOCAL_ROOT / "pyproject.toml"), optional_dependencies=["rag", "backend"],
    )
    .add_local_dir(str(LOCAL_ROOT / "src"), f"{REMOTE_ROOT}/src", copy=True)
    # Both DCMFNet checkpoints load during startup; without them the lifespan fails.
    .add_local_dir(
        str(LOCAL_ROOT / "model_artifacts"), f"{REMOTE_ROOT}/model_artifacts", copy=True,
    )
    .add_local_file(
        str(LOCAL_ROOT / "data/monitoring/drift_reference.json"),
        f"{REMOTE_ROOT}/data/monitoring/drift_reference.json", copy=True,
    )
    .add_local_file(
        str(LOCAL_ROOT / "data/monitoring/score_reference.json"),
        f"{REMOTE_ROOT}/data/monitoring/score_reference.json", copy=True,
    )
    .add_local_dir(
        str(LOCAL_ROOT / "data/indexes/models"), f"{REMOTE_ROOT}/data/indexes/models",
        copy=True,
    )
    .add_local_dir(
        str(LOCAL_ROOT / "data/indexes/qdrant"), f"{REMOTE_ROOT}/data/indexes/qdrant",
        copy=True, ignore=[".lock"],
    )
    .add_local_file(
        str(LOCAL_ROOT / "data/indexes/rag_corpus_manifest.json"),
        f"{REMOTE_ROOT}/data/indexes/rag_corpus_manifest.json", copy=True,
    )
    .add_local_file(
        str(LOCAL_ROOT / "agent_docs/RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json"),
        f"{REMOTE_ROOT}/agent_docs/RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json", copy=True,
    )
    .add_local_file(
        str(LOCAL_ROOT / "agent_docs/RAG_MEDCPT_ENCODER_PIN.json"),
        f"{REMOTE_ROOT}/agent_docs/RAG_MEDCPT_ENCODER_PIN.json", copy=True,
    )
    .add_local_file(
        str(LOCAL_ROOT / "agent_docs/PROMPT_GUARD_PIN.json"),
        f"{REMOTE_ROOT}/agent_docs/PROMPT_GUARD_PIN.json", copy=True,
    )
    .add_local_file(
        str(LOCAL_ROOT / "agent_docs/INTENT_ROUTER_UTTERANCES.json"),
        f"{REMOTE_ROOT}/agent_docs/INTENT_ROUTER_UTTERANCES.json", copy=True,
    )
    .add_local_file(
        str(LOCAL_ROOT / "agent_docs/INTENT_ROUTER_CALIBRATION.json"),
        f"{REMOTE_ROOT}/agent_docs/INTENT_ROUTER_CALIBRATION.json", copy=True,
    )
    .env({"PYTHONPATH": f"{REMOTE_ROOT}/src", "HF_HUB_OFFLINE": "1"})
)

app = modal.App("clinical-risk-research-api")
runtime_secret = modal.Secret.from_name("clinical-risk-agent-secrets")


@app.function(
    image=image,
    secrets=[runtime_secret],
    region="ap-south",
    routing_region="ap-south",
    cpu=4.0,
    memory=8192,
    min_containers=0,
    max_containers=1,
    scaledown_window=60,
    timeout=60,
)
@modal.concurrent(max_inputs=50)
@modal.asgi_app()
def web():
    """Construct the configured Bodhica ASGI application inside the Modal container."""
    from clinical_risk_agent.backend import BackendSettings, create_app

    return create_app(BackendSettings.from_env(root=Path(REMOTE_ROOT)))
