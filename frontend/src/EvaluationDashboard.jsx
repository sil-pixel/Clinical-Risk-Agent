import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";

/** Format a finite metric or display a dash when it is unavailable. */
const format = (value, digits = 4) => Number.isFinite(value) ? value.toFixed(digits) : "—";

/** Render one evaluation metric with its value and interpretation. */
function Metric({ label, value, detail }) {
  return <div className="eval-metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
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
      <p className="eval-provenance">Scores update after replies are delivered; evaluation does not delay chat. Groundedness is unscored without source passages. Correctness is an estimate from the configured LLM, not independently verified truth or a gold-answer comparison. Missing scores and failures are excluded from averages.</p>
      <p className="eval-provenance">Most recent 2,000 evaluated or skipped replies since server start. Only scores and metadata are retained; no chat text is saved. Evaluations make an additional provider request.</p>
      <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Time</th><th>Response type</th><th>Groundedness</th><th>Correctness estimate</th><th>Status / judge</th></tr></thead>
        <tbody>{quality?.recent.map((r, i) => <tr key={`${r.created_at}-${i}`}><td>{new Date(r.created_at).toLocaleTimeString()}</td><td>{r.response_kind}</td><td>{format(r.groundedness, 3)}</td><td>{format(r.correctness, 3)}</td><td>{r.status}{r.judge_model ? ` · ${r.judge_model}` : ''}</td></tr>)}</tbody></table></div>
      {!quality?.recent.length && <p className="eval-provenance">Send a chat message to start live evaluation.</p>}
    </section>
    <section className="evaluation-section">
      <h2>Live ML accuracy</h2>
      <div className="eval-grid">
        <Metric label="RMSE" value="—" detail="Needs matched observed outcome labels" />
        <Metric label="MSE" value="—" detail="Needs matched observed outcome labels" />
        <Metric label="R²" value="—" detail="Needs matched observed outcome labels" />
        <Metric label="Spearman ρ" value="—" detail="Needs matched observed outcome labels" />
      </div>
      <p className="eval-provenance">Questionnaire predictions alone cannot measure live accuracy. These metrics remain unscored until matched outcome labels are available; archived benchmark values are not substituted.</p>
    </section>
    <section className="evaluation-section"><h2>Live operations</h2>
      <p className="eval-provenance">{data?.window}. Aggregate timings only; no chat text or questionnaire answers are logged.</p>
      <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Operation</th><th>Requests</th><th>Errors</th><th>Median latency</th><th>P95 latency</th><th>Latest status</th></tr></thead>
      <tbody>{data?.operations.map((r) => <tr key={r.operation}><td>{r.operation.replaceAll('_', ' ')}</td><td>{r.count}</td><td>{r.errors}</td><td>{format(r.median_ms / 1000, 2)}s</td><td>{format(r.p95_ms / 1000, 2)}s</td><td>{r.last_status}</td></tr>)}</tbody></table></div>
      {!data?.operations.length && <p className="eval-provenance">Send a chat message or submit an assessment to start collecting timings.</p>}
    </section>
  </main>;
}
