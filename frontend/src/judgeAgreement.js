export const QUALITY_LABELS = ["bad", "acceptable", "good"];

/** Calculate chance-adjusted agreement using explicitly paired ordinal labels. */
export function kappa(left, right, weighting = null) {
  if (left.length !== right.length || [...left, ...right].some(x => !QUALITY_LABELS.includes(x))) throw new Error("Invalid paired labels");
  if (![null, "linear", "quadratic"].includes(weighting)) throw new Error("Invalid weighting");
  const n = left.length;
  if (!n) return { n: 0, value: null, agreement: null };
  const matrix = Array.from({ length: 3 }, () => [0, 0, 0]);
  left.forEach((label, i) => { matrix[QUALITY_LABELS.indexOf(label)][QUALITY_LABELS.indexOf(right[i])] += 1; });
  const rows = matrix.map(row => row.reduce((a, b) => a + b, 0));
  const columns = QUALITY_LABELS.map((_, j) => matrix.reduce((a, row) => a + row[j], 0));
  let observed = 0, expected = 0;
  matrix.forEach((row, i) => row.forEach((count, j) => {
    let distance = weighting ? Math.abs(i - j) / 2 : Number(i !== j);
    if (weighting === "quadratic") distance **= 2;
    observed += distance * count / n;
    expected += distance * rows[i] * columns[j] / n ** 2;
  }));
  return { n, value: expected > 0 ? 1 - observed / expected : null,
    agreement: matrix.reduce((a, row, i) => a + row[i], 0) / n };
}

/** Reject imported reviews that alter the frozen stimuli or invent confirmed labels. */
export function validateReview(original, imported) {
  if (original.case_sha256 !== imported.case_sha256 || original.cases.length !== imported.cases?.length) throw new Error("Wrong review packet");
  const fields = ["id", "query_id", "split", "question", "response", "reference_answer", "pmids"];
  original.cases.forEach((row, i) => {
    const other = imported.cases[i];
    if (fields.some(key => JSON.stringify(row[key]) !== JSON.stringify(other[key]))) throw new Error("Frozen response content changed");
    if (other.human_reviewed === true && !QUALITY_LABELS.includes(other.human_annotation)) throw new Error("Confirmed review has no valid label");
  });
  return imported;
}
