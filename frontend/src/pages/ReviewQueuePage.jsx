import { useEffect, useState } from "react";
import { api } from "../api/client";

export default function ReviewQueuePage() {
  const [filter, setFilter] = useState("open");
  const [gaps, setGaps] = useState([]);
  const [corrections, setCorrections] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([api.listGaps(filter), api.listCorrections()])
      .then(([g, c]) => {
        setGaps(g);
        setCorrections(c);
      })
      .catch((err) => setError(err.message));
  }, [filter]);

  async function resolveGap(id) {
    await api.updateGap(id, "resolved");
    setGaps((prev) => prev.filter((g) => g.id !== id));
  }

  return (
    <section>
      <h2>Review Queue</h2>
      {error && <p role="alert">{error}</p>}

      <label>
        Filter:{" "}
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
      </label>

      <h3>Gaps</h3>
      <ul>
        {gaps.map((g) => (
          <li key={g.id}>
            {g.reason} — {g.status}{" "}
            {g.status === "open" && <button onClick={() => resolveGap(g.id)}>Mark resolved</button>}
          </li>
        ))}
      </ul>

      <h3>Corrections</h3>
      <ul>
        {corrections.map((c) => (
          <li key={c.id}>
            {c.original_answer} → {c.corrected_answer} ({c.corrected_by})
          </li>
        ))}
      </ul>
    </section>
  );
}
