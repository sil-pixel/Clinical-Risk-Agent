export const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

let pendingSession = null;

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

export async function deleteSession(token) {
  if (!token) return;
  await fetch(`${API_BASE}/v1/session`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
}

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
