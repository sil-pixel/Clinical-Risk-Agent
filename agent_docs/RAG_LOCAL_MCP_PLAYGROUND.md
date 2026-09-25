# Local RAG MCP playground

This is a read-only stdio MCP server over the pinned 21-PubMed-source research corpus. It uses the existing embedded Qdrant collections and local MedCPT models; it makes no live literature requests and does not create a network listener. Use public or synthetic research questions, not patient data.

## Start in MCP Inspector

From the repository root, with Node 22.19+ and the project `.venv` available:

```sh
.venv/bin/python -m pip install -e '.[rag,mcp]'
npx --yes @modelcontextprotocol/inspector .venv/bin/python scripts/rag_mcp_server.py
```

Open the local URL printed by Inspector, connect using stdio, and choose the Tools tab. The server waits for a client on stdin when run directly, so a bare `python scripts/rag_mcp_server.py` does not show a prompt or web page. Stop Inspector with Ctrl-C. Embedded Qdrant permits one process to own its local store at a time; close another local benchmark or Inspector session before starting this one.

The five tools are:

| Tool | Try this | What it returns |
| --- | --- | --- |
| `search_evidence` | `question`: “Is childhood ADHD associated with later substance abuse or dependence?”, `limit`: `3` | Hierarchical passages with PMID, exact excerpt and bounded use. `support_status` is `not_evaluated_for_the_question`. |
| `get_paper` | `pmid`: `21382538` | Indexed citation, exact abstract, passage IDs and bounded-use appraisal. |
| `compare_retrieval` | Same question, `limit`: `3` | Side-by-side document and hierarchical matches for that question. These are live retrieval results, not a scored benchmark. |
| `list_curated_claims` | No arguments | Five available bounded claim IDs. |
| `get_curated_claim` | `claim_id`: `childhood_adhd_later_abuse_dependence` | The catalogued source, anchored exact passage and bounded use for that ID. Unknown IDs return `no_curated_assertion`. |

Try `get_curated_claim` with `cybervictimization_later_diagnosed_sud`: it returns no curated passage. A `search_evidence` call about that topic may still return *related* papers about experimentation. Treat its matches as candidates to inspect, not proof of the asked disorder claim. The server provides neither answer generation nor clinical advice.

For a quick protocol check without opening the graphical Inspector:

```sh
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_mcp_smoke.py --stdio
```

The smoke script launches the actual stdio server, lists its tools, calls all five, checks structured results, and exits. The SDK dependency is optional under `.[mcp]`; local testing used official Python MCP SDK 2.2.0. The [official SDK running guide](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/index.md) describes stdio, and the [Inspector guide](https://github.com/modelcontextprotocol/docs/blob/main/docs/tools/inspector.mdx) documents the interactive client.

## Current boundaries

The server verifies the corpus manifest against the curated catalog, pinned encoder weights, source identities, eligibility, exact assertion anchors and Qdrant collection sizes before serving a tool call. It does not accept file paths, collection names or URLs from MCP callers. Results are read-only; raw questions are processed in memory and are not written by the server.

Exploratory search uses hierarchical relevance-first RRF with a diagnostic dense cosine `>0.0` so you can compare matches. It does not run the optional claim checker for arbitrary question text. The curated-claim catalog covers five appraised associations only. The current configured `>0.85` route and broader user-facing gate policy are unchanged; a trusted query-to-claim mapper, wider catalog review, held-out passage evaluation and AI Architect sign-off remain necessary before product integration. This local playground is not that product integration.
