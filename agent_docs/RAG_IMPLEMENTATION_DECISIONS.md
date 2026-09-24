# RAG Implementation Decisions

Status: Product-owner-approved baseline on 2026-09-24; model revisions, thresholds, and public release require measured evidence.

Owner: RAG Engineer. Source architecture: [`APPROVED_AI_ARCHITECTURE.md`](APPROVED_AI_ARCHITECTURE.md) and [`AI_MODEL_BENCHMARK_REPORT.md`](AI_MODEL_BENCHMARK_REPORT.md).

## Retrieval strategies to compare

Use the same eligible source set, query judgments, dense encoder, lexical tokenizer, fusion constant, cross-encoder, source cap, and latency environment for both strategies.

| Strategy | Indexed unit | Citation and generation unit |
| --- | --- | --- |
| `document` | Whole title-plus-abstract or one licensed full-text section | Exact matched document/section text, bounded for context |
| `hierarchical` | Sentence-bounded child passage within an abstract or licensed section | Exact matched child passage, with bounded neighboring parent context |

The hierarchical strategy is the implementation baseline; document-level is the controlled comparator. An abstract shorter than the target child size remains one child. No chunk crosses publication identity or a licensed section boundary. Stable document, parent, and child IDs preserve citation identity. Chunk sizes are measured with the selected embedding tokenizer at indexing time: abstract children target 220–300 tokens with one-sentence overlap; full-text children target 300 tokens with no more than 50-token overlap. A tokenizer-independent approximation is permitted only in deterministic local fixtures, not in a benchmark claim.

MedCPT's article encoder is trained and documented with title-plus-abstract input. Title-plus-child embedding is therefore a benchmark hypothesis, not an assumed quality improvement. Compare the two retrieval strategies with relevance labels before pinning the representation.

## Common retrieval path

1. Apply topic, publication date, source class, DOI/PMID, license, quality, metadata isolation, and current retraction checks before indexing and again before returning evidence. PubMed abstracts are the default. Full text requires an explicit machine-readable license permitting storage and display.
2. Search the eligible scientific corpus with MedCPT dense and BM25 lexical retrieval, taking 40 candidates from each. Fuse ranks with RRF `k=60` and retain 30 candidates. Pin a Qdrant version supporting explicit RRF `k`; do not use its default value.
3. Rerank at most 20 query–candidate pairs with the MedCPT cross-encoder candidate. Compare against no reranker and a small general cross-encoder before selecting a release artifact.
4. Reject candidates below the pinned embedding-specific semantic gate. Apply evidence hierarchy, recency, and quality only to already relevant eligible candidates. Collapse to at most five distinct publications, preserving conflict positions when supported.
5. Return exact matched text and source-owned citation metadata. The LLM may cite only returned source IDs; it may not generate metadata or change excerpt text.
6. If the primary vector path fails or returns no eligible match, run one search against an independently available, same-corpus BM25 index. Keep fallback provenance and the same eligibility gates. Distinguish no eligible evidence from retrieval unavailable.

The initial `>0.85` dense cosine threshold is a release hypothesis. It must be evaluated against relevant, borderline, and irrelevant labels; a threshold change requires AI Architect approval. The two strategies are also compared under dense-only, BM25-only, hybrid, and hybrid-plus-reranker ablations.

## Evaluation and provenance

Freeze a non-user query set with source-level and passage-level relevance judgments, no-evidence cases, and conflicting-evidence cases. Report Recall@5/10/20, Precision@5, MRR@10, nDCG@10, no-evidence precision/recall, conflict coverage, fallback recovery, index size, peak memory, and cold/warm latency. A reranker must improve nDCG@10 or Precision@5 by at least 5% relative without violating the 60-second end-to-end gate. Publish source identities, licenses, model revisions/checksums, corpus/index versions, appraisal rubric, and retraction-check version in the benchmark manifest; do not include runtime user queries or results.

Incremental ingestion and complete active DOI/PMID retraction scrubbing run every two weeks. A retraction check older than 14 days makes a source ineligible. A newly retracted or deprecated source is removed from both active vector and lexical indexes and from any current context window, with a non-retrievable audit tombstone.

## Implementation order

1. Canonical typed retrieval contracts and deterministic eligibility/chunking logic.
2. Versioned public-corpus ingestion and independent BM25 index, with tests for license, quality, recency, retraction, and citation provenance.
3. Qdrant dense/sparse adapter and locally hosted embedding/reranking adapters, pinned by revision and checksum.
4. Same-corpus document-versus-hierarchical benchmark and quality/latency report.
5. Live PubMed escalation, fortnightly update/scrub automation, and downstream handoff.

No exact model or retrieval strategy is represented as empirically superior until the frozen benchmark is run.

## Implementation checkpoint (2026-09-24)

The repository now contains typed retrieval contracts, strict scientific-source eligibility, document and hierarchical chunking, a versioned in-memory corpus snapshot, independent BM25, a Qdrant dense/sparse adapter with mandatory isolation filters, RRF-60 fusion, bounded reranking, exact-text citation records, lexical fallback, and a same-case strategy comparison harness. Local-only MedCPT query/article and cross-encoder adapters require SHA-256-verified safetensors artifacts. PubMed EFetch ingestion accepts only explicitly approved PMIDs and quality appraisals. These paths have synthetic unit and local-Qdrant tests; they are engineering coverage, not a clinical or retrieval-quality result.

Conflict status requires a pre-appraised stance tied to the request's `claim_id`; absent a matching claim, no conflict is inferred from wording. This protects against falsely treating a publication's position as universal across questions.

**Not yet release evidence:** a topic-curated, licensed, appraised publication set; persisted/reloadable corpus and independent BM25 artifacts; pinned MedCPT and second biomedical embedding revisions/checksums; second reranking configuration; frozen source- and passage-level judgments; actual document-versus-hierarchical and ablation results; calibrated relevance gates; cold/warm resource results; licensed full-text/BioC path; bounded live PubMed escalation; automated fortnightly ingest/retraction scrub and audit tombstones; downstream workflow integration. The Qdrant adapter has been tested with local Qdrant only, not a deployed service. Public RAG claims and release remain gated on these items and architecture review of any threshold change.
