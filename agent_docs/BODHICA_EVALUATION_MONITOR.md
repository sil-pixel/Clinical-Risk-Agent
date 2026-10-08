# Bodhica evaluation monitor

Open the **Evaluations** tab at `http://localhost:5173`. The read-only API is
`GET /v1/evaluations/dashboard`; it accepts loopback connections without forwarded-client headers.
Add administrator authentication before exposing the dashboard through a deployment proxy.

## Scores and provenance

### Live dashboard

The dashboard displays live service responses, not archived benchmark scores. After a
generated response is delivered through either message endpoint, a background LLM judge
estimates correctness (factual accuracy, relevance and completeness, **without a gold
reference**) and groundedness against that response's exact cited passages. Correctness
is an automated estimate from the separately configured judge, not human verification. Groundedness is null
for replies without source passages. Nulls and failed evaluations do not enter means.
Scores, individual score counts, pending jobs, skipped jobs and errors are displayed.

The live judge uses `LLM_JUDGE_MODEL` with the configured provider/key and makes an additional paid provider call; if unset it falls back to the chat model. Locally it is set to `gemini-3.5-flash`, while chat is unchanged. Human review of the 100-response calibration packet is complete, but the judge has not yet been scored against it, so calibration remains pending; see [the calibration workflow](LLM_JUDGE_CALIBRATION.md). Agreement is reported from the command line, not on the dashboard.
Only one live evaluation runs at a time; replies arriving while it is busy are explicitly
counted as skipped. No evaluation queue accumulates private chat content. Prompts, answers
and passages are sent to the configured provider transiently for judging but are never
written to evaluation files or monitoring logs. Only scalar scores, response type, judge
identity and timestamp are retained, in a bounded 2,000-reply memory window reset at
server restart. This is server-wide local developer telemetry, not a per-user dashboard.
The latest 20 score records are shown without chat text. Safety refusals, abstentions and
generation failures are not scored as generated answers; request failures appear in operations.

Live ML accuracy cannot be inferred from questionnaire predictions without observed
reference outcomes, so the dashboard has no ML accuracy section; ML monitoring shows input
drift and the out-of-distribution rate instead.
Existing offline reports remain on disk and available through the read-only local API.
They are not displayed in the live dashboard, except the latest held-out routing benchmark,
which is labeled as such.

### Intent routing

Free-text messages that pass the safety and language checks are routed by certain exact-match
rules first, then by the pinned embedding-similarity router (ADR-027).

- **Live**: for each routed message the dashboard keeps only the intent, whether it was routed or
  sent to clarification (confidence below 0.85 or unfamiliar text), its confidence, and whether a
  rule, the semantic router or a confirmed suggestion decided. It shows the clarification rate,
  the share of clarifications that named a best guess, confirmed suggestions, rule share, mean
  confidence and routed-intent counts over the most recent 2,000 messages since server start. A
  confirmed resend counts as a separate routed message. Message text is
  never kept. Live messages have no correct labels, so live precision and recall cannot be computed.
- **Held-out benchmark**: `.venv/bin/python scripts/evaluate_bodhica.py routing` scores the deployed
  router and the rules-only baseline on `INTENT_ROUTER_EVAL.json` (`--split test` by default;
  `calibration` or `all` are also available). The dashboard shows the latest report: accuracy,
  macro precision, recall and F1, and per-intent precision, recall and F1.
- **Clarification is treated as a prediction.** Asking to clarify on a labeled message lowers that
  intent's recall but not any intent's precision. Vague messages labeled for clarification are
  correct when clarified, and the `clarify` row scores them. Macro averages cover the six intents
  only. An intent that is never predicted counts as precision 0. Route metrics also merge
  `scientific_question` and `mental_health_education`, which share retrieval.
- Current test split (43 cases), deployed router behind Prompt Guard 2
  (ADR-028): accuracy 86.0%, macro precision 0.972, macro recall 0.877, macro F1 0.921. Rules only: 23.3%, 0.111, 0.185, 0.102. The product owner approved the
  cases on 2026-10-07. The router's reference utterances are still pending review and share an
  author with the cases, so these scores are optimistic.

### Live ML input drift

Each completed assessment adds its 85 answered feature codes to cumulative per-answer counts
(reset at server restart). Individual submissions are not retained, and the dashboard exposes
only drift scores, never the counts. Below 30 assessments it shows only the sample size, so a few
submissions cannot be reverse-read. The 20 polygenic and batch inputs are always training
medians in live use, so they are excluded.

- **Reference**: `data/monitoring/drift_reference.json`, aggregate counts from the fully
  synthetic `synthetic_dcmfnet.csv` (missing reference values excluded because live
  submissions are complete). Rebuild with
  `.venv/bin/python scripts/evaluate_bodhica.py drift-reference data/synthetic_data/synthetic_dcmfnet.csv`.
- **Per feature**: Jensen–Shannon distance (base 2, 0–1; drifted at ≥ 0.1, Evidently's
  categorical default) and PSI (stable < 0.1 ≤ moderate < 0.25 ≤ major).
- **Dataset**: drift when ≥ 50% of features drift.
- Drift shows that the input population changed. It does not measure accuracy. Because the
  reference is synthetic, drift against real users is expected and is not by itself a
  model fault.

**Out-of-distribution rate.** Each completed assessment is scored twice against reference
statistics saved in the same profile, then discarded. Only the flag counts are kept:

- **Answer surprise**: average negative log-likelihood of the answers under Laplace-smoothed
  reference answer frequencies. Flags rare or unseen answer codes.
- **Mahalanobis distance** from the reference mean, using the reference covariance. Flags
  unusual combinations of individually common answers.
- Thresholds are the 99th percentile of the reference rows (in-sample; missing reference
  values filled with each question's modal code), so about 1% of in-distribution submissions
  are flagged per score. The dashboard shows each rate and the share flagged by either score,
  hidden below 30 assessments. On the synthetic data, uniformly random answer sets were
  always flagged.

Monte Carlo dropout was evaluated and not adopted. Its spread on these checkpoints (std
≈ 0.0005 positive and 0.0001 negative, against RMSE 0.033 and 0.066) does not track error,
because dropout only acts inside attention gates.

Offline batch comparison of two non-user CSVs (saved as a `drift` report):

```sh
.venv/bin/python scripts/evaluate_bodhica.py drift reference.csv current.csv
```

### Archived offline evaluations

- **Groundedness**: automated judge estimates support for generated factual claims in the supplied corpus passages. Only corpus-cited answers enter this mean.
- **Correctness**: automated judge compares the generated answer with the frozen reference answer. Abstention on an answerable case scores zero; generation and judge failures are excluded and reported separately.
- Judge model, generator model, corpus hash, dataset hash, sample size, and date accompany each report. The default judge uses `LLM_JUDGE_MODEL` when configured, otherwise the generator model. A separate model is still not human validation.
- **RMSE, MSE, R², Spearman rho**: computed separately for both deployed checkpoints against labeled non-user data, on the normalized target scale. Spearman uses average ranks for ties; constant input produces an undefined value, displayed as a dash. R² is undefined for a constant reference target.
- The initial current-checkpoint ML report evaluates the existing 20,000-row fully synthetic Thesis dataset. Training overlap is unknown: these are descriptive benchmark scores, not established held-out accuracy. Historical multi-seed reports are separate and are not linked to deployed checkpoint identities.

Operational monitoring retains only bounded in-memory aggregates: operation type, outcome, latency, and timestamp. User chat, questionnaire answers, and model percentages are not evaluation telemetry. Benchmark JSON reports contain only non-user case IDs, aggregate scores, and version metadata.

## Re-running evaluations

With the backend running and the configured LLM key in `.env`:

```sh
.venv/bin/python scripts/evaluate_bodhica.py llm
```

This evaluates all 20 frozen cases. `--limit 5` runs an initial subset; `--judge-model MODEL`
selects another model from the same configured provider. Running a benchmark makes paid provider calls.

For a labeled non-user CSV with all 105 input columns and both target columns
(`SCZ18_Pos_Norm`, `SCZ18_Neg_Norm`):

```sh
.venv/bin/python scripts/evaluate_bodhica.py ml /path/to/evaluation.csv
```

Outputs are versioned in `data/evaluations/`; the dashboard refreshes every 10 seconds.
These commands do not retrain or modify either checkpoint. Reports survive server restarts;
operational aggregates reset at startup.

## Assessment latency recovery

Gemini calls have a 100-second provider deadline with automatic retries disabled.
The backend request deadline is 115 seconds so a single provider call has time to
complete with retrieval/validation overhead. Multi-call workflows still share that
overall backend deadline.

Both ML models load during backend startup. Assessment submission returns scores immediately
after protected inference; an asynchronous explanation uses only the validated display values.
The browser polls `GET /v1/assessments/latest` until the explanation finishes. Provider failure
retains the scores and enables **Retry explanation**, using the cached result rather than re-running
the questionnaire. This state stays in memory within the authorized session lifetime and is removed
on session reset. No assessment values are written to benchmark files.

Symptom definitions follow the project's target mapping: the positive category includes psychotic
and manic patterns; its negative target covers depressive patterns. This differs from clinical
schizophrenia terminology, in which negative symptoms concern reduced motivation, pleasure,
or emotional expression. Source: [NIMH schizophrenia overview](https://www.nimh.nih.gov/health/publications/schizophrenia).
