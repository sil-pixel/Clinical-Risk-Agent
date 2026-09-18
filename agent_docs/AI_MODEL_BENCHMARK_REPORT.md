# AI Model and Resource Benchmark Report

Status: Candidate screening complete; empirical release benchmark required before model-artifact approval

Owner: AI Architect defines gates; RAG Engineer and AI Engineer execute; Testing Agent independently verifies

Date: 2026-09-17

## Executive decision

The architecture and candidate families are approved. No exact downloadable model revision is represented as benchmark-approved because the repository contains no frozen retrieval relevance set, human-reviewed answer set, safety set, fine-tuned intent/safety artifacts, or Modal run evidence. Fabricating scores would violate the measured-selection requirement.

The primary CPU-only benchmark stack is:

- Generator: `Qwen/Qwen2.5-1.5B-Instruct-GGUF`, Q4_K_M, through `llama.cpp`.
- Dense retrieval: `ncbi/MedCPT-Query-Encoder` with `ncbi/MedCPT-Article-Encoder`.
- Reranker: `ncbi/MedCPT-Cross-Encoder`.
- Language identification: `facebook/fasttext-language-identification`.
- Intent and safety: separate project-fine-tuned `distilbert/distilbert-base-uncased` classifiers; deterministic safety rules remain authoritative.
- BERTScore: `roberta-large`, rescaled baseline, offline only.
- Vector engine: Qdrant with a versioned non-user corpus snapshot and an independent BM25 fallback index.

These are release candidates, not permission to skip the gates below.

## Operating envelope

- Device: CPU only; GPU is prohibited.
- Modal plan control: Starter credits may cover light use, but free operation is not guaranteed. Modal currently advertises `$30/month` Starter compute credit and usage-based CPU/memory billing. Configure a `$0` out-of-pocket spend limit and a usage budget no greater than available credits. See [Modal pricing](https://modal.com/pricing) and [Modal budgets](https://modal.com/docs/guide/budgets).
- Capacity: 50 active anonymous testers and 50 simultaneous HTTP requests; start with eight concurrent CPU-heavy model jobs and load shed excess work.
- Demand assumption: up to 1,000 visitors/day, not 1,000 guaranteed full model workflows/day.
- Deadline: every accepted request reaches validated `done` or safe `error` within 60 seconds.
- Scale-to-zero: `min_containers=0`; cold and warm runs are measured separately.
- Benchmark resource profiles: 2 physical CPU/4 GiB, 4 CPU/8 GiB, and 8 CPU/16 GiB. Do not approve a larger profile unless it remains inside the monthly credit simulation.

## Candidate comparison matrix

### Generator

Benchmark the primary Qwen 1.5B Q4 candidate against Qwen 0.5B Q4 and one approximately 2B permissively licensed instruction model available at execution time. Use identical prompts, evidence, output limits, and runtime.

Required measures:

- exact structured-schema validity before retry;
- claim-level citation membership and entailment;
- unsupported medical/scientific claim rate;
- preservation of target identity and supplied display values;
- disclaimer, generic-profile, and causal-language compliance;
- tokens/second, time to first validated block, total latency, peak RSS, CPU-seconds, and estimated Modal cost;
- cold/warm p50, p95, p99, and maximum;
- one bounded regeneration rate and final safe-failure rate.

Release gates:

- `100%` pass on deterministic score, citation-provenance, prohibited-content, and required-disclosure checks;
- first-pass unsupported medical/scientific claims at most `5%` and citation-context matching above `85%`;
- no controlled case exceeds the 60-second terminal-state deadline;
- peak memory fits the approved resource profile with at least 20% headroom;
- projected monthly usage fits the configured credit budget at the approved daily operation ceiling.

### Biomedical retrieval

Compare:

1. MedCPT query/article encoder pair.
2. `NeuML/pubmedbert-base-embeddings` or another pinned PubMedBERT sentence-embedding artifact with compatible licensing.
3. `sentence-transformers/all-MiniLM-L6-v2` as a small general-purpose baseline.

For each embedding compare dense only, BM25 only, hybrid RRF, hybrid plus MedCPT cross-encoder, and the full local-plus-live cascade. Use identical eligible documents and query judgments.

Initial approved configuration for measurement:

- abstract parent: title plus complete abstract;
- abstract children: 220 to 300 tokens, sentence-boundary split, one-sentence overlap;
- full-text parents: licensed section boundaries;
- full-text children: 300 tokens with at most 50-token overlap, never crossing document identity;
- dense candidates: 40;
- sparse candidates: 40;
- RRF constant: 60;
- fused candidates before reranking: 30;
- cross-encoder rerank depth: 20;
- final distinct sources: at most 5;
- one query rewrite and one live PubMed escalation maximum.

Measure Recall@5/10/20, Precision@5, MRR@10, nDCG@10, no-evidence precision/recall, conflict coverage, fallback recovery, latency, memory, and index size. Report bootstrap confidence intervals where meaningful.

The cosine `>0.85` rule is a benchmark hypothesis. Report score distributions for relevant, borderline, and irrelevant labels, precision/recall and false-negative cost at `0.85`, and the threshold that maximizes the predeclared validation objective. If `0.85` fails the objective, public release remains blocked until the AI Architect records a threshold ADR; do not silently change or retain it.

### Reranker

Compare MedCPT cross-encoder with no reranker and a small general cross-encoder baseline. Approve MedCPT only if it improves nDCG@10 or Precision@5 by at least 5% relative without causing the 60-second end-to-end gate to fail. Quantized ONNX/OpenVINO variants require parity evidence against the pinned PyTorch artifact.

### Language gate

Compare Meta fastText with Lingua on a frozen set containing Indian English, medical terms, abbreviations, short inputs, misspellings, transliterated/code-mixed text, and supported/unsupported edge cases.

The selected gate emits `SUPPORTED_ENGLISH`, `UNSUPPORTED_LANGUAGE`, or `UNCERTAIN_LANGUAGE`. Calibrate two thresholds rather than forcing a binary prediction. Release requires at least `0.98` recall for clearly unsupported non-English/code-mixed fixtures, at least `0.97` recall for supported English fixtures, and `100%` correct handling of the finite critical safety fixtures because safety interception runs first.

### Intent and safety classifiers

Fine-tune separate DistilBERT sequence classifiers. The intent artifact uses only the approved intent enum. The safety artifact uses the approved terminal categories and `ALLOW_NORMAL_PROCESSING`; it cannot weaken a deterministic rule and any critical/uncertain positive fails closed.

Intent release gates remain accuracy and macro-F1 above `0.85`, calibrated confidence, per-class reporting, out-of-distribution evaluation, and threshold selection on a held-out calibration set. Safety requires zero observed false negatives on every finite release-blocking critical fixture and reports per-class recall, precision, calibration, and abstention on broader fixtures. Prompt-injection tests are a separate adversarial slice and never replace clinical-safety evaluation.

## BERTScore policy

BERTScore is a secondary offline evaluation metric, never a runtime validator or public-response gate. Use `roberta-large` with `rescale_with_baseline=True`, normalized whitespace, pinned `bert-score` and Transformers versions, and the full reported model hash. The official implementation identifies `roberta-large` as the default English encoder and recommends reporting the configuration hash: [BERTScore project](https://github.com/Tiiiger/bert_score).

BERTScore evaluates generated text, not tabular correctness. Structured questionnaire values, probabilities, citation IDs, and provenance are evaluated by exact deterministic checks. For narrative evaluation, serialize only human-reviewed reference explanations; do not convert user records into retained evaluation data.

Build at least 200 synthetic or approved non-user cases spanning assessment explanations, scientific questions, no-evidence, conflicting evidence, safety refusals, and failure responses. Two reviewers approve references and score factual correctness, completeness, clarity, and safety. Calibrate BERTScore precision/recall/F1 against those human labels and publish correlation, receiver-operating characteristics for any proposed alert threshold, and disagreement analysis. No `0.85` threshold is assumed.

## Corpus and persistence benchmark

The local corpus contains PubMed abstracts plus eligible full text only when an explicit machine-readable license permits ingestion and display. Paywalled or unclear-license full text is excluded. Topic scope covers substance use, schizophrenia, depression, psychosis, mental, emotional, sexual, and physical abuse, bullying, ADHD, ASD, and evidence-supported associations among those subjects.

Persist only versioned public-corpus artifacts: normalized documents, Qdrant snapshot, independent BM25 index, provenance manifest, license evidence, quality appraisal, retraction status, and checksums. Store them in a dedicated non-user Modal Volume or bake an immutable snapshot into the image. Serving containers restore or mount the pinned snapshot read-only. User text, queries, sessions, questionnaire values, vectors, and results never enter that storage.

When both local paths provide no sufficient eligible evidence, allow one live PubMed E-utilities search using system-generated non-sensitive terms. Respect NCBI's documented rate limits—three requests/second without an API key and ten with a key—and use batching where possible: [NCBI E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25497/). Live candidates pass the same date, DOI/PMID, quality, license, and retraction gates before use.

## Required benchmark artifacts

- frozen dataset manifests and labeling instructions;
- candidate model IDs, revisions, licenses, checksums, quantization, and runtime versions;
- raw non-user benchmark outputs and aggregate report;
- retrieval judgments and threshold curves;
- human-review adjudication log without user data;
- cold/warm Modal resource and cost measurements;
- final pass/fail decision for every gate;
- architecture decision update naming the winning artifacts or recording the blocker.

Until these artifacts exist, implementation may use deterministic fakes and local development candidates, but public model-backed release is not approved.
