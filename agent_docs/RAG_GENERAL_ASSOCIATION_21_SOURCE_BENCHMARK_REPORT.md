# Expanded 21-source retrieval benchmark

Completed 2026-09-25. Research only; provisional AI-reviewed labels, not human-adjudicated or clinical/release validation.

## Result

Macro averages over 19 answerable cases; one context-only negative is reported separately. All metrics use distinct publications, except BERTScore, which compares the top passage against the frozen reference answer.

| Metric | Document | Hierarchical |
| --- | ---: | ---: |
| Precision@5 | 0.2211 | 0.2211 |
| Recall@5 | 1.0000 | 1.0000 |
| BERTScore F1, top passage | 0.7597 | 0.7796 |
| nDCG@5 | 0.9590 | 0.9542 |
| MRR@5 | 0.9737 | 0.9474 |

Both strategies recover all 21 direct-source judgments across the 19 answerable questions within their top five. Precision counts only grade-2 sources: because these questions have only one or two direct sources each, 0.2211 is the maximum possible mean Precision@5 under these frozen labels. It is not 22% recall.

Document ranks a direct source first in 18/19 questions; hierarchical does so in 17/19. Both rank a contextual source before the direct source for GEN-06. Hierarchical additionally places contextual perpetration PMID 33224066 ahead of the two direct victimization studies for BULLY-DIRECT-04, which asks whether those studies establish causation of diagnosed SUD. The direct papers rank second and third. This is an exposure/outcome support distinction, not a missing-source problem.

Hierarchical's BERTScore advantage is 0.0199, but this length-sensitive passage/reference similarity does not establish more correct generated answers. Document's nDCG/MRR advantages are small. This run does not establish an overall winner or justify reversing the existing hierarchical baseline; document remains the comparator. No significance or held-out generalization claim is made.

## No-direct-evidence control

NONE-BULLY-SUD has two grade-1 contextual sources and no grade-2 source; it is excluded from all five averages. Both strategies return five papers with `sufficient_evidence`, rather than abstaining, under the diagnostic dense-cosine gate `>0.0`. Hierarchical's first paper is about perpetration, not victimization. Thus neither configuration demonstrates adequate no-evidence behavior in this test. Returning related studies must not imply support for diagnosed SUD or causality. This is a retrieval-status observation, not an evaluated generated clinical answer.

All 20 queries in each strategy used primary hybrid retrieval; no fallback was triggered. This run does not test dependency failures, fallback quality, production latency or the runtime `>0.85` gate. Next: expanded support-gate diagnostics, including endpoint/exposure mismatches and primary/fallback behavior. Any proposed runtime threshold change still requires architecture sign-off in [RAG decisions](RAG_IMPLEMENTATION_DECISIONS.md).

## Frozen inputs and settings

- [Consolidated labels](RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.json) and [pre-run checksum lock](RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.lock.json): SHA-256 `59b8367b62f040aea6121da26acb02b1e5a14ba3418bf917cc308ecaa2a33a15`.
- Corpus manifest SHA-256: `3a0fb23ca8681f2918ed53cee7235df5e877468bcfa73cf156b4359b8b12c4a6`.
- [Raw per-case results](../data/indexes/rag_general_benchmark_21_source_results.json): SHA-256 `9b903797c727a141c22398c3420169502a78952fcb32a096011a24bbffe6f688`. This local artifact is git-ignored; copy it with the corpus/model artifacts for environment transfer.
- Document collection `scientific_document_corpus_d3deb77204142fea`: 21 points. Hierarchical collection `scientific_hierarchical_corpus_45b1823ca05127fd`: 39 passages. Both contain the same 21 PMIDs.
- Same pinned MedCPT encoders, Qdrant BM25/dense hybrid, relevance-first RRF and no cross-encoder for both strategies. Diagnostic cosine `>0.0`; k=5. No runtime threshold change.
- Precision, recall and reciprocal rank count grade 2 only. nDCG uses gain `2^grade - 1`; unlisted PMIDs are grade 0. MRR is truncated at five.
- BERTScore: local DistilBERT, layer 5, no IDF or baseline rescaling; model hashes are recorded in raw results. It measures passage/reference similarity, not answer quality.
- Environment: Python 3.13.7, macOS 26.5.2 arm64; qdrant-client 1.19.1, torch 2.14.0, transformers 4.57.6, bert-score 0.3.13, numpy 2.5.3. Local embedded Qdrant and offline models; BERTScore CPU.

The lock merges the parent and expansion with the 11 reconciliation decisions, uses bounded independent references for GEN-01/ACE-01/ACE-02, and retains the full-text-informed perpetration caveat. Original proposals and the blinded AI review remain unchanged, with input hashes in the lockable labels. Historical NONE-ADHD retains its ID but is now answerable. Human review remains explicitly pending for later validation, not assigned to the product owner.

## Reproduction and checks

```sh
PYTHONPATH=src HF_HUB_OFFLINE=1 .venv/bin/python scripts/rag_general_benchmark.py \
  --gold agent_docs/RAG_GENERAL_ASSOCIATION_GOLD_21_SOURCE.json \
  --output data/indexes/rag_general_benchmark_21_source_results.json
```

The runner verifies the gold checksum, corpus/source manifests, encoder weights, BERTScore weights, eligibility and collection counts. The consolidation script refuses to overwrite existing locked labels. Do not relabel after inspecting ranks without creating a new version and declaring the resulting evaluation non-held-out.

Verification: `PYTHONPATH=src .venv/bin/python -m pytest tests/unit -q` — 42 passed, 12 subtests passed. Added regression coverage for context-only negatives, explicit/legacy ranking and checksum tamper detection. Historical 16-source results and labels were preserved.

Limitations: small reused/paraphrased question set, AI-reviewed labels, abstract-only indexed text, only one negative, and no passage-level gold. Full-text-informed source cautions do not make all retrieved passages independently sufficient. These results support engineering comparison, not clinical approval.
