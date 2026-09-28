export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

let pendingSession = null;

/** Create a private session while coalescing overlapping connection requests. */
export async function createSession() {
  if (!pendingSession) {
    pendingSession = (async () => {
      const response = await fetch(`${API_BASE}/v1/session`, { method: "POST" });
      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.error?.message || "Unable to create a private session.");
      }
      return response.json();
    })().finally(() => {
      pendingSession = null;
    });
  }
  return pendingSession;
}

/** Invalidate the private backend session associated with a bearer token. */
export async function deleteSession(token) {
  if (!token) return;
  await fetch(`${API_BASE}/v1/session`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

/** Submit protected questionnaire answers and return scores or a safe API error. */
export async function submitAssessment(token, payload) {
  const response = await fetch(`${API_BASE}/v1/assessments`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) {
    const error = new Error(body.error?.message || body.message || "Assessment unavailable.");
    error.payload = body;
    throw error;
  }
  return body;
}

/** Fetch the session's latest assessment and background explanation status. */
export async function getLatestAssessment(token) {
  const response = await fetch(`${API_BASE}/v1/assessments/latest`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Explanation unavailable");
  return response.json();
}

/** Retry the LLM explanation without recalculating the cached assessment scores. */
export async function retryAssessmentExplanation(token) {
  const response = await fetch(`${API_BASE}/v1/assessments/explanation`, {
    method: "POST", headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Unable to retry the explanation right now.");
  return response.json();
}
