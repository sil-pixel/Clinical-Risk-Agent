# Direct ADHD/bullying source expansion — research-only handoff

Status: ready for research engineering handoff. Five sources approved by Silpa are ingested in the 21-source corpus; assistant full-text appraisal and a blinded independent AI first pass are available. Proceed using provisional AI-reviewed labels under [RAG_ENGINEER_HANDOFF.md](RAG_ENGINEER_HANDOFF.md). Human evaluation is a later validation/release workstream; no manual labeling assignment is required from the product owner. Consolidation/locking of research labels and the new benchmark remain engineering tasks.

## Candidate intake

- ADHD and later abuse/dependence: [PMID 21382538](https://pubmed.ncbi.nlm.nih.gov/21382538/), prospective-study meta-analysis. Full text inspected. Direct to SUD-like outcomes, but comorbid disruptive-behavior specificity remains unresolved.
- ADHD and later substance-use patterns: [PMID 29315559](https://pubmed.ncbi.nlm.nih.gov/29315559/), MTA observational follow-up. Full text inspected. Direct to use/onset/frequency, **not** incident SUD.
- Peer victimization and later use: [PMID 28562268](https://pubmed.ncbi.nlm.nih.gov/28562268/), longitudinal cohort. Full text inspected. Direct to a small modeled indirect path through depressive symptoms, not a robust direct total association, strict repeated-bullying definition, or SUD.
- Bullying perpetration and use: [PMID 33224066](https://pubmed.ncbi.nlm.nih.gov/33224066/), three-wave panel. Full text inspected. **Perpetration**, not victimization; smoking/drinking, not SUD. Table 5 supports a significant pooled age-12→13 path; the sex-stratified paths are non-significant, explaining the discussion's potentially confusing wording.
- Cyberbullying victimization and experimentation: [PMID 40625792](https://pubmed.ncbi.nlm.nih.gov/40625792/), ABCD cohort. Full text inspected. Cyberbullying and experimentation (as little as a sip or puff) only, not all bullying or SUD. The ABCD overlap with PMID 37598455 must not be treated as independent replication.

The detailed bounded-use and quality notes are in [RAG_DIRECT_ADHD_BULLYING_SOURCE_APPRAISALS_DRAFT.json](RAG_DIRECT_ADHD_BULLYING_SOURCE_APPRAISALS_DRAFT.json). All five PMIDs, dates, DOIs and current retraction states were checked in PubMed at ingestion on 2026-09-25. Silpa's research-corpus approval is recorded in [RAG_DIRECT_21_SOURCE_RESEARCH_MANIFEST.json](RAG_DIRECT_21_SOURCE_RESEARCH_MANIFEST.json); it is not independent human item-by-item quality adjudication or clinical approval.

## Independent judgment review

The current assignment is [RAG_ENGINEER_HANDOFF.md](RAG_ENGINEER_HANDOFF.md). The coordinator notes and blank worksheet are optional assets for a future evaluation team. When conducting a blind human first pass, provide only the blinded packet and a worksheet copy until first-pass ratings are saved.

The 20-case expansion consists of the original 13 cases, a proposed update to `NONE-ADHD`, retention of `NONE-BULLY-SUD` as no adequate direct source, and seven new questions. Assistant proposals and support anchors are in [RAG_GENERAL_ASSOCIATION_GOLD_EXPANSION_REVIEW_DRAFT.json](RAG_GENERAL_ASSOCIATION_GOLD_EXPANSION_REVIEW_DRAFT.json). They are deliberately **not** a frozen gold file. The active corpus manifest is `data/indexes/rag_corpus_manifest.json` (21 PMIDs); the prior 16-source manifest is archived as `data/indexes/rag_corpus_manifest_16_source_36a593277a41.json`.

An independent AI reviewer completed a blind first pass in [RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_AI_FIRST_PASS.json](RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_AI_FIRST_PASS.json). All 20 questions were rated over the 21-source abstract universe before it saw the assistant proposals. Eleven grade maps differed; [RAG_GENERAL_ASSOCIATION_GOLD_AI_ADJUDICATION_DRAFT.json](RAG_GENERAL_ASSOCIATION_GOLD_AI_ADJUDICATION_DRAFT.json) preserves each difference and a recommended resolution. This is a separate-model check, **not independent human sign-off**. In particular, the original `NONE-BULLY-SUD` still has no grade-2 source; use-only papers can be grade-1 context. The new `BULLY-DIRECT-04` asks whether these papers *establish* causation/SUD and is directly answerable "no" from their measured outcomes/designs rather than being an abstention case.

Later human evaluation should use a reviewer interface and an explicit audit/holdout plan owned by the evaluation team. The [blank worksheet](RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_REVIEW_WORKSHEET.json) remains available as a data format. Record actual reviewer identity, scope and decisions when that work occurs; the product owner's ingestion approval does not constitute annotation sign-off.

## Ingestion verification and gate to benchmark

1. Completed: the 21-source manifest preserves the old 16 source entries exactly and adds five Silpa-approved research-only entries, each with an assistant full-text appraisal and bounded use. The pinned MedCPT artifacts were reused; ingestion created `scientific_document_corpus_d3deb77204142fea` (21 points) and `scientific_hierarchical_corpus_45b1823ca05127fd` (39 passages). Every PMID occurs in both collections. The original 16-source collections remain present.
2. Next for the RAG engineer: consolidate the provisional AI judgments and disagreement resolutions, bind them to the corpus hash and lock a research version before running the 21-source benchmark and exploratory gate diagnostics. Human review is a later validation task. Prior 16-source results remain historical; runtime threshold changes still require architecture approval.
3. Pending for any clinical-facing use: independent human item-by-item quality adjudication, exact claim-boundary enforcement and clinical release review. Corpus admission alone does not satisfy these gates.

This is a research retrieval exercise. It does not authorize clinical advice, individual risk prediction, causal assertions, or changes to the clinical release gate.
