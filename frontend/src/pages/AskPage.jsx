import { useState } from "react";
import { api } from "../api/client";

export default function AskPage() {
  const [text, setText] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    try {
      setResult(await api.query(text));
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <section>
      <h2>Ask</h2>
      <form onSubmit={handleSubmit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask about Meridian Robotics..."
        />
        <button type="submit">Ask</button>
      </form>
      {error && <p role="alert">{error}</p>}
      {result && (
        <div>
          <p>{result.answer}</p>
          <ul>
            {result.citations?.map((c, i) => (
              <li key={i}>
                {c.source_path} — {c.author_or_attendees?.join(", ")} ({c.anchor})
              </li>
            ))}
          </ul>
          {result.routing && <RoutingCard queryId={result.query_id} routing={result.routing} />}
        </div>
      )}
    </section>
  );
}

function RoutingCard({ queryId, routing }) {
  const [question, setQuestion] = useState(routing.draft_question);
  return (
    <div>
      <h3>Low confidence — route to {routing.person}</h3>
      <p>{routing.rationale}</p>
      <textarea value={question} onChange={(e) => setQuestion(e.target.value)} />
      <button onClick={() => api.sendRouting({ query_id: queryId, person: routing.person, question })}>
        Send
      </button>
    </div>
  );
}
