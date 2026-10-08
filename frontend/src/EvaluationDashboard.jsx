import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";

/** Format a finite metric or display a dash when it is unavailable. */
const format = (value, digits = 4) => Number.isFinite(value) ? value.toFixed(digits) : "—";

/** Render one evaluation metric with its value and interpretation. */
function Metric({ label, value, detail }) {
  return <div className="eval-metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

/** Describe the live input-drift state in one line. */
function driftSummary(drift) {
  if (!drift) return "—";
  if (drift.status === "no_reference") return "No reference profile";
  if (drift.status === "insufficient_data") return `Collecting (${drift.n}/${drift.min_n})`;
  return drift.status === "drift" ? "Drift detected" : "Stable";
}

/** Display live answer-quality estimates and aggregate service monitoring. */
export default function EvaluationDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    /** Fetch local monitoring data without updating state after unmount. */
    const refresh = async () => {
      try {
        const response = await fetch(`${API_BASE}/v1/evaluations/dashboard`);
        if (!response.ok) throw new Error("This dashboard is available on the local development server.");
        const value = await response.json();
        if (active) { setData(value); setError(""); }
      } catch (e) { if (active) setError(e.message); }
    };
    refresh();
    const timer = window.setInterval(refresh, 10000);
    return () => { active = false; window.clearInterval(timer); };
  }, []);
  const quality = data?.live_quality;
  const routing = data?.live_routing;
  const routingReport = data?.reports?.find((r) => r.kind === "routing");
  const hybrid = routingReport?.results?.hybrid;
  const baseline = routingReport?.results?.rules_only;
  const pct = (value) => Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "—";
  const guard = data?.live_guardrails;
  const drift = data?.input_drift;
  const ood = data?.input_ood;
  const oodRate = (rate) => ood?.status === "scored" ? `${format(rate * 100, 1)}%` : "—";
  return <main id="main" className="evaluation-page">
    <header className="evaluation-heading"><div><span className="eyebrow eyebrow--dark">Bodhica · Developer dashboard</span>
      <h1>Live chat evaluation</h1><p>Quality of responses delivered in this running chat service.</p></div>
      <small>{data ? `Updated ${new Date(data.updated_at).toLocaleTimeString()} · refreshes every 10s` : "Connecting…"}</small>
    </header>
    {error && <p role="alert" className="validation-summary">{error}</p>}
    <section className="evaluation-section">
      <div className="evaluation-section-title"><h2>Live LLM answer quality</h2><span className="eval-badge">Background automated judge</span></div>
      <div className="eval-grid">
        <Metric label="Groundedness" value={format(quality?.groundedness.mean, 3)} detail={`Support in source passages · ${quality?.groundedness.n ?? 0} scored replies · 0–1`} />
        <Metric label="Correctness estimate" value={format(quality?.correctness.mean, 3)} detail={`Judge-estimated factual accuracy · ${quality?.correctness.n ?? 0} scored replies · 0–1`} />
        <Metric label="Evaluated replies" value={quality?.evaluated ?? 0} detail={`${quality?.pending ?? 0} evaluation(s) pending`} />
        <Metric label="Evaluation errors" value={quality?.errors ?? 0} detail={`${quality?.skipped ?? 0} replies skipped (judge busy / unavailable)`} />
      </div>
      <p className="eval-provenance">Scores update after replies are delivered; evaluation does not delay chat. Groundedness is unscored without source passages. Correctness is an estimate from the separately configured judge model, not independently verified truth. Human calibration is pending; missing scores and failures are excluded from averages.</p>
      <p className="eval-provenance">Most recent 2,000 evaluated or skipped replies since server start. Only scores and metadata are retained; no chat text is saved. Evaluations make an additional provider request.</p>
      <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Time</th><th>Response type</th><th>Groundedness</th><th>Correctness estimate</th><th>Status / judge</th></tr></thead>
        <tbody>{quality?.recent.map((r, i) => <tr key={`${r.created_at}-${i}`}><td>{new Date(r.created_at).toLocaleTimeString()}</td><td>{r.response_kind}</td><td>{format(r.groundedness, 3)}</td><td>{format(r.correctness, 3)}</td><td>{r.status}{r.judge_model ? ` · ${r.judge_model}` : ''}</td></tr>)}</tbody></table></div>
      {!quality?.recent.length && <p className="eval-provenance">Send a chat message to start live evaluation.</p>}
    </section>
    <section className="evaluation-section">
      <div className="evaluation-section-title"><h2>Intent routing</h2><span className="eval-badge">Rules first, then embedding similarity</span></div>
      <div className="eval-grid">
        <Metric label="Messages routed" value={routing?.n ?? 0} detail="Free-text messages past safety and language checks" />
        <Metric label="Clarification rate" value={pct(routing?.clarification_rate)} detail={`Confidence below ${routing?.threshold ?? 0.85} or unfamiliar text · ${pct(routing?.unfamiliar_rate)} unfamiliar`} />
        <Metric label="Decided by rules" value={pct(routing?.rule_share)} detail="Remainder decided by the semantic router or a confirmed suggestion" />
        <Metric label="Suggestions confirmed" value={routing?.confirmed_suggestions ?? 0} detail={`${pct(routing?.suggestion_share)} of clarifications named a best guess`} />
        <Metric label="Mean confidence" value={format(routing?.mean_confidence, 3)} detail="Calibrated intent confidence · 0–1" />
      </div>
      {routing?.routed_intents && <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Routed intent</th><th>Messages</th><th>Share of routed</th></tr></thead>
        <tbody>{Object.entries(routing.routed_intents).map(([intent, count]) => {
          const routed = Object.values(routing.routed_intents).reduce((a, b) => a + b, 0);
          return <tr key={intent}><td>{intent.replaceAll("_", " ")}</td><td>{count}</td><td>{pct(count / routed)}</td></tr>;
        })}</tbody></table></div>}
      <p className="eval-provenance">Live messages have no correct labels, so live routing shows only volumes, clarifications and confidence. Most recent 2,000 messages since server start; no message text is kept.</p>
      <h3>Guardrails</h3>
      <div className="eval-grid">
        <Metric label="Refused or redirected" value={Object.values(guard?.outcomes ?? {}).reduce((a, n) => a + n, 0)} detail={`of ${guard?.messages ?? 0} chat replies · safety, medication, diagnosis, third-party, unsupported`} />
        <Metric label="Injection attempts blocked" value={routing?.prompt_guard_blocked ?? 0} detail="Prompt Guard 2, before routing or any external model" />
      </div>
      {Object.keys(guard?.outcomes ?? {}).length > 0 && <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Guardrail outcome</th><th>Replies</th></tr></thead>
        <tbody>{Object.entries(guard.outcomes).map(([k, n]) => <tr key={k}><td>{k.replaceAll("_", " ").toLowerCase()}</td><td>{n}</td></tr>)}</tbody></table></div>}
      <p className="eval-provenance">Counts of guardrail outcomes since server start; no message text is kept.</p>
      <h3>Held-out routing benchmark</h3>
      {hybrid ? <>
        <div className="eval-grid">
          <Metric label="Accuracy" value={pct(hybrid.intent.accuracy)} detail={`Rules only: ${pct(baseline?.intent.accuracy)}`} />
          <Metric label="Macro precision" value={format(hybrid.intent.macro_precision, 3)} detail={`Rules only: ${format(baseline?.intent.macro_precision, 3)}`} />
          <Metric label="Macro recall" value={format(hybrid.intent.macro_recall, 3)} detail={`Rules only: ${format(baseline?.intent.macro_recall, 3)}`} />
          <Metric label="Macro F1" value={format(hybrid.intent.macro_f1, 3)} detail={`Rules only: ${format(baseline?.intent.macro_f1, 3)}`} />
        </div>
        <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Intent</th><th>Precision</th><th>Recall</th><th>F1</th><th>Cases</th></tr></thead>
          <tbody>{Object.entries(hybrid.intent.per_label).map(([label, m]) => <tr key={label}><td>{label.replaceAll("_", " ")}</td><td>{format(m.precision, 2)}</td><td>{format(m.recall, 2)}</td><td>{format(m.f1, 2)}</td><td>{m.support}</td></tr>)}</tbody></table></div>
        <p className="eval-provenance">{`${routingReport.dataset}, ${routingReport.split} split, ${hybrid.intent.n} cases · ${routingReport.model} · ${new Date(routingReport.created_at).toLocaleDateString()}. Asking to clarify lowers recall but never precision; the clarify row scores vague messages that should be clarified. ${routingReport.eval_status === "human_approved" ? "Cases are human-approved but share an author with the router's examples" : "Cases are pending human review"}, so scores are optimistic.`}</p>
      </> : <p className="eval-provenance">Run evaluate_bodhica.py routing to produce a benchmark report.</p>}
    </section>
    <section className="evaluation-section">
      <div className="evaluation-section-title"><h2>Live ML input drift</h2><span className="eval-badge">Questionnaire inputs vs reference</span></div>
      <div className="eval-grid">
        <Metric label="Status" value={driftSummary(drift)} detail={drift?.reference?.dataset ? `Reference: ${drift.reference.dataset} · ${drift.reference.n} rows` : "Run evaluate_bodhica.py drift-reference"} />
        <Metric label="Assessments" value={drift?.n ?? 0} detail={`Scores shown from ${drift?.min_n ?? 30} submissions`} />
        <Metric label="Drifted features" value={drift?.features ? `${drift.drifted_features}/${drift.evaluated_features}` : "—"} detail={`Jensen–Shannon distance ≥ ${drift?.threshold ?? 0.1}`} />
        <Metric label="Drift share" value={format(drift?.drift_share, 2)} detail={`Dataset drift at ≥ ${drift?.dataset_drift_share ?? 0.5}`} />
      </div>
      <p className="eval-provenance">Compares the 85 answered questionnaire features with the synthetic reference profile. Polygenic and batch inputs are fixed medians and are excluded. Only cumulative per-answer counts since server start are kept; individual submissions are not retained, and scores stay hidden below the minimum sample size. Drift signals a population change, not reduced accuracy.</p>
      <div className="eval-grid">
        <Metric label="Out-of-distribution rate" value={oodRate(ood?.either_rate)} detail={`Either score above reference ${format((1 - (ood?.expected_rate ?? 0.01)) * 100, 0)}th percentile · ~${format((ood?.expected_rate ?? 0.01) * 100, 0)}% expected per score`} />
        <Metric label="Answer surprise" value={oodRate(ood?.surprise_rate)} detail="Rare answers under reference frequencies" />
        <Metric label="Mahalanobis" value={oodRate(ood?.mahalanobis_rate)} detail="Unusual combinations of answers" />
        <Metric label="OOD status" value={ood?.status === "insufficient_data" ? `Collecting (${ood.n}/${ood.min_n})` : ood?.status === "no_reference" ? "No reference" : ood ? "Scored" : "—"} detail="Each submission scored, then discarded" />
      </div>
      <p className="eval-provenance">Each completed assessment is scored against reference statistics and only the flag counts are kept. A rate well above ~1% means many users answer unlike the reference population; random answer patterns are always flagged. The reference is synthetic, so higher rates with real users are expected.</p>
      {drift?.features && <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Feature</th><th>JS distance</th><th>PSI</th><th>PSI band</th><th>Drifted</th></tr></thead>
        <tbody>{drift.features.slice(0, 10).map((f) => <tr key={f.feature}><td>{f.feature}</td><td>{format(f.js_distance, 3)}</td><td>{format(f.psi, 3)}</td><td>{f.psi_band}</td><td>{f.drifted ? "Yes" : "No"}</td></tr>)}</tbody></table></div>}
    </section>
    <section className="evaluation-section"><h2>Live operations</h2>
      <p className="eval-provenance">{data?.window}. Aggregate timings only; no chat text or questionnaire answers are logged.</p>
      <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Operation</th><th>Requests</th><th>Errors</th><th>Median latency</th><th>P95 latency</th><th>Latest status</th></tr></thead>
      <tbody>{data?.operations.map((r) => <tr key={r.operation}><td>{r.operation.replaceAll('_', ' ')}</td><td>{r.count}</td><td>{r.errors}</td><td>{format(r.median_ms / 1000, 2)}s</td><td>{format(r.p95_ms / 1000, 2)}s</td><td>{r.last_status}</td></tr>)}</tbody></table></div>
      {!data?.operations.length && <p className="eval-provenance">Send a chat message or submit an assessment to start collecting timings.</p>}
    </section>
  </main>;
}
