// The answer, its citations, and the metadata badges (Part 3 section 1).
//
// The answer is rendered claim by claim rather than as one blob, because the
// API returns it that way: each claim carries the indices of the citations it
// rests on, so a marker next to a sentence points at the source for *that*
// sentence rather than at a bibliography for the whole paragraph.
//
// The same card renders a routed query, minus the answer. What retrieval did
// find is still shown, labelled as what the system looked at -- a reviewer
// judging a routing decision needs to see the evidence it was made on.

import { fileName } from "../lib/format";
import { Badge, ConfidenceMeter } from "./ui";

export default function AnswerCard({ result, onOpenSource }) {
  const meta = result.derived_metadata || {};
  const answered = Boolean(result.answer);

  return (
    <article className={answered ? "card answer-card" : "card answer-card unanswered"}>
      <header className="answer-head">
        <div className="answer-head-main">
          <Badge tone={answered ? "ok" : "warn"}>{answered ? "Answered" : "Routed — no answer"}</Badge>
          {meta.topic_domain && <Badge tone="accent">{meta.topic_domain}</Badge>}
          {meta.priority && (
            <Badge tone={meta.priority === "high" ? "warn" : "neutral"}>{meta.priority} priority</Badge>
          )}
          {meta.source_types?.map((type) => (
            <Badge key={type}>{type}</Badge>
          ))}
          {meta.quality_flags?.map((flag) => (
            <Badge key={flag} tone="warn" title="Quality flag carried by a cited source">
              {flag}
            </Badge>
          ))}
          {meta.date_range && (
            <Badge title="Date range of the cited sources">
              {meta.date_range.earliest === meta.date_range.latest
                ? meta.date_range.earliest
                : `${meta.date_range.earliest} → ${meta.date_range.latest}`}
            </Badge>
          )}
        </div>
        <ConfidenceMeter value={result.confidence} threshold={result.confidence_threshold} />
      </header>

      {answered ? (
        <div className="answer-body">
          {result.claims?.length > 0 ? (
            result.claims.map((claim, i) => (
              <p key={i} className="claim">
                {claim.text}{" "}
                {claim.citations.map((index) => (
                  <CitationMarker
                    key={index}
                    index={index}
                    citation={result.citations[index]}
                    onOpenSource={onOpenSource}
                  />
                ))}
              </p>
            ))
          ) : (
            <p className="claim">{result.answer}</p>
          )}
          {meta.caveat && <p className="caveat">⚠ {meta.caveat}</p>}
        </div>
      ) : (
        <p className="answer-body subtle">
          Confidence fell below the threshold, so no answer was synthesized. The sources below are
          what retrieval found — shown so the routing decision can be judged, not as an answer.
        </p>
      )}

      <section className="citations">
        <h4>{answered ? `Citations (${result.citations.length})` : `Retrieved sources (${result.citations.length})`}</h4>
        <ul className="citation-list">
          {result.citations.map((citation, index) => (
            <li key={citation.chunk_id}>
              <button
                className="citation"
                onClick={() => onOpenSource(citation.document_id, citation.chunk_id)}
                title="Open the full source document"
              >
                <span className="citation-index">{index + 1}</span>
                <span className="citation-main">
                  <span className="citation-title">
                    {citation.title || fileName(citation.source_path)}
                  </span>
                  <span className="citation-meta mono">
                    {fileName(citation.source_path)} · {citation.anchor}
                    {citation.date ? ` · ${citation.date}` : ""}
                  </span>
                  <span className="citation-people">
                    {citation.author_or_attendees?.length
                      ? citation.author_or_attendees.join(", ")
                      : "no author recorded"}
                  </span>
                  <span className="citation-excerpt">{citation.excerpt}</span>
                </span>
                <span className="citation-scores">
                  <span title="Retrieval score for this chunk">{citation.score.toFixed(2)}</span>
                  {citation.quality_flags?.map((flag) => (
                    <Badge key={flag} tone="warn">
                      {flag}
                    </Badge>
                  ))}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <Breakdown result={result} />
    </article>
  );
}

function CitationMarker({ index, citation, onOpenSource }) {
  if (!citation) return null;
  return (
    <button
      className="citation-marker"
      onClick={() => onOpenSource(citation.document_id, citation.chunk_id)}
      title={`${fileName(citation.source_path)} · ${citation.anchor}`}
    >
      {index + 1}
    </button>
  );
}

/** How the confidence number was arrived at. Collapsed by default: it is the
 *  answer to "why did it score that?", which only some readers are asking. */
function Breakdown({ result }) {
  const breakdown = result.confidence_breakdown || {};
  const meta = result.derived_metadata || {};
  if (!Object.keys(breakdown).length) return null;

  // Ordered as the score is derived: the retrieval parts, the retrieval score
  // they make, then the grounding gate that discounts it, then the result.
  // `answer grounding` and `× grounding` are null when retrieval alone fell
  // short -- no draft was written, so grounding was never measured, and a 0.00
  // would read as "checked, failed".
  const signals = [
    ["top similarity", breakdown.top_similarity],
    ["support", breakdown.support],
    ["corroboration", breakdown.corroboration],
    ["source trust", breakdown.source_trust],
    ["retrieval score", breakdown.retrieval_confidence],
    ["answer grounding", breakdown.answer_support],
    ["× grounding", breakdown.grounding_multiplier],
    ["= confidence", breakdown.value],
  ];

  return (
    <details className="breakdown">
      <summary>How this confidence was computed</summary>
      <dl className="signal-grid">
        {signals.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd className="mono">{value === undefined || value === null ? "—" : Number(value).toFixed(2)}</dd>
          </div>
        ))}
        <div>
          <dt>documents matched</dt>
          <dd className="mono">{breakdown.matched_documents ?? "—"}</dd>
        </div>
        <div>
          <dt>chunks retrieved</dt>
          <dd className="mono">{meta.retrieved_chunks ?? "—"}</dd>
        </div>
      </dl>
      {breakdown.reasons?.length > 0 && (
        <ul className="reasons">
          {breakdown.reasons.map((reason, i) => (
            <li key={i}>{reason}</li>
          ))}
        </ul>
      )}
      <p className="subtle">
        {[meta.answer_method && `answer method: ${meta.answer_method}`, meta.answer_model, `${result.latency_ms} ms`]
          .filter(Boolean)
          .join(" · ")}
      </p>
    </details>
  );
}
