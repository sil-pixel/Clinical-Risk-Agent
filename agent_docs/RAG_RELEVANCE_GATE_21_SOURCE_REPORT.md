# Expanded hierarchical support-gate diagnostic

Run 2026-09-25 on the 21-source Qdrant corpus. Hierarchical retrieval with relevance-first RRF remains the selected research strategy. This diagnostic evaluates whether the current routing gate and a simulated passage cutoff distinguish papers that directly answer a question from related papers with different exposures or outcomes.

## Observed behavior

The [pre-run spec](RAG_RELEVANCE_GATE_21_SOURCE_SPEC.json) binds the [locked 20-case research labels](RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.json) and corpus hashes, and declares four additional exploratory no-direct-evidence probes. These probes target cybervictimization, peer victimization, perpetration and the MTA ADHD cohort where retrieved papers discuss use or experimentation, but not a diagnosed SUD for the specified exposure and time frame. They are analyst-authored checks, not independently reviewed gold.

| Route at configured cosine `>0.85` | Direct source in top five | Unsupported questions returning papers | No-evidence outcomes |
| --- | ---: | ---: | ---: |
| Normal retrieval | 19/19 answerable gold | 1/1 gold + 4/4 probes | 0/24 |
| Forced dense outage, independent BM25 fallback | 19/19 answerable gold | 1/1 gold + 4/4 probes | 0/24 |

All 24 normal queries took keyword fallback because no dense hit passed `>0.85`. The forced-outage run confirmed that the independent BM25 route likewise returns related sources for every unsupported question. Both routes label those returns `sufficient_evidence`; that status currently reflects source presence, not claim-specific support. The fallback protects recall, but it does not solve abstention.

An offline simulation retained only top-five passages whose own MedCPT dense cosine exceeded each predeclared cutoff. It did not refill from lower ranks or reproduce the fallback path. Counts below separate the locked gold from the four exploratory probes:

| Simulated cosine cutoff (`>`) | Direct source retained, gold | Gold negative abstained | Probes abstained |
| ---: | ---: | ---: | ---: |
| 0.60 | 19/19 | 0/1 | 1/4 |
| 0.65 | 12/19 | 0/1 | 3/4 |
| 0.70 | 5/19 | 1/1 | 3/4 |
| 0.75 | 2/19 | 1/1 | 4/4 |
| 0.80–0.90 | 0/19 | 1/1 | 4/4 |

The locked negative's strongest selected passage scores 0.673. The MTA-specific SUD probe reaches 0.718, while directly answering sources for BULLY-01 and BULLY-DIRECT-02 score 0.602 and 0.613. A single cosine cutoff cannot retain all direct sources and abstain on these endpoint mismatches. Some positive cases have a high-scoring contextual passage, so accepting a query based only on its maximum score would further obscure the difference.

## Decision and next engineering work

Retain the existing runtime `>0.85` routing threshold and hierarchical baseline. This run supplies no defensible replacement scalar threshold and does not approve a new evidence gate. The next gate design must check the question's exposure, outcome, time frame and study design against the cited passage, and apply that check after both primary and fallback retrieval. It needs a typed `no_eligible_evidence` result when retrieved papers are only contextual. Test that design with passage-level labels and a held-out set before proposing a runtime change; AI Architect sign-off must be recorded in [RAG decisions](RAG_IMPLEMENTATION_DECISIONS.md).

Next in the RAG engineer workflow: integration and recovery checks for restoring the pinned 21-source Qdrant and same-corpus BM25 snapshot, exact excerpt and citation handling, bounded-use enforcement, latency, and unavailable-dependency behavior. Once the retrieval interface is stable, remind the user about the deferred local read-only MCP playground before interactive integration.

## Reproducibility and limits

- Spec SHA-256: `ff5eac456dfc922b630d2a1271cc3d688bac4f48130139f87cef41a69e493ae7`.
- Gold SHA-256: `59b8367b62f040aea6121da26acb02b1e5a14ba3418bf917cc308ecaa2a33a15`; corpus SHA-256: `3a0fb23ca8681f2918ed53cee7235df5e877468bcfa73cf156b4359b8b12c4a6`.
- [Raw case results](../data/indexes/rag_relevance_gate_21_source_results.json) SHA-256: `caac0d78513007e98a61cb26ba08507b0009ca7e6ff8b0a20a032446d728138f`. Local `data/indexes` artifacts are git-ignored and must be copied with the pinned corpus/models for reproduction elsewhere.
- Run: `PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_relevance_gate_calibration.py --spec agent_docs/RAG_RELEVANCE_GATE_21_SOURCE_SPEC.json --output data/indexes/rag_relevance_gate_21_source_results.json`.

The gold cases were previously used in retrieval comparisons. The four probes were authored for this diagnostic. Judgments are source-level and provisional; this run cannot validate passage support, generated answer quality, generalization or a clinical release rule. The forced outage covers only the dense search failure mode, not all backend failures.
