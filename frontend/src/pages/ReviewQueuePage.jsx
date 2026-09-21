// The review queue (Part 3 section 3): what the system could not answer and
// what humans had to correct, as one triage list.
//
// Gaps and corrections are the two failure modes and they read differently --
// a gap is "nobody answered this yet", a correction is "the answer was wrong" --
// so they are separate lists on one screen rather than a merged feed. Both are
// joined to the query that caused them by the API, which is what makes a row
// triageable instead of a bare reason string.

import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { Badge, Empty, ErrorNote, Spinner } from "../components/ui";
import { formatTimestamp } from "../lib/format";

const FILTERS = [
  { id: "open", label: "Open" },
  { id: "resolved", label: "Resolved" },
  { id: "", label: "All" },
];

export default function ReviewQueuePage() {
  const [filter, setFilter] = useState("open");
  const [gaps, setGaps] = useState([]);
  const [corrections, setCorrections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [g, c] = await Promise.all([api.listGaps(filter), api.listCorrections()]);
      setGaps(g);
      setCorrections(c);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  async function setStatus(id, status) {
    try {
      const updated = await api.updateGap(id, status);
      // Re-filter rather than patch in place: under "Open", a resolved gap
      // should leave the list it no longer belongs to.
      setGaps((prev) =>
        filter && updated.status !== filter
          ? prev.filter((gap) => gap.id !== id)
          : prev.map((gap) => (gap.id === id ? { ...gap, ...updated } : gap)),
      );
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section className="page">
      <div className="page-head">
        <h2>Review queue</h2>
        <p className="subtle">
          Everything the system escalated or got wrong, for a lead to work through periodically.
        </p>
      </div>

      <div className="queue-toolbar">
        <div className="segmented" role="group" aria-label="Filter gaps by status">
          {FILTERS.map((option) => (
            <button
              key={option.id || "all"}
              className={filter === option.id ? "segment active" : "segment"}
              onClick={() => setFilter(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <button className="btn-secondary" onClick={load} disabled={loading}>
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {error && <ErrorNote>{error}</ErrorNote>}
      {loading && <Spinner label="Loading the queue…" />}

      {!loading && (
        <>
          <section className="queue-section">
            <h3>Gaps ({gaps.length})</h3>
            {gaps.length === 0 ? (
              <Empty>
                No {filter || ""} gaps. A gap is written whenever a query falls below the confidence
                threshold.
              </Empty>
            ) : (
              <ul className="queue-list">
                {gaps.map((gap) => (
                  <GapRow key={gap.id} gap={gap} onSetStatus={setStatus} />
                ))}
              </ul>
            )}
          </section>

          <section className="queue-section">
            <h3>Corrections ({corrections.length})</h3>
            {corrections.length === 0 ? (
              <Empty>No corrections recorded yet.</Empty>
            ) : (
              <ul className="queue-list">
                {corrections.map((correction) => (
                  <CorrectionRow key={correction.id} correction={correction} />
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </section>
  );
}

function GapRow({ gap, onSetStatus }) {
  const resolved = gap.status === "resolved";
  return (
    <li className="queue-item">
      <div className="queue-item-head">
        <p className="queue-query">“{gap.query_text}”</p>
        <Badge tone={resolved ? "ok" : "warn"}>{gap.status}</Badge>
      </div>

      <p className="queue-reason">{gap.reason}</p>

      <div className="queue-facts">
        <span>
          gap #{gap.id} · query #{gap.query_id}
        </span>
        <span>confidence {Number(gap.confidence).toFixed(2)}</span>
        <span>{formatTimestamp(gap.created_at)}</span>
        {resolved && gap.resolved_at && <span>resolved {formatTimestamp(gap.resolved_at)}</span>}
      </div>

      {gap.suggested_routing_person ? (
        <div className="queue-routee">
          <strong>{gap.suggested_routing_person}</strong>
          <span className="subtle">
            {[gap.person_title, gap.person_department, gap.person_email].filter(Boolean).join(" · ")}
          </span>
        </div>
      ) : (
        <p className="subtle">No routee — nothing in the corpus connected anyone to this question.</p>
      )}

      {(gap.routing_rationale || gap.draft_question) && (
        <details className="queue-details">
          <summary>Routing detail</summary>
          {gap.routing_rationale && <p>{gap.routing_rationale}</p>}
          {gap.matched_content && <blockquote className="matched">{gap.matched_content}</blockquote>}
          {gap.draft_question && (
            <p className="draft-echo">
              <span className="subtle">Draft question: </span>
              {gap.draft_question}
            </p>
          )}
        </details>
      )}

      <div className="queue-actions">
        {resolved ? (
          <button className="btn-secondary" onClick={() => onSetStatus(gap.id, "open")}>
            Reopen
          </button>
        ) : (
          <button className="btn" onClick={() => onSetStatus(gap.id, "resolved")}>
            Mark resolved
          </button>
        )}
      </div>
    </li>
  );
}

function CorrectionRow({ correction }) {
  return (
    <li className="queue-item">
      <div className="queue-item-head">
        <p className="queue-query">“{correction.query_text}”</p>
        <Badge tone="accent">corrected</Badge>
      </div>

      <div className="diff">
        <div className="diff-side">
          <h4>What the system said</h4>
          <p>{correction.original_answer || <span className="subtle">no answer — it routed</span>}</p>
        </div>
        <div className="diff-side diff-corrected">
          <h4>What it should say</h4>
          <p>{correction.corrected_answer}</p>
        </div>
      </div>

      <div className="queue-facts">
        <span>
          correction #{correction.id} · query #{correction.query_id}
        </span>
        <span>by {correction.corrected_by}</span>
        <span>{formatTimestamp(correction.timestamp)}</span>
      </div>
    </li>
  );
}
