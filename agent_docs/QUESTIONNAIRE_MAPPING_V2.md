# Questionnaire mapping v2

Silpa approved mapping updates for the revised questionnaire on 2026-09-28.
The active public/backend contract is `prototype_questionnaire_v2`. Version 1
submissions are rejected rather than reinterpreted after the question-ID changes.

## Revised public IDs

| Public ID | Revised question meaning | Existing checkpoint feature | Codes |
| --- | --- | --- | --- |
| q007 | Visual experiences around age 15 | `SCZ15_PROD_seen_hallucinations9` | 0–2 |
| q014 | Visual experiences around age 15, unchanged | `SCZ15_Seen_hallucinations15` | 0–2 |
| q066 | Repeated bullying | `ACE15_bullied_often15` | 1–5 |
| q067 | Mocking, hurtful names or embarrassment | `ACE15_tease_bullying15` | 1–5 |
| q068 | Exclusion or emotional bullying | `ACE15_emotional_bullying15` | 1–5 |
| q069 | Harmful rumours | `ACE15_rumours_bullying15` | 1–5 |
| q070 | Number of people involved | `ACE15_bullying_by_num15` | 1–6 |
| q071 | Bullying duration | `ACE15_bullying_time15` | 1–6 |
| q072 | Other bullying, now last | `ACE15_other_bullying15` | 1–5 |
| q073 | Prejudice-motivated violence | `ACE18_hate_crime18` | 0–1 |
| q074 | Emotional harm | `ACE18_emotional_abuse18` | 0–1 |
| q075 | Witnessing threatening or violent crime | `ACE18_witness_crime18` | 0–1 |
| q076 | Other harmful event, now last | `ACE18_other_abuse18` | 0–1 |

Option codes retain their accepted meanings; only their public question associations
change. All other questions retain their previous feature mappings. The backend maps
by feature name and emits all 105 values in each checkpoint's original schema order.
Neither checkpoint nor its metadata is renamed, reordered or retrained.

## Timeframe limitation

The user revised q007 from age 9 to age 15. Its legacy checkpoint feature remains
`SCZ15_PROD_seen_hallucinations9`; replacing it with the existing age-15 feature would
drop a required input or duplicate q014's feature assignment. This is an explicit
prototype wording-to-feature alias, not verified measurement equivalence. Both q007
and q014 now ask about age-15 visual experiences. Changing the model's learned input
semantics requires training-data clarification and potentially retraining, not an
artifact-field rename.

## Verification

Tests compare the complete frontend/backend option contracts and version identifiers.
For each revised ID and both checkpoints, a one-answer change must modify only its
intended feature, preserve all 105 inputs and retain the artifact's input order.
Version-1 submissions are covered by explicit rejection tests.
