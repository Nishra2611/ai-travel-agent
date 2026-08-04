const BASE = "http://localhost:8001";

export async function refineTrip(sessionId, instruction) {
  const r = await fetch(`${BASE}/refine`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, instruction }),
  });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `Refinement failed with HTTP ${r.status}`);
  }
  return r.json();
}

export async function pollStatus(jobId) {
  const r = await fetch(`${BASE}/status/${jobId}`);
  return r.json();
}

export async function exportItinerary(sessionId, fmt = "json") {
  const r = await fetch(`${BASE}/export?session_id=${sessionId}&fmt=${fmt}`);
  if (fmt === "json") return r.json();
  return r.blob();
}
