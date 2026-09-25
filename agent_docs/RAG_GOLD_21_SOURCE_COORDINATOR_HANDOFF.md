# Review coordinator handoff: 21-source RAG gold judgments

Status: optional reference for the evaluation team's later human validation workstream. The current research engineering assignment is [RAG_ENGINEER_HANDOFF.md](RAG_ENGINEER_HANDOFF.md); product has approved proceeding with provisional AI-reviewed labels. No manual grading task is assigned to the product owner. No human review has been recorded. These coordinator notes contain adjudication flags, so withhold them when running a genuinely blind first pass.

## Give the reviewer these two files first

1. [Blinded source and question packet](RAG_GOLD_21_SOURCE_BLINDED_PACKET.json): 21 PubMed citations/links and 20 unlabeled questions. Its corpus-manifest SHA-256 is `3a0fb23ca8681f2918ed53cee7235df5e877468bcfa73cf156b4359b8b12c4a6`.
2. [Blank review worksheet](RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_REVIEW_WORKSHEET.json): make a copy for the reviewer to fill. Keep this template unchanged.

Do **not** give the reviewer the assistant draft, AI first pass, adjudication draft, source appraisals, old gold file, benchmark rankings, or relevance-gate report until their first-pass worksheet is saved. The packet links to PubMed abstracts without copying article text into the handoff.

For each question, inspect all 21 source abstracts and list only nonzero PMID grades: `2` when the source directly answers the exact exposure, outcome and time frame; `1` for limited context; omit grade `0`. Provide a short `evidence_spans` note for every listed PMID. Write a bounded `reference_answer` when any grade-2 source exists. If none exists, keep the answer `null` even if grade-1 context exists. Distinguish diagnosed substance-use disorder from use/experimentation and bullying perpetration from peer or cyberbullying victimization. Treat absence of direct evidence in this corpus as an abstention, not evidence that no association exists in the wider literature.

Fill the reviewer name and date. Then run:

```bash
.venv/bin/python scripts/rag_validate_gold_review.py /path/to/completed_review.json
```

The command checks completeness and structure; it does **not** decide whether the judgments are scientifically correct. The blank template intentionally fails it.

## After the first pass is saved

Only now compare with [assistant proposals](RAG_GENERAL_ASSOCIATION_GOLD_EXPANSION_REVIEW_DRAFT.json), [blinded AI first pass](RAG_GENERAL_ASSOCIATION_GOLD_INDEPENDENT_AI_FIRST_PASS.json) and [AI disagreement record](RAG_GENERAL_ASSOCIATION_GOLD_AI_ADJUDICATION_DRAFT.json). Document every disagreement and the final reasoned grade/answer, especially:

- `NONE-ADHD`: the newly added meta-analysis addresses later abuse/dependence, unlike the old 16-source corpus.
- `NONE-BULLY-SUD`: victimization papers address use or experimentation, not diagnosed SUD; grade-1 context is possible without a grade-2 answer.
- `BULLY-DIRECT-04`: asking whether these *papers establish* a causal SUD claim can be answered "no" from their designs and endpoints; do not conflate that with proving no real-world association.
- PMID 33224066: the exposure is perpetration; its pooled age-12→13 path is significant while sex-stratified cross-lagged paths are not.
- PMID 28562268: the modeled indirect victimization→use association is small, and peer victimization is not necessarily repeated bullying.
- PMID 40625792: a sip/puff counts as experimentation; it is not disorder and is not independent replication of another ABCD analysis.
- PMID 38446452: its abstract includes alcohol/drug misuse in a combined psychiatric outcome, not a separate substance-specific family-adjusted effect estimate.

## Later human-validation acceptance

A fully human-reviewed version requires recorded case judgments, evidence anchors, adjudication, reviewer identity/date and a final checksum tied to its corpus. A focused audit must instead record the subset actually reviewed. The evaluation owner should provide an annotation interface and define the audit/holdout scope. This work is not a gate to the current engineering handoff or research benchmark: the RAG engineer may consolidate and checksum-lock provisional AI-reviewed labels for exploratory runs now. Runtime threshold changes retain their architecture approval requirement.

Research-only corpus inclusion is separate from clinical approval. No individual-risk, causal, or treatment claims are authorized by this handoff.
