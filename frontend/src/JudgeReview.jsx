import { useEffect, useState } from "react";
import { API_BASE } from "./api.js";
import { kappa, QUALITY_LABELS, validateReview } from "./judgeAgreement.js";

/** Display synthetic response review with explicit human confirmation and agreement scoring. */
export default function JudgeReview() {
  const [packet, setPacket] = useState(null);
  const [original, setOriginal] = useState(null);
  const [index, setIndex] = useState(0);
  const [label, setLabel] = useState("");
  const [note, setNote] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    fetch(`${API_BASE}/v1/evaluations/judge-review`).then(async response => {
      if (!response.ok) throw new Error("Review packet unavailable on the local backend.");
      return response.json();
    }).then(value => {
      if (!active) return;
      setOriginal(value);
      const saved = localStorage.getItem(`bodhica-judge-${value.case_sha256}`);
      try { setPacket(saved ? validateReview(value, JSON.parse(saved)) : value); }
      catch { setPacket(value); }
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    const current = packet?.cases[index];
    setLabel(current?.human_annotation || "");
    setNote(current?.human_note || "");
    setShowSuggestions(false);
  }, [index, packet]);
  const current = packet?.cases[index];
  /** Persist synthetic review progress locally without saving live chat text. */
  function save(value) {
    localStorage.setItem(`bodhica-judge-${value.case_sha256}`, JSON.stringify(value));
    setPacket(value);
  }
  /** Confirm only the human-selected annotation for the currently displayed response. */
  function confirm() {
    if (!QUALITY_LABELS.includes(label)) return;
    const cases = packet.cases.map((row, i) => i === index ? { ...row,
      human_annotation: label, human_reviewed: true, human_note: note,
      human_reviewed_at: new Date().toISOString() } : row);
    try { save({ ...packet, reviewer: "Silpa", cases }); setError(""); }
    catch { setError("Browser storage unavailable. Export your review before leaving this page."); setPacket({ ...packet, cases }); }
  }
  /** Export the review packet with confirmed annotations for reproducible offline scoring. */
  function exportReview() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(packet, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = "BODHICA_JUDGE_HUMAN_REVIEW.json"; link.click();
    URL.revokeObjectURL(url);
  }
  /** Import only reviews or judge runs whose immutable content matches this packet. */
  async function importReview(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      if (file.size > 2000000) throw new Error("Review file too large");
      save(validateReview(original, JSON.parse(await file.text()))); setError("");
    } catch (e) { setError(e.message); }
    event.target.value = "";
  }
  return <section className="evaluation-section">
    <h2>Judge calibration review · 100 responses</h2>
    <p>Controlled synthetic research examples—not live chat logs. Review the answer against the question and provisional reference. Labels: <strong>good</strong> = accurate and complete; <strong>acceptable</strong> = useful and safe, minor omissions; <strong>bad</strong> = material error, unsupported claim, irrelevant or unsafe.</p>
    <p className="eval-provenance">Calibration is pending. My predicted human labels are guesses, never your annotations. Reference summaries are provisional, not independently verified full-text judgments. All variants of a question remain in one split (50 calibration / 25 validation / 25 holdout).</p>
    {error && <p role="alert">{error}</p>}
    {current && <>
      <p>{packet.cases.filter(c => c.human_reviewed === true).length}/100 confirmed · {current.id} · {current.split}</p>
      <label>Response <select value={index} onChange={e => setIndex(Number(e.target.value))}>
        {packet.cases.map((row, i) => <option key={row.id} value={i}>{row.id}{row.human_reviewed ? " ✓" : ""} · {row.query_id}</option>)}
      </select></label>
      <h3>{current.question}</h3><blockquote>{current.response}</blockquote>
      <details><summary>Reference summary and sources</summary><p>{current.reference_answer}</p>
        <p>{current.pmids.length ? current.pmids.map(pmid => <a key={pmid} href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}/`} target="_blank" rel="noreferrer">PMID {pmid} </a>) : "No direct eligible source: evidence-gap case."}</p>
      </details>
      <fieldset><legend>Your annotation</legend>{QUALITY_LABELS.map(value => <label key={value} style={{ marginRight: 20 }}>
        <input type="radio" name="judge-human-label" value={value} checked={label === value} onChange={() => setLabel(value)} /> {value}
      </label>)}</fieldset>
      <label>Optional review note <input value={note} onChange={e => setNote(e.target.value)} maxLength={1000} /></label>
      <p><button onClick={confirm} disabled={!label}>Confirm my annotation</button> <button onClick={() => setIndex(Math.max(0, index - 1))} disabled={!index}>Previous</button> <button onClick={() => setIndex(Math.min(99, index + 1))} disabled={index === 99}>Next</button></p>
      <label><input type="checkbox" checked={showSuggestions} onChange={e => setShowSuggestions(e.target.checked)} /> Reveal AI suggestions (can bias your review)</label>
      {showSuggestions && <p>My annotation: {current.assistant_annotation}. My guess of your annotation: {current.predicted_human_annotation}. {current.assistant_rationale} Actual judge: {current.judge_annotation || "not scored"}.</p>}
      <p><button onClick={exportReview}>Export review</button> <label>Import review / judge results <input type="file" accept="application/json,.json" onChange={importReview} /></label></p>
      <p className="eval-provenance">Progress is stored in this browser for these synthetic examples only. Export to keep a backup. Importing replaces the current review—export first if you have unsaved work.</p>
      <h3>Confirmed human–judge agreement</h3>
      <div className="eval-table-scroll"><table className="eval-table"><thead><tr><th>Split</th><th>Paired reviews</th><th>Cohen κ</th><th>Linear weighted κ</th><th>Quadratic weighted κ</th></tr></thead><tbody>
        {["calibration", "validation", "holdout"].map(split => {
          const rows = packet.cases.filter(c => c.split === split && c.human_reviewed === true && QUALITY_LABELS.includes(c.human_annotation) && QUALITY_LABELS.includes(c.judge_annotation));
          const human = rows.map(c => c.human_annotation), judge = rows.map(c => c.judge_annotation);
          return <tr key={split}><td>{split}</td><td>{rows.length}</td>{[null, "linear", "quadratic"].map(weight => <td key={weight || "unweighted"}>{kappa(human, judge, weight).value?.toFixed(3) ?? "—"}</td>)}</tr>;
        })}
      </tbody></table></div>
      <p className="eval-provenance">Only actual model labels paired with your confirmed labels enter these scores. No pairs or degenerate label distributions produce a dash. κ measures agreement, not factual accuracy or probability calibration. Tune on calibration cases only; do not use holdout annotations to tune the judge.</p>
    </>}
  </section>;
}
