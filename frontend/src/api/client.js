// The only place the UI knows the API exists. Every call returns parsed JSON
// or throws an Error whose message is safe to render: FastAPI's `detail` when
// there is one, and a "the server isn't running" message for a dead socket,
// which is the failure a reviewer is most likely to hit first.

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export { BASE_URL };

class NetworkError extends Error {}

// A request the browser never delivered -- a keep-alive socket closed as it was
// written to, or a burst dropped below fetch -- fails without reaching the
// server, so re-sending is not a re-run. Reads only: a retried POST could
// double-write, and a correction stored twice is worse than an error message.
const READ_RETRIES = 2;

async function request(path, options = {}) {
  for (let attempt = 0; ; attempt++) {
    try {
      return await send(path, options);
    } catch (err) {
      const retryable = err instanceof NetworkError && !options.method;
      if (!retryable || attempt >= READ_RETRIES) throw err;
      await new Promise((resolve) => setTimeout(resolve, 150 * (attempt + 1)));
    }
  }
}

async function send(path, options) {
  let res;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      // Only the writes declare a JSON body. Sending the header on a GET as
      // well would make it a non-simple request and put a CORS preflight in
      // front of every read.
      ...(options.body ? { headers: { "Content-Type": "application/json" } } : null),
      ...options,
    });
  } catch {
    throw new NetworkError(
      `Cannot reach the API at ${BASE_URL}. Start it with ` +
        `\`uvicorn app.main:app --reload --port 8000\` from backend/.`,
    );
  }

  const body = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(detailOf(body) || `${options.method || "GET"} ${path} failed (${res.status})`);
  }
  return body;
}

// FastAPI returns `detail` as a string for HTTPException and as a list of
// error objects for request-validation failures.
function detailOf(body) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((e) => e.msg).filter(Boolean).join("; ");
  return null;
}

function queryString(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, value);
  }
  const rendered = search.toString();
  return rendered ? `?${rendered}` : "";
}

export const api = {
  health: () => request("/health"),
  query: (text) => request("/query", { method: "POST", body: JSON.stringify({ text }) }),
  getDocument: (id) => request(`/documents/${id}`),
  sendRouting: (payload) =>
    request("/routing/send", { method: "POST", body: JSON.stringify(payload) }),
  listCorrections: () => request("/corrections"),
  createCorrection: (payload) =>
    request("/corrections", { method: "POST", body: JSON.stringify(payload) }),
  listGaps: (status) => request(`/gaps${queryString({ status })}`),
  updateGap: (id, status) =>
    request(`/gaps/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  getMetrics: () => request("/metrics"),
};
