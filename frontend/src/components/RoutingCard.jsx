// The low-confidence path (Part 3 section 2): who, why, and an editable draft
// question with a send action.
//
// "Why" is the API's rationale plus the passage it was computed from, and the
// passage is clickable through to its source -- the point of the card is that a
// human can check the routing decision before it goes anywhere, so the evidence
// has to be in front of them, not summarized.

import { useState } from "react";
import { api } from "../api/client";
import { fileName } from "../lib/format";
import { Badge, ErrorNote } from "./ui";

export default function RoutingCard({ queryId, routing, onOpenSource }) {
  const [question, setQuestion] = useState(routing.draft_question || "");
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(null);
  const [error, setError] = useState(null);

  async function send() {
    setSending(true);
    setError(null);
    try {
      setSent(
        await api.sendRouting({
          query_id: queryId,
          person: routing.person,
          question,
          gap_id: routing.gap_id,
        }),
      );
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <article className="card routing-card">
      <header className="routing-head">
        <div>
          <h3>Route to a human</h3>
          <p className="subtle">{routing.reason}</p>
        </div>
        <Badge tone="warn">low confidence</Badge>
      </header>

      <div className="routee">
        <div className="routee-avatar" aria-hidden="true">
          {initials(routing.person)}
        </div>
        <div>
          <p className="routee-name">{routing.person}</p>
          <p className="subtle">
            {[routing.title, routing.department].filter(Boolean).join(" · ")}
          </p>
          {routing.email && <p className="mono subtle">{routing.email}</p>}
        </div>
        <Badge title="How this person is recorded against the matched document">{routing.role}</Badge>
      </div>

      <section className="routing-why">
        <h4>Why this person</h4>
        <p>{routing.rationale}</p>
        {routing.matched_content && (
          <blockquote className="matched">
            <p>{routing.matched_content}</p>
            {routing.matched_document_id && (
              <button
                className="btn-link"
                onClick={() => onOpenSource(routing.matched_document_id, null)}
              >
                {fileName(routing.matched_source_path)}
                {routing.matched_anchor ? ` · ${routing.matched_anchor}` : ""}
              </button>
            )}
          </blockquote>
        )}
      </section>

      <section className="routing-draft">
        <label htmlFor="draft-question">
          <h4>Draft question</h4>
        </label>
        <textarea
          id="draft-question"
          rows={4}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <div className="routing-actions">
          <button className="btn" onClick={send} disabled={sending || !question.trim()}>
            {sending ? "Sending…" : `Send to ${routing.person.split(" ")[0]}`}
          </button>
          <span className="subtle">
            Delivery is simulated; the recipient is still looked up in <code>people</code>.
          </span>
        </div>
        {error && <ErrorNote>{error}</ErrorNote>}
        {sent && (
          <p className="sent-note">
            Sent to <strong>{sent.to}</strong> (simulated). The gap stays open until someone
            resolves it in the review queue — sending is not answering.
          </p>
        )}
      </section>
    </article>
  );
}

/** Confidence was low and the corpus did not connect anyone to the question.
 *  The gap is still logged, which is the thing worth showing. */
export function NoRouteeCard({ gapId, note }) {
  return (
    <article className="card routing-card">
      <header className="routing-head">
        <div>
          <h3>No one to route to</h3>
          <p className="subtle">{note}</p>
        </div>
        <Badge tone="warn">gap #{gapId}</Badge>
      </header>
      <p>
        Naming whoever happens to sit nearest an unrelated paragraph would be the same fabrication
        as inventing an answer, so no suggestion is made. The gap is on the review queue.
      </p>
    </article>
  );
}

function initials(name) {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}
