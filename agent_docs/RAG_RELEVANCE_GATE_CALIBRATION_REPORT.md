# Hierarchical relevance-gate calibration diagnostic

Status: **no threshold approved; runtime unchanged**. Exploratory analysis run 2026-09-24 on the frozen 16-source PubMed-abstract corpus and 13 general-association questions (11 with a directly answering source, two with no direct source in this corpus). The judgments are assistant-authored and already used for retrieval strategy selection, so this is neither an independent calibration set nor release validation.

The selected research ranking was fixed: hierarchical passages, MedCPT dense + BM25 lexical candidates fused with RRF-60, relevance-first ordering, no cross-encoder, and a five-source cap. The [pre-run calibration specification](RAG_RELEVANCE_GATE_CALIBRATION_SPEC.json), SHA-256 `5440c22a76cfb9c8b53bc8b950a12aca017a824c80b4e66e1465595f96145129`, declares a **simulated post-retrieval passage gate**: retain each of the original top-five passages only if its own dense cosine is strictly greater than the swept cutoff; classify no adequate *local* evidence if none remain. This is distinct from the current `HybridRetriever` cosine threshold, which routes to independent BM25 when no dense hit passes.

| Dense cosine cutoff (`>`) | Direct source retained, answerable | No-direct-evidence probes abstained |
| ---: | ---: | ---: |
| 0.00–0.60 | 11/11 | 0/2 |
| 0.65 | 5/11 | 2/2 |
| 0.70 | 2/11 | 2/2 |
| 0.75 | 1/11 | 2/2 |
| 0.80–0.90 | 0/11 | 2/2 |

The best selected-passage cosine for the two no-direct-evidence questions was **0.631** (ADHD–substance-use) and **0.606** (bullying–substance-use). Directly answering passages for two answerable questions scored **0.602** and **0.621**, respectively. Their distributions overlap: no single cosine cutoff can both retain all 11 direct sources and abstain on both no-direct-evidence probes in this set. The exact predeclared sweep and per-question scores are in the ignored local `data/indexes/rag_relevance_gate_calibration.json` result.

At the currently configured `>0.85` *routing* threshold, all **13/13** queries took keyword fallback and **0/2** no-direct-evidence probes received a no-evidence status. Simply raising or lowering that routing number cannot be treated as an abstention policy: fallback can return a topically related but non-answering source. A true evidence gate must separately assess whether a returned source directly supports the particular question, apply equally to the primary and fallback paths, and permit an explicit no-adequate-evidence result without fabricating citations.

Decision: **retain `>0.85` and do not deploy the simulated gate**. The selected relevance-first RRF strategy remains a research configuration, while the configured runtime may still use BM25 fallback. Before proposing a new threshold or rule, expand the corpus with directly relevant ADHD and bullying–substance-use studies where eligible, obtain independent source- and passage-level judgments with more no-evidence and borderline queries, and evaluate a claim-specific support gate on an untouched holdout with primary/fallback parity. Any actual threshold or evidence-gate policy change requires explicit AI Architect sign-off recorded in [`RAG_IMPLEMENTATION_DECISIONS.md`](RAG_IMPLEMENTATION_DECISIONS.md). No such sign-off is recorded here.

Reproduce with `HF_HUB_OFFLINE=1 PYTHONPATH=src .venv/bin/python scripts/rag_relevance_gate_calibration.py`. The script verifies frozen gold and corpus hashes, the indexed Qdrant collection, and pinned MedCPT encoder weights. The post-retrieval simulation does not refill from lower ranks, and it does not model safe lexical-only fallback recovery; do not treat its 2/2 negative result as a validated abstention sensitivity estimate.
