# RAG engineer handoff

Status: **ready to hand to the RAG engineer**, verified 2026-09-25. The 21-source corpus, locked provisional labels, retrieval comparison, expanded support-gate diagnostic, local claim-support/recovery checks, and read-only MCP contract evaluation are complete. This means the research baseline is reproducible and its limits are documented; it does **not** mean the RAG engineer's product-integration or release work is complete. There is no user-facing RAG endpoint or approved runtime claim gate.

## What is handed over

| Component | Current state | Evidence or entry point |
| --- | --- | --- |
| Corpus | 21 approved PubMed abstracts in one local embedded Qdrant store; 21 document points and 39 hierarchical passages | [Source manifest](RAG_DIRECT_21_SOURCE_RESEARCH_MANIFEST.json), `data/indexes/rag_corpus_manifest.json`, `scripts/rag_ingest.py` |
| Encoders | Offline pinned MedCPT query/article models | [Encoder pin](RAG_MEDCPT_ENCODER_PIN.json) |
| Retrieval | Hierarchical MedCPT dense + BM25, relevance-first RRF, no cross-encoder; document retained as comparator | `src/clinical_risk_agent/rag/retrieval.py`, [implementation decisions](RAG_IMPLEMENTATION_DECISIONS.md) |
| Research labels | 20 cases, 19 with a direct source and one context-only negative; provisional AI-reviewed judgments bound to corpus | [Gold](RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.json), [checksum lock](RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.lock.json) |
| Strategy comparison | Both Recall@5 1.0; document slightly higher nDCG/MRR, hierarchical higher top-passage BERTScore | [21-source report](RAG_GENERAL_ASSOCIATION_21_SOURCE_BENCHMARK_REPORT.md), `scripts/rag_general_benchmark.py` |
| Support-gate diagnostic | The configured `>0.85` route falls back to BM25 for all 24 tested questions and returns related papers for all five unsupported questions; a scalar cosine cutoff cannot separate them while retaining every direct source | [Expanded diagnostic](RAG_RELEVANCE_GATE_21_SOURCE_REPORT.md), `scripts/rag_relevance_gate_calibration.py` |
| Claim support prototype | Optional exact-passage assertion checker filters both primary and fallback candidates; five bounded claims and four mismatched SUD claims passed 36 local route checks | [Catalog](RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json), [integration report](RAG_CLAIM_SUPPORT_INTEGRATION_REPORT.md), `src/clinical_risk_agent/rag/support.py`, `scripts/rag_support_integration.py` |
| Local MCP playground | Five read-only stdio tools over the pinned corpus; exploratory matches are not claim support. The contract evaluation checked all 21 paper lookups, five supported and four unsupported catalog cases, exact search provenance, comparison calls and invalid inputs | [Playground and evaluation instructions](RAG_LOCAL_MCP_PLAYGROUND.md), `scripts/rag_mcp_server.py`, `scripts/rag_mcp_evaluate.py` |

The active corpus manifest SHA-256 is `3a0fb23ca8681f2918ed53cee7235df5e877468bcfa73cf156b4359b8b12c4a6`. The gold SHA-256 is `59b8367b62f040aea6121da26acb02b1e5a14ba3418bf917cc308ecaa2a33a15`. The assertion catalog SHA-256 is `97843a01dd345bedd273883134f4d42867d0d1852db4ededba29fcdf318e201a`. Verify these before using the local results. The historical 16-source corpus and reports remain separate.

The existing runtime cosine setting is strictly greater than `0.85`. The research comparison used `>0.0` to retain diagnostic candidates. Neither the threshold nor a new runtime support policy has AI Architect sign-off. The prototype checker is opt-in; unknown claim IDs or unannotated passages fail closed only when that checker is supplied.

## Reproduce the handoff checks

Run from the repository root with the local `.venv`, pinned model directories, `data/indexes/rag_corpus_manifest.json`, and `data/indexes/qdrant` present. Embedded Qdrant should be opened by one process at a time. The corpus/model and result artifacts under `data/indexes` are git-ignored; copy them with an environment transfer or rebuild from pinned public sources.

```sh
PYTHONPATH=src .venv/bin/python -m pytest tests/unit -q
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_general_benchmark.py --gold agent_docs/RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.json --output data/indexes/rag_general_benchmark_21_source_results.json
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_relevance_gate_calibration.py --spec agent_docs/RAG_RELEVANCE_GATE_21_SOURCE_SPEC.json --output data/indexes/rag_relevance_gate_21_source_results.json
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_support_integration.py
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_mcp_evaluate.py
```

Latest checks on 2026-09-25: 44 unit tests and 12 subtests passed. The 21-source benchmark reproduced document and hierarchical Recall@5 of 1.0 (19 answerable cases); the expanded gate diagnostic reproduced 19/19 direct-source recovery and related-source returns on all five unsupported questions at the configured route; the support integration passed 36/36 primary/fallback checks and returned `retrieval_unavailable` on dual outage. The MCP evaluation passed five-tool discovery, 21/21 exact paper lookups, five positive and four negative curated cases, nine exact-provenance searches, five comparison calls, and four invalid-input rejections. Its warm-call timing is a local diagnostic, not a service-level objective. Exact excerpts and display citations matched indexed passages; Qdrant closed and reopened with the same 39 hierarchical passages. The [integration report](RAG_CLAIM_SUPPORT_INTEGRATION_REPORT.md) records route latency and result checksum.

## Next owner work

1. Define and validate a trusted query-to-claim contract. `RetrievalQuery.claim_id` is internal; a client-provided ID cannot authorize a source. Extend the curated assertion catalog beyond its five claims, and review each claim, source, exact passage, endpoint, exposure, time frame, and bounded use. Preserve the distinction between substance use/experimentation and diagnosed SUD, and between perpetration and victimization.
2. Test passage-level support and abstention on an untouched set with independently reviewed positive, borderline, and negative examples. Include primary and fallback routes, missing catalog entries, model/index drift, and recovery after a source update or retraction. The provisional 20-case gold and four authored probes are engineering fixtures, not release validation.
3. Prepare a concrete runtime gate proposal with measured recall/abstention tradeoffs and get AI Architect approval recorded in [RAG decisions](RAG_IMPLEMENTATION_DECISIONS.md) before activation. Keep the selected hierarchical configuration while evaluating it; the current `>0.85` setting has no approved replacement.
4. Build the product integration only after that policy decision: restore/publish automation for Qdrant and same-corpus independent BM25, controlled source updates and retraction scrub, validated citation/context construction, typed no-evidence/unavailable handling, dependency-failure and cold-start measurements, and end-to-end latency against the product requirement. The research script demonstrates local recovery but is not a deployment runbook. The local MCP server is a developer inspection surface, not the application route or an intent router.

Human evaluation belongs to the evaluation team, not to the product owner as a manual annotation assignment. A review queue should show the question, publication, exact passage, proposed grade, and accept/change controls. Use a distinct held-out set for agreement and release claims. The [blinded packet](RAG_GOLD_21_SOURCE_BLINDED_PACKET.json) and [worksheet](RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_REVIEW_WORKSHEET.json) are optional material for that later work.

[Local MCP instructions](RAG_LOCAL_MCP_PLAYGROUND.md) cover hands-on inspection and the reproducible contract evaluation. Its arbitrary-query search results are explicitly unverified candidates. The five-claim assertion catalog and absent trusted query-to-claim interface still limit user-facing product integration. Jev remains optional; it is not a handoff prerequisite.
