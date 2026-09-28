# Bodhica evaluation monitor

Open the **Evaluations** tab at `http://localhost:5173`. The read-only API is
`GET /v1/evaluations/dashboard`; it accepts loopback connections without forwarded-client headers.
Add administrator authentication before exposing the dashboard through a deployment proxy.

## Scores and provenance

- **Groundedness**: automated judge estimates support for generated factual claims in the supplied corpus passages. Only corpus-cited answers enter this mean.
- **Correctness**: automated judge compares the generated answer with the frozen reference answer. Abstention on an answerable case scores zero; generation and judge failures are excluded and reported separately.
- Judge model, generator model, corpus hash, dataset hash, sample size, and date accompany each report. The default judge is the configured generator model, so the judgment is not independent or human-validated.
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
