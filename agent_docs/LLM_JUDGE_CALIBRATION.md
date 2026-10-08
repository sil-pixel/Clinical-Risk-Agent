# Bodhica judge calibration preparation

Status: **human review complete, judge not yet scored**. On 2026-10-08 Silpa confirmed all 100 responses (50 calibration, 25 validation, 25 holdout), exported to `agent_docs/BODHICA_JUDGE_HUMAN_REVIEW.json`. Human labels: 29 good, 13 acceptable, 58 bad. The judge model has not scored any case yet, so no human–judge κ exists. Against my provisional labels, unweighted κ is 0.55 (calibration), 0.57 (validation) and 0.63 (holdout); most disagreements are responses I labeled acceptable that were judged bad. The live judge is configured separately using `LLM_JUDGE_MODEL=gemini-3.5-flash`, sharing the Gemini provider/key with chat. Chat's model is unchanged. A different model reduces self-evaluation coupling but is not independent human verification.

Integration check on 2026-09-29: one synthetic fixture was successfully scored by `gemini-3.5-flash`, producing correctness, groundedness and `good`. This verifies adapter/model availability for that request, not agreement or reliability across all 100 cases. The remaining fixtures have not been model-scored yet; no κ can be claimed before paired reviews and judgments exist.

## Review

Review was done in a dashboard panel that has since been removed (2026-10-08) because all 100 responses are annotated. The export above is the record of human labels; the fixture-hash check in `scripts/llm_judge_review.py` rejects any edit to questions, responses or splits.

The frozen [100-response packet](LLM_JUDGE_REVIEW_100.json) contains 20 existing research questions with five controlled answer variants each. These are assistant-authored synthetic fixtures, **not Gemini-generated production responses**. They deliberately include flawed answers, which must never be served as health information. Each has my provisional annotation, rationale and prediction of Silpa's annotation. Predicted labels are guesses and never replace confirmed human review. No human labels or model judgments have been fabricated.

References are the existing provisional AI-reviewed corpus summaries, not independently established medical truth or verbatim full-text passages. The offline judge receives them as explicitly marked reference-summary proxies. This tests bounded answer quality, not real retrieval groundedness. Some abbreviated responses may cross the acceptable/bad boundary; the human review should correct my labels. This initial set does not represent the full live conversational distribution, crisis handling, questionnaire explanations or adversarial prompts. Later calibration should include consented/de-identified representative live examples and expert factual review.

## Split and agreement

All five responses to a query stay together: 50 calibration, 25 validation, 25 holdout. The frozen SHA-256 covers IDs, queries, responses, references, sources and splits. Imports reject edits to this content. AI suggestions are not supplied to the model judge.

Report unweighted Cohen's κ as the primary agreement metric, plus linear and quadratic weighted κ for ordered `bad < acceptable < good` labels. Include paired sample counts, raw agreement and confusion matrices. Undefined or empty comparisons remain null, never zero. These are agreement statistics, not factual accuracy or probability calibration; see [scikit-learn's Cohen κ reference](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.cohen_kappa_score.html).

Only `human_reviewed=true` with a valid actual human label is eligible. Actual judge labels are required for human–judge κ. My annotations are a separate comparison; predictions of your annotations are excluded. Failures remain unscored. Scores are reported separately by split, not optimistically pooled after tuning. The five variants per question are correlated, so 100 responses are not 100 independent questions; do not infer precise population performance from this sample.

## Run the model and calculate agreement

Export the review from the app, then run (from the project root):

```sh
PYTHONPATH=src .venv/bin/python scripts/llm_judge_review.py score \
  --input agent_docs/BODHICA_JUDGE_HUMAN_REVIEW.json \
  --output agent_docs/BODHICA_JUDGE_SCORED_REVIEW.json --limit 100
PYTHONPATH=src .venv/bin/python scripts/llm_judge_review.py report \
  --input agent_docs/BODHICA_JUDGE_SCORED_REVIEW.json
```

Each scored response is checkpointed; resume with the scored export as input to skip successful judgments. A run makes up to 100 billable provider calls, each with the existing 100-second Gemini deadline. Start with `--limit 1` to check availability. The scoring output is not the frozen packet. Run `report` on the scored file to get human–judge κ by split.

## Calibration completion gate

After confirmed human review and a baseline judge run, inspect calibration-split disagreements, revise the rubric or select reviewed calibration examples, and freeze model ID, rubric, prompt and fixture hashes. Evaluate changes on validation, then run holdout once after the choice is frozen. Never use holdout labels as prompt examples or to fit thresholds. If holdout is used for another tuning round it is no longer held out and needs replacement. Do not call the live scores calibrated until that reviewed, held-out validation and promotion decision are recorded. No arbitrary κ cutoff or threshold has been silently approved.

Current live quality metadata explicitly says `pending_human_review`; this implementation prepares review, independent model scoring and agreement reporting. It does not automatically tune or promote a calibration artifact before Silpa's review.
