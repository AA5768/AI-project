// The provenance panel behind a citation (Part 3 section 1: "clickable to show
// the source excerpt").
//
// It shows the stored document, not a re-summary of it: every chunk with the
// anchor that locates it in the real file, the verbatim people rows, and the
// decisions/action items enrichment derived -- each with the evidence quote the
// API only returns when it was verified against the raw text.

import { useEffect, useState } from "react";
import { api } from "../api/client";
import { fileName } from "../lib/format";
import { Badge, ErrorNote, Spinner } from "./ui";

export default function SourceDrawer({ documentId, chunkId, onClose }) {
  const [doc, setDoc] = useState(null);
  const [error, setError] = useState(null);

  // Mounted per document (the caller keys on documentId), so there is no
  // previous document's state to clear here.
  useEffect(() => {
    let cancelled = false;
    api
      .getDocument(documentId)
      .then((d) => !cancelled && setDoc(d))
      .catch((err) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // The cited chunk is what the reader clicked through for, so bring it into
  // view instead of making them hunt for it in a long document.
  useEffect(() => {
    if (!doc || !chunkId) return;
    document.getElementById(`chunk-${chunkId}`)?.scrollIntoView({ block: "center" });
  }, [doc, chunkId]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label="Source document"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer-head">
          <div>
            <h3>{doc?.title || (doc ? fileName(doc.source_path) : "Source")}</h3>
            {doc && <p className="mono subtle">{doc.source_path}</p>}
          </div>
          <button className="btn-icon" onClick={onClose} aria-label="Close source">
            ✕
          </button>
        </header>

        <div className="drawer-body">
          {error && <ErrorNote>{error}</ErrorNote>}
          {!doc && !error && <Spinner label="Loading source…" />}
          {doc && <DocumentBody doc={doc} chunkId={chunkId} />}
        </div>
      </aside>
    </div>
  );
}

function DocumentBody({ doc, chunkId }) {
  return (
    <>
      <div className="badge-row">
        <Badge tone="accent">{doc.source_type}</Badge>
        {doc.date && <Badge>{doc.date}</Badge>}
        {doc.topic_domain && <Badge>{doc.topic_domain}</Badge>}
        {doc.priority && <Badge tone={doc.priority === "high" ? "warn" : "neutral"}>{doc.priority} priority</Badge>}
        <Badge
          tone={doc.enrichment_confidence >= 0.5 ? "neutral" : "warn"}
          title="How confident Part 1's enrichment was about this document"
        >
          enriched {Number(doc.enrichment_confidence).toFixed(2)} · {doc.enrichment_method}
        </Badge>
        {doc.quality_flags?.map((flag) => (
          <Badge key={flag} tone="warn">
            {flag}
          </Badge>
        ))}
      </div>

      {doc.summary && <p className="drawer-summary">{doc.summary}</p>}

      {doc.people?.length > 0 && (
        <Section title={`People (${doc.people.length})`}>
          <ul className="people-list">
            {doc.people.map((person) => (
              <li key={`${person.id}-${person.role}`}>
                <strong>{person.name}</strong>
                <span className="subtle">
                  {[person.title, person.department].filter(Boolean).join(" · ")}
                </span>
                <Badge>{person.role}</Badge>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {doc.decisions?.length > 0 && (
        <Section title={`Decisions (${doc.decisions.length})`}>
          <ul className="derived-list">
            {doc.decisions.map((d) => (
              <li key={d.id}>
                <p>{d.text}</p>
                {d.decided_by && <p className="subtle">decided by {d.decided_by}</p>}
                <Evidence item={d} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {doc.action_items?.length > 0 && (
        <Section title={`Action items (${doc.action_items.length})`}>
          <ul className="derived-list">
            {doc.action_items.map((a) => (
              <li key={a.id}>
                <p>{a.text}</p>
                <p className="subtle">
                  {[a.owner && `owner ${a.owner}`, a.due_date && `due ${a.due_date}`]
                    .filter(Boolean)
                    .join(" · ")}
                </p>
                <Evidence item={a} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      <Section title={`Chunks (${doc.chunks?.length || 0})`}>
        <ul className="chunk-list">
          {doc.chunks?.map((chunk) => (
            <li
              key={chunk.id}
              id={`chunk-${chunk.id}`}
              className={chunk.id === chunkId ? "chunk cited" : "chunk"}
            >
              <p className="chunk-anchor mono">
                {chunk.source_anchor}
                {chunk.id === chunkId && <span className="cited-tag">cited</span>}
              </p>
              <p className="chunk-text">{chunk.text}</p>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

function Evidence({ item }) {
  if (!item.evidence_verified) {
    // The API withholds the quote when it could not be located in the source.
    // Saying so is more useful than showing nothing.
    return <p className="subtle">evidence quote not verified against the source — withheld</p>;
  }
  return <blockquote className="evidence">{item.evidence}</blockquote>;
}

function Section({ title, children }) {
  return (
    <section className="drawer-section">
      <h4>{title}</h4>
      {children}
    </section>
  );
}
