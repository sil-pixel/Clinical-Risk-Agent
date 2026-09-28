import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";

const format = (value, digits = 4) => Number.isFinite(value) ? value.toFixed(digits) : "—";

function Metric({ label, value, detail }) {
  return <div className="eval-metric"><span>{label}</span><strong>{value}</strong><small>{detail}</small></div>;
}

export default function EvaluationDashboard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [target, setTarget] = useState("positive");
  const [mlRun, setMlRun] = useState("");
  const [llmRun, setLlmRun] = useState("");
  useEffect(() => {
    let active = true;
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
  const reports = data?.reports || [];
  const llmReports = reports.filter((r) => r.kind === "llm");
  const llm = llmReports.find((r) => r.run_id === llmRun) || llmReports[0];
  const mlReports = reports.filter((r) => r.kind === "ml" && r.targets?.[target]);
  const ml = mlReports.find((r) => r.run_id === mlRun) || mlReports[0];
  const metrics = ml?.targets[target];
  return <main id="main" className="evaluation-page">
    <header className="evaluation-heading"><div><span className="eyebrow eyebrow--dark">Bodhica · Developer dashboard</span>
      <h1>Evaluation monitor</h1><p>Quality benchmarks and current service performance.</p></div>
      <small>{data ? `Updated ${new Date(data.updated_at).toLocaleTimeString()} · refreshes every 10s` : "Connecting…"}</small>
    </header>
    {error && <p role="alert" className="validation-summary">{error}</p>}
    <section className="evaluation-section">
      <div className="evaluation-section-title"><h2>LLM answer quality</h2><span className="eval-badge">{llm?.metrics.correctness != null ? "Automated judge" : "Quality unscored"}</span></div>
      {llmReports.length > 1 && <label className="eval-provenance">Benchmark run <select value={llm?.run_id || ''} onChange={(e) => setLlmRun(e.target.value)}>{llmReports.map((r) => <option key={r.run_id} value={r.run_id}>{r.metrics.n} cases · {new Date(r.created_at).toLocaleString()}</option>)}</select></label>}
      <div className="eval-grid">
        <Metric label="Groundedness" value={format(llm?.metrics.groundedness, 3)} detail="Support in the cited passages · 0–1" />
        <Metric label="Correctness" value={format(llm?.metrics.correctness, 3)} detail="Agreement with frozen reference answers · 0–1" />
        <Metric label="Answer coverage" value={llm ? `${format(llm.metrics.answer_coverage * 100, 0)}%` : "—"} detail="Answered cases / attempted cases" />
        <Metric label="Attempted cases" value={llm?.metrics.n ?? "—"} detail={llm ? `${llm.metrics.grounded_n} corpus-grounded answers scored` : "No completed evaluation"} />
      </div>
      <p className="eval-provenance">{llm ? `${llm.dataset} · ${llm.model} · judge: ${llm.judge_model} · ${new Date(llm.created_at).toLocaleString()}` : "Run the frozen gold benchmark with scripts/evaluate_bodhica.py llm. Groundedness is scored only for answers with corpus evidence."}</p>
      {llm && <p className="eval-provenance">{llm.note}</p>}
      {llm?.metrics.generation_errors > 0 && <p role="status" className="eval-provenance">{llm.metrics.generation_errors} generation failures in this run. Errors appear in service monitoring rather than answer-quality scores.</p>}
      {llm?.metrics.judge_errors > 0 && <p className="eval-provenance">{llm.metrics.judge_errors} judge result(s) incomplete; only available scores enter the reported means.</p>}
    </section>
    <section className="evaluation-section">
      <div className="evaluation-section-title"><h2>ML prediction quality</h2><div className="evaluation-toggle">
        {['positive', 'negative'].map((name) => <button type="button" className={`button ${target === name ? 'button--primary' : 'button--quiet'}`} key={name} onClick={() => setTarget(name)}>{name === 'positive' ? 'Positive symptoms' : 'Negative / depressive'}</button>)}
      </div></div>
      <span className="eval-badge">{ml?.evaluation_type === "historical_multi_seed" ? "Historical baseline" : "Synthetic evaluation · holdout unverified"}</span>
      {mlReports.length > 1 && <label className="eval-provenance">Benchmark run <select value={ml?.run_id || ''} onChange={(e) => setMlRun(e.target.value)}>{mlReports.map((r) => <option key={r.run_id} value={r.run_id}>{r.dataset} · {new Date(r.created_at).toLocaleString()}</option>)}</select></label>}
      <div className="eval-grid">
        <Metric label="RMSE" value={format(metrics?.rmse)} detail="Root mean squared error · lower is better" />
        <Metric label="MSE" value={format(metrics?.mse, 6)} detail="Mean squared error · lower is better" />
        <Metric label="R²" value={format(metrics?.r2)} detail="Explained variance · can be negative" />
        <Metric label="Spearman ρ" value={format(metrics?.spearman_rho)} detail="Rank agreement · −1 to 1" />
      </div>
      <p className="eval-provenance">{ml ? `${ml.dataset} · ${ml.evaluation_type} · ${new Date(ml.created_at).toLocaleString()}` : "Current-checkpoint accuracy requires labeled evaluation data; questionnaire predictions alone cannot supply these metrics."}</p>
      {ml && <p className="eval-provenance">{ml.note} {metrics.n ? `n = ${metrics.n}` : ''}</p>}
      {metrics?.runs && <div className="eval-table-scroll"><table className="eval-table"><caption>Historical results by seed</caption><thead><tr><th>Seed</th><th>RMSE</th><th>MSE</th><th>R²</th><th>Spearman ρ</th></tr></thead><tbody>{metrics.runs.map((r) => <tr key={r.seed}><td>{r.seed}</td><td>{format(r.rmse)}</td><td>{format(r.mse, 6)}</td><td>{format(r.r2)}</td><td>{format(r.spearman_rho)}</td></tr>)}</tbody></table></div>}
    </section>
    <section className="evaluation-section"><h2>Live operations</h2>
      <p className="eval-provenance">{data?.window}. Aggregate timings only; no chat text or questionnaire answers are logged.</p>
      <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Operation</th><th>Requests</th><th>Errors</th><th>Median latency</th><th>P95 latency</th><th>Latest status</th></tr></thead>
      <tbody>{data?.operations.map((r) => <tr key={r.operation}><td>{r.operation.replaceAll('_', ' ')}</td><td>{r.count}</td><td>{r.errors}</td><td>{format(r.median_ms / 1000, 2)}s</td><td>{format(r.p95_ms / 1000, 2)}s</td><td>{r.last_status}</td></tr>)}</tbody></table></div>
      {!data?.operations.length && <p className="eval-provenance">Send a chat message or submit an assessment to start collecting timings.</p>}
    </section>
    <section className="evaluation-section"><h2>Benchmark history</h2>
      <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Completed</th><th>Evaluation</th><th>Dataset</th><th>Version / method</th></tr></thead><tbody>{reports.map((r) => <tr key={r.run_id}><td>{new Date(r.created_at).toLocaleString()}</td><td>{r.kind.toUpperCase()}</td><td>{r.dataset}</td><td>{r.model || r.evaluation_type}</td></tr>)}</tbody></table></div>
    </section>
  </main>;
}
