// The ask screen (Part 3 sections 1-2).
//
// One POST /query drives everything below it: the same response either carries
// an answer with citations or a routing card, and the page does not decide
// which -- it renders whichever branch the API's own confidence produced.

import { useState } from "react";
import { api } from "../api/client";
import AnswerCard from "../components/AnswerCard";
import CorrectionForm from "../components/CorrectionForm";
import RoutingCard, { NoRouteeCard } from "../components/RoutingCard";
import SourceDrawer from "../components/SourceDrawer";
import { ErrorNote, Spinner } from "../components/ui";

// One that the corpus answers, one that it can only route, one that nothing in
// the corpus is about -- the three outcomes the system distinguishes.
const EXAMPLES = [
  "What did we decide about the Northgate particle excursion?",
  "What is the nine pass number for Helios-3?",
  "What is our parental leave policy?",
];

export default function AskPage() {
  const [text, setText] = useState("");
  const [asking, setAsking] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [source, setSource] = useState(null);

  async function ask(question) {
    const trimmed = question.trim();
    if (!trimmed || asking) return;
    setAsking(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.query(trimmed));
    } catch (err) {
      setError(err.message);
    } finally {
      setAsking(false);
    }
  }

  const openSource = (documentId, chunkId) => setSource({ documentId, chunkId });

  return (
    <section className="page">
      <div className="page-head">
        <h2>Ask</h2>
        <p className="subtle">
          Answers are drawn from 22 meeting transcripts and 15 Office documents. Every claim carries
          the source it came from; when the corpus cannot support an answer, the question is routed
          to a person instead of guessed at.
        </p>
      </div>

      <form
        className="ask-form"
        onSubmit={(e) => {
          e.preventDefault();
          ask(text);
        }}
      >
        <input
          className="ask-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask about Meridian Microsystems…"
          aria-label="Your question"
          autoFocus
        />
        <button className="btn" type="submit" disabled={asking || !text.trim()}>
          {asking ? "Asking…" : "Ask"}
        </button>
      </form>

      <div className="examples">
        <span className="subtle">Try:</span>
        {EXAMPLES.map((example) => (
          <button
            key={example}
            className="chip"
            disabled={asking}
            onClick={() => {
              setText(example);
              ask(example);
            }}
          >
            {example}
          </button>
        ))}
      </div>

      {asking && <Spinner label="Retrieving, scoring, and checking the answer against its sources…" />}
      {error && <ErrorNote>{error}</ErrorNote>}

      {result && (
        <div className="results">
          <AnswerCard result={result} onOpenSource={openSource} />

          {result.answer && (
            <div className="answer-footer">
              {/* Keyed by query: a new question starts a new correction form,
                  never one still holding the previous answer's draft. */}
              <CorrectionForm key={result.query_id} queryId={result.query_id} />
            </div>
          )}

          {result.routing && (
            <RoutingCard
              key={result.query_id}
              queryId={result.query_id}
              routing={result.routing}
              onOpenSource={openSource}
            />
          )}

          {!result.routing && result.gap_id && (
            <NoRouteeCard
              gapId={result.gap_id}
              note={result.derived_metadata?.routing_unavailable}
            />
          )}
        </div>
      )}

      {source && (
        <SourceDrawer
          key={source.documentId}
          documentId={source.documentId}
          chunkId={source.chunkId}
          onClose={() => setSource(null)}
        />
      )}
    </section>
  );
}
