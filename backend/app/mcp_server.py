"""MCP server over the same service layer the HTTP API uses.

An assistant that can reach this corpus is a different product from a web app
that can, and the difference should not be a second implementation of the
rules. Every tool here calls `app.query.service` and `app.db.repository`
directly -- the same two confidence gates, the same routing walk over
document_people, the same citation shape, the same query_log and gaps rows.
Swap the transport and the answers do not change. If they ever do, one of the
two surfaces has grown a rule the other does not have, which is the thing this
layout exists to prevent.

The one place a difference is deliberate: an assistant reads prose, not JSON
with an excerpt field, so `ask` returns a rendered answer with its citations
inline and keeps the structured payload alongside it. A model that has to
reconstruct the citation mapping from an array of indices will sometimes get it
wrong, and a wrong citation is worse here than a verbose one.

    python -m app.mcp_server            # stdio, the usual MCP transport

Registering it with Claude Code:

    claude mcp add meridian-kb -- python -m app.mcp_server

Read-only by design. Corrections and gap triage stay on the HTTP API behind the
review queue, because both are human judgements about a specific answer and an
assistant resolving its own gaps is a loop with nobody in it.
"""

import json
import logging
import sqlite3
from contextlib import contextmanager

from mcp.server.mcpserver import MCPServer

from app.config import settings
from app.db import repository
from app.db.connection import get_connection
from app.query.service import answer_query

logger = logging.getLogger(__name__)

# MCPServer is the SDK's high-level server; it was called FastMCP before
# mcp 2.0, which is what most examples still show.
mcp = MCPServer("meridian-kb")

MAX_EXCERPT = 400


@contextmanager
def _db():
    """One connection per tool call, for the reason app/api/deps.py gives: a
    sqlite3 connection belongs to the thread that opened it."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()


def _render(outcome) -> str:
    """The answer as an assistant should read it: claims with their sources
    attached, then the sources, then how confident the system is and why."""
    lines: list[str] = []

    if outcome.answer:
        for claim in outcome.claims:
            markers = "".join(f"[{index + 1}]" for index in claim["citations"])
            lines.append(f"{claim['text']} {markers}".strip())
        caveat = outcome.derived_metadata.get("caveat")
        if caveat:
            lines.append(f"\nCaveat: {caveat}")
    else:
        lines.append(
            f"Not answerable from the corpus (confidence {outcome.confidence:.2f}, "
            f"threshold {settings.confidence_threshold:.2f})."
        )
        routing = outcome.routing
        if routing:
            who = ", ".join(filter(None, [routing["person"], routing.get("title")]))
            lines.append(f"\nAsk {who}.")
            lines.append(f"Why: {routing['rationale']}")
            lines.append(f"Draft question: {routing['draft_question']}")
        else:
            lines.append(
                "\n"
                + outcome.derived_metadata.get(
                    "routing_unavailable",
                    "No one in the corpus is connected to this question.",
                )
            )

    if outcome.citations:
        lines.append("\nSources:")
        for index, citation in enumerate(outcome.citations, start=1):
            people = ", ".join(citation["author_or_attendees"]) or "not recorded"
            lines.append(
                f"  [{index}] {citation['source_path']} | {citation['anchor']} "
                f"| {citation['date'] or 'undated'} | {people} "
                f"| document_id={citation['document_id']}"
            )

    lines.append(
        f"\nConfidence {outcome.confidence:.2f} "
        f"(threshold {settings.confidence_threshold:.2f}); "
        f"query_id={outcome.query_id}"
    )
    return "\n".join(lines)


@mcp.tool()
def ask(question: str, top_k: int = 8) -> str:
    """Ask the Meridian Microsystems knowledge base a question.

    Searches meeting transcripts and Office documents, then either answers with
    citations or names the person to ask, depending on whether the corpus
    actually supports an answer. Returns the rendered answer followed by the
    structured payload as JSON.

    Use document_id from a citation with read_document to see the full source.
    """
    with _db() as conn:
        outcome = answer_query(conn, question, top_k=top_k)

    payload = {
        "query_id": outcome.query_id,
        "answer": outcome.answer,
        "confidence": outcome.confidence,
        "confidence_threshold": settings.confidence_threshold,
        "confidence_breakdown": outcome.confidence_breakdown,
        "claims": outcome.claims,
        "citations": [
            {**citation, "excerpt": citation["excerpt"][:MAX_EXCERPT]}
            for citation in outcome.citations
        ],
        "derived_metadata": outcome.derived_metadata,
        "routing": outcome.routing,
        "gap_id": outcome.gap_id,
    }
    return f"{_render(outcome)}\n\n---\n{json.dumps(payload, indent=2, default=str)}"


@mcp.tool()
def read_document(document_id: int, include_raw_text: bool = False) -> str:
    """Open the full source behind a citation.

    Returns the document's metadata, its verbatim author/attendee list, every
    chunk with its anchor, and the decisions and action items enrichment
    derived from it. Evidence quotes that could not be located verbatim in the
    source are withheld rather than shown.

    raw_text is off by default because a document can be long; turn it on when
    you need the exact wording around a chunk.
    """
    with _db() as conn:
        row = repository.get_document(conn, document_id)
        if row is None:
            return f"No document with id {document_id}."

        document = dict(row)
        document["attendees_or_author"] = json.loads(document.get("attendees_or_author") or "[]")
        document["quality_flags"] = json.loads(document.get("quality_flags") or "[]")
        if not include_raw_text:
            document.pop("raw_text", None)

        document["chunks"] = [dict(c) for c in repository.get_document_chunks(conn, document_id)]
        document["people"] = [dict(p) for p in repository.get_document_people(conn, document_id)]
        document["decisions"] = [
            dict(d) for d in repository.get_document_decisions(conn, document_id)
        ]
        document["action_items"] = [
            dict(a) for a in repository.get_document_action_items(conn, document_id)
        ]

    for item in [*document["decisions"], *document["action_items"]]:
        item["evidence_verified"] = bool(item["evidence_verified"])
        if not item["evidence_verified"]:
            item["evidence"] = None

    return json.dumps(document, indent=2, default=str)


@mcp.tool()
def open_gaps(limit: int = 20) -> str:
    """List questions the corpus could not answer, newest first.

    Each gap carries the query that caused it, why it was routed, and who was
    suggested. This is the review queue a team lead triages -- reading it tells
    you what the corpus is missing, which is usually more useful than any single
    answer it can give.
    """
    with _db() as conn:
        rows = [dict(r) for r in repository.list_gaps(conn, status="open")][:limit]
    if not rows:
        return "No open gaps."
    return json.dumps(rows, indent=2, default=str)


@mcp.tool()
def health(window: int = 50) -> str:
    """Instrumentation: confidence trend, routing and correction rates,
    latency, and ingestion health.

    The number to read first is queries.answered_without_intervention -- the
    share answered with neither a routed hand-off nor a subsequent human
    correction. Compare it against the same figure over the trailing window: an
    all-time rate that looks healthy beside a much worse recent one means the
    corpus has gone stale against what people are now asking.
    """
    with _db() as conn:
        snapshot = repository.metrics_snapshot(conn, window=window)
    snapshot["confidence_threshold"] = settings.confidence_threshold
    return json.dumps(snapshot, indent=2, default=str)


def main() -> None:
    logging.basicConfig(level=logging.WARNING)  # stdout is the MCP transport
    if not settings.db_path.exists():
        raise SystemExit(
            f"No database at {settings.db_path}. "
            "Run: python -m app.ingestion.pipeline --reset"
        )
    try:
        with _db() as conn:
            conn.execute("SELECT 1 FROM chunks LIMIT 1").fetchone()
    except sqlite3.Error as exc:
        raise SystemExit(f"Database at {settings.db_path} is not usable: {exc}")

    mcp.run()


if __name__ == "__main__":
    main()
