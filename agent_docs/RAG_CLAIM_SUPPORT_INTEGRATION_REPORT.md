# Claim support integration and recovery checks

Run 2026-09-25 against the pinned 21-source local Qdrant corpus. The hierarchical retriever now accepts a `SupportChecker` and applies it to fused primary candidates and independent BM25 fallback candidates before source selection and citation creation. The research implementation uses [curated assertions](RAG_21_SOURCE_CLAIM_SUPPORT_CATALOG.json): each claim ID is bound to a publication, exact indexed passage and verified text anchor. Unknown claims and unannotated passages yield no supported evidence. The existing cosine routing threshold is unchanged.

The catalog currently covers five bounded claims: childhood ADHD and later abuse/dependence; MTA ADHD and later use frequency; peer victimization and later use; cybervictimization and later experimentation; and bullying perpetration and early smoking/drinking. It deliberately has no assertion for diagnosed SUD in the latter four study-specific settings. The perpetration assertion relies on the recorded full-text measurement appraisal, while its citation still displays the exact indexed abstract passage. Assertion IDs and their bounded meanings are trusted internal inputs; no user-query-to-claim router or public endpoint is wired yet. A caller must not accept a client-supplied claim ID as authority.

## Local check results

| Retrieval route | Direct claims returned | Mismatched SUD claims abstained |
| --- | ---: | ---: |
| Primary hybrid, diagnostic cosine `>0.0` | 5/5 | 4/4 |
| Configured cosine `>0.85` with independent BM25 fallback | 5/5 | 4/4 |
| Injected dense outage with BM25 fallback | 5/5 | 4/4 |
| Injected primary sparse outage with BM25 fallback | 5/5 | 4/4 |

Across 36 retrieval checks, citation IDs were contiguous, source IDs unique, cap respected, and each returned excerpt matched the indexed passage and display record exactly. A dual dense/independent-BM25 outage returned `retrieval_unavailable` with no citations. Closing and reopening embedded Qdrant restored the same 39-passage hierarchical collection. Rebuilding independent BM25 from the same snapshot succeeded.

The recovery checks found and fixed a status error: when primary search was unavailable but BM25 completed with zero supported passages, the retriever previously returned `retrieval_unavailable`. It now returns `no_eligible_evidence` with `primary_status=unavailable` and `fallback_status=zero_match`. A true dual outage remains unavailable.

Observed per-query retrieval latency in this local warm run: median 36.64 ms, p95 51.75 ms across 36 checks. Model loading, app startup, and network deployment are outside these timings. This is one-machine engineering data, not a 60-second end-to-end product result.

## Reproduction and scope

Run `PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_support_integration.py`. The [raw result](../data/indexes/rag_support_integration_results.json) is git-ignored, SHA-256 `865cc654c4de6d9793cebca25e4e2399be86a91a1ba5a9df0a278d450a755300`. Catalog SHA-256 `97843a01dd345bedd273883134f4d42867d0d1852db4ededba29fcdf318e201a`; corpus SHA-256 `3a0fb23ca8681f2918ed53cee7235df5e877468bcfa73cf156b4359b8b12c4a6`. The script verifies the corpus, encoder hashes, collection count and assertion anchors before testing. Local Qdrant, corpus and pinned model artifacts must accompany an environment transfer or be rebuilt.

`PYTHONPATH=src .venv/bin/python -m pytest tests/unit -q` passed 44 tests and 12 subtests. Unit checks include primary/fallback parity, rejection of unknown claims, invalid anchor/catalog-version rejection, and the corrected no-evidence versus unavailable statuses.

This is a bounded research integration, not a runtime policy approval. The catalog does not yet cover every topic in the 21-source corpus; unknown claims fail closed, so its recall across the general 20-case gold set has not been established. It relies on trusted typed claim IDs and curated source/passage assertions, not automated verification of arbitrary free-text claims. Before user-facing integration, extend and independently review the catalog, validate the query-to-claim contract and passage-level support on a held-out set, then obtain the AI Architect gate-policy sign-off in [RAG decisions](RAG_IMPLEMENTATION_DECISIONS.md). No human clinical approval is implied.
