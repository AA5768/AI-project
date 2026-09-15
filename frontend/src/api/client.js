const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`${options?.method || "GET"} ${path} failed: ${res.status}`);
  return res.json();
}

export const api = {
  query: (text) => request("/query", { method: "POST", body: JSON.stringify({ text }) }),
  getDocument: (id) => request(`/documents/${id}`),
  sendRouting: (payload) => request("/routing/send", { method: "POST", body: JSON.stringify(payload) }),
  listCorrections: () => request("/corrections"),
  createCorrection: (payload) => request("/corrections", { method: "POST", body: JSON.stringify(payload) }),
  listGaps: (status) => request(`/gaps${status ? `?status=${status}` : ""}`),
  updateGap: (id, status) => request(`/gaps/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  getMetrics: () => request("/metrics"),
};
