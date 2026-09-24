# Expanded-corpus retrieval diagnostic — 2026-09-24

Status: **provisional source-level diagnostic, not a dual-adjudicated or release benchmark**.

The [pre-run locked qrels](RAG_BENCHMARK_16_SOURCE_QRELS.json) contain 19 synthetic/researcher-authored queries: one answerable source-level query for each of the 16 indexed PMIDs and three no-evidence probes. The qrels file records SHA-256 hashes of the corpus manifest, source-approval manifest, and prior draft. It was written before either retrieval variant ran. It reuses eight corpus-matched answerable queries from the prior draft and adds eight source-specific context/direct questions; the three no-evidence probes are retained. Labels have not been blindly dual-reviewed and exact passage/chunk judgments are not frozen.

Both strategies searched the **same 16 PubMed abstracts** in the same local Qdrant database, with pinned MedCPT query/article encoders and independent BM25 fallback. The document collection has 16 points; the hierarchical collection has 30. No cross-encoder reranker was pinned. The configured run used strict dense cosine `>0.85`; a predeclared diagnostic ablation used `>0.0` without changing the product policy. All metrics below use only the 16 answerable cases except no-evidence recall, which uses the three probes. A single positive source per answerable query makes Recall@5 equal to Hit@5.

| Run | Strategy | Hit@1 | Recall@5 | Recall@10 | MRR@10 | nDCG@10 | Dense-admitted cases | Keyword-fallback cases | No-evidence recall | Median retrieve latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Configured `>0.85` | Document | 1/16 | 5/16 | 11/16 | 0.192 | 0.305 | 0/19 | 19/19 | 0/3 | 32.15 ms |
| Configured `>0.85` | Hierarchical | 2/16 | 7/16 | 12/16 | 0.251 | 0.366 | 0/19 | 19/19 | 0/3 | 32.39 ms |
| Ablation `>0.0` | Document | 1/16 | 5/16 | 10/16 | 0.185 | 0.285 | 19/19 | 0/19 | 0/3 | 32.86 ms |
| Ablation `>0.0` | Hierarchical | 2/16 | 7/16 | 13/16 | 0.257 | 0.383 | 19/19 | 0/19 | 0/3 | 33.68 ms |

Hierarchical placed the target source at a better rank in 13 of 16 answerable cases under each setting; three tied, and none favored document. This is a paired observation in a small, assistant-labeled corpus, not proof of general superiority. The configured result is specifically a **lexical fallback comparison**, not an effective hybrid/semantic-reranking comparison: no dense similarity cleared the strict `0.85` threshold. The diagnostic ablation admits dense candidates but has no calibrated relevance gate and is not an approved replacement.

All three no-evidence probes returned some evidence rather than `no_eligible_evidence`; no-evidence precision is undefined because neither strategy predicted the empty class. Topical retrieval alone did not recognize that a source cannot answer an individualized dosing, autism-risk, or single-incident causal question. The configured ranker also sorts by evidence tier and publication recency ahead of fused relevance, which may contribute to low first-rank accuracy for older narrative/context papers; that mechanism is an inference from [`HybridRetriever._select`](../src/clinical_risk_agent/rag/retrieval.py), not a causal ablation result.

The run artifact with per-case ranks, top-five PMIDs, statuses, and latency is `data/indexes/rag_benchmark_16_source_results.json` (local generated data). The exact collection names, model hashes and corpus provenance are in `data/indexes/rag_corpus_manifest.json`. Reproduce the diagnostic from the project root with `.venv/bin/python scripts/rag_benchmark.py`; the runner refuses to run if a locked input hash or collection point count changes.

Before a release-quality comparison: blind dual-adjudicate source and passage labels, cover the missing ADHD/ASD and other intended topics, calibrate the dense and no-evidence relevance gates on a separate development split, pin a cross-encoder reranker, and rerun both strategies on an untouched test split. Do not tune a threshold on these 19 reported cases and then call this same set an independent evaluation.
