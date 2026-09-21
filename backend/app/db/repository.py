"""All SQL against the knowledge tables lives here, so the FK chain
chunks -> documents -> document_people -> people is established in one place and
cannot drift between the ingestion pipeline and the API.

Top half: ingestion-time writes. Bottom half: the query-time writes and reads
the API serves (query log, gaps, corrections, metrics), which hang off the same
chain -- a gap points at the person row that the matched document points at.
"""

import json
import sqlite3
from datetime import datetime, timezone

from app.enrichment.schema import EnrichmentResult
from app.ingestion.common import Chunk, Document
from app.retrieval.embeddings import serialize


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------- people


def upsert_person(
    conn: sqlite3.Connection,
    name: str,
    title: str | None = None,
    department: str | None = None,
    email: str | None = None,
) -> int:
    name = name.strip()
    conn.execute(
        "INSERT INTO people (name, title, department, email) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET "
        "  title = COALESCE(excluded.title, people.title), "
        "  department = COALESCE(excluded.department, people.department), "
        "  email = COALESCE(excluded.email, people.email)",
        (name, title, department, email),
    )
    row = conn.execute("SELECT id FROM people WHERE name = ?", (name,)).fetchone()
    return int(row["id"])


def resolve_person(conn: sqlite3.Connection, name: str) -> int:
    """Map a loosely-written name onto an existing person where that is unambiguous.

    Enrichment yields owners the way the source wrote them -- "Dana will produce
    the RCA" gives "Dana", whose attendee record says "Dana Okafor". Creating a
    second row would split one person in two and let Part 2 route to a half-name.
    A partial name is only merged when exactly one existing person matches; two
    Danas means we keep the ambiguous name as its own row rather than guess.
    """
    name = name.strip()
    if not name:
        raise ValueError("cannot resolve an empty person name")

    exact = conn.execute(
        "SELECT id FROM people WHERE name = ? COLLATE NOCASE", (name,)
    ).fetchone()
    if exact is not None:
        return int(exact["id"])

    if " " not in name:
        token = name.casefold()
        candidates = [
            int(row["id"])
            for row in conn.execute("SELECT id, name FROM people")
            if token in [part.casefold() for part in str(row["name"]).split()]
        ]
        if len(candidates) == 1:
            return candidates[0]

    return upsert_person(conn, name)


def link_person(conn: sqlite3.Connection, document_id: int, person_id: int, role: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO document_people (document_id, person_id, role) VALUES (?, ?, ?)",
        (document_id, person_id, role),
    )


# ------------------------------------------------------------------------ documents


def delete_document(conn: sqlite3.Connection, source_path: str) -> None:
    """Remove a document and everything hanging off it, including the vec0 rows,
    which are not covered by ON DELETE CASCADE because vec0 is a virtual table."""
    row = conn.execute(
        "SELECT id FROM documents WHERE source_path = ?", (source_path,)
    ).fetchone()
    if row is None:
        return
    document_id = int(row["id"])
    chunk_ids = [
        int(r["id"])
        for r in conn.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
    ]
    for chunk_id in chunk_ids:
        conn.execute("DELETE FROM chunk_vectors WHERE chunk_id = ?", (chunk_id,))
    conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))


def persist_document(
    conn: sqlite3.Connection,
    document: Document,
    result: EnrichmentResult,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> int:
    """Insert one fully-processed document. Replaces any prior row for the same
    source_path so re-running ingestion is idempotent."""
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"{document.source_path}: {len(chunks)} chunks but {len(embeddings)} embeddings"
        )

    delete_document(conn, document.source_path)
    enrichment = result.enrichment

    cursor = conn.execute(
        """
        INSERT INTO documents (
            source_path, source_type, title, attendees_or_author, date,
            topic_domain, priority, summary, quality_flags, raw_text,
            enrichment_method, enrichment_model, enrichment_confidence, ingested_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document.source_path,
            document.source_type,
            document.title,
            json.dumps(document.attendees_or_author),
            document.date,
            enrichment.topic_domain,
            enrichment.priority,
            enrichment.summary,
            json.dumps(enrichment.quality_flags),
            document.raw_text,
            result.method,
            result.model,
            result.confidence,
            utcnow(),
        ),
    )
    document_id = int(cursor.lastrowid)

    for chunk, vector in zip(chunks, embeddings):
        chunk_cursor = conn.execute(
            "INSERT INTO chunks (document_id, chunk_index, text, source_anchor, "
            "char_count, embedding) VALUES (?, ?, ?, ?, ?, ?)",
            (
                document_id,
                chunk.index,
                chunk.text,
                chunk.source_anchor,
                chunk.char_count,
                serialize(vector),
            ),
        )
        conn.execute(
            "INSERT INTO chunk_vectors (chunk_id, embedding) VALUES (?, ?)",
            (int(chunk_cursor.lastrowid), serialize(vector)),
        )

    # evidence has already been grounded against raw_text; a surviving quote is
    # verbatim source text, a dropped one is recorded as unverified.
    for decision in enrichment.decisions:
        conn.execute(
            "INSERT INTO decisions (document_id, text, decided_by, evidence, evidence_verified) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                document_id,
                decision.text,
                decision.decided_by,
                decision.evidence,
                int(bool(decision.evidence)),
            ),
        )

    for action in enrichment.action_items:
        conn.execute(
            "INSERT INTO action_items (document_id, text, owner, due_date, evidence, "
            "evidence_verified) VALUES (?, ?, ?, ?, ?, ?)",
            (
                document_id,
                action.text,
                action.owner,
                action.due_date,
                action.evidence,
                int(bool(action.evidence)),
            ),
        )

    role = "attendee" if document.source_type == "transcript" else "author"
    for name in document.attendees_or_author:
        link_person(conn, document_id, upsert_person(conn, name), role)
    for action in enrichment.action_items:
        if action.owner and action.owner.strip():
            link_person(conn, document_id, resolve_person(conn, action.owner), "action_owner")

    return document_id


def rebuild_fts(conn: sqlite3.Connection) -> None:
    """Resync the external-content FTS index with chunks. Cheap at this corpus
    size and immune to the trigger-drift you get from partial re-ingests."""
    conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")


# ------------------------------------------------------------------ instrumentation


def start_ingestion_run(conn: sqlite3.Connection, data_dir: str, method: str) -> int:
    cursor = conn.execute(
        "INSERT INTO ingestion_runs (started_at, data_dir, enrichment_method) VALUES (?, ?, ?)",
        (utcnow(), data_dir, method),
    )
    return int(cursor.lastrowid)


def log_ingestion_error(
    conn: sqlite3.Connection, run_id: int, source_path: str | None, stage: str, error: str
) -> None:
    conn.execute(
        "INSERT INTO ingestion_errors (run_id, source_path, stage, error) VALUES (?, ?, ?, ?)",
        (run_id, source_path, stage, error),
    )


def log_enrichment(
    conn: sqlite3.Connection, run_id: int, source_path: str, result: EnrichmentResult
) -> None:
    conn.execute(
        "INSERT INTO enrichment_log (run_id, source_path, method, confidence, fell_back, timestamp)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, source_path, result.method, result.confidence, int(result.fell_back), utcnow()),
    )


def finish_ingestion_run(
    conn: sqlite3.Connection,
    run_id: int,
    doc_count: int,
    chunk_count: int,
    parse_failures: int,
    enrichment_failures: int,
    confidences: list[float],
    duration_ms: int,
) -> None:
    conn.execute(
        """
        UPDATE ingestion_runs SET
            finished_at = ?, doc_count = ?, chunk_count = ?, parse_failures = ?,
            enrichment_failures = ?, enrichment_confidence_avg = ?,
            enrichment_confidence_min = ?, enrichment_confidence_max = ?, duration_ms = ?
        WHERE id = ?
        """,
        (
            utcnow(),
            doc_count,
            chunk_count,
            parse_failures,
            enrichment_failures,
            (sum(confidences) / len(confidences)) if confidences else None,
            min(confidences) if confidences else None,
            max(confidences) if confidences else None,
            duration_ms,
            run_id,
        ),
    )


# ------------------------------------------------------------------- query log


def log_query(
    conn: sqlite3.Connection,
    query_text: str,
    answer: str | None,
    confidence: float,
    matched_chunk_ids: list[int],
    latency_ms: int,
    routed: bool,
    source_types: list[str],
) -> int:
    """Record one query. Written for every query, answered or routed, because
    /metrics reads the routing rate off this table (Part 1 section 5)."""
    cursor = conn.execute(
        "INSERT INTO query_log (query_text, answer, confidence, timestamp, "
        "matched_chunk_ids, latency_ms, routed, source_types) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            query_text,
            answer,
            confidence,
            utcnow(),
            json.dumps(matched_chunk_ids),
            latency_ms,
            int(routed),
            json.dumps(source_types),
        ),
    )
    return int(cursor.lastrowid)


def get_query(conn: sqlite3.Connection, query_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM query_log WHERE id = ?", (query_id,)).fetchone()


# ----------------------------------------------------------------------- gaps


def record_gap(
    conn: sqlite3.Connection,
    query_id: int,
    reason: str,
    suggested_routing_person: str | None,
    suggested_person_id: int | None,
    routing_rationale: str | None,
    matched_content: str | None,
    draft_question: str | None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO gaps (query_id, reason, suggested_routing_person, suggested_person_id, "
        "routing_rationale, matched_content, draft_question, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, 'open', ?)",
        (
            query_id,
            reason,
            suggested_routing_person,
            suggested_person_id,
            routing_rationale,
            matched_content,
            draft_question,
            utcnow(),
        ),
    )
    return int(cursor.lastrowid)


def list_gaps(
    conn: sqlite3.Connection,
    status: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    """Gaps newest first, joined to the query that produced them.

    The join is the point: a gap with no query text is untriageable, so the read
    path never hands back a bare reason string.
    """
    clauses, params = [], []
    if status:
        clauses.append("g.status = ?")
        params.append(status)
    if since:
        clauses.append("g.created_at >= ?")
        params.append(since)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    return conn.execute(
        f"""
        SELECT g.*, q.query_text, q.confidence, q.timestamp AS query_timestamp,
               p.title AS person_title, p.department AS person_department,
               p.email AS person_email
        FROM gaps g
        JOIN query_log q ON q.id = g.query_id
        LEFT JOIN people p ON p.id = g.suggested_person_id
        {where}
        ORDER BY g.created_at DESC, g.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


def set_gap_status(conn: sqlite3.Connection, gap_id: int, status: str) -> sqlite3.Row | None:
    conn.execute(
        "UPDATE gaps SET status = ?, resolved_at = ? WHERE id = ?",
        (status, utcnow() if status == "resolved" else None, gap_id),
    )
    return conn.execute("SELECT * FROM gaps WHERE id = ?", (gap_id,)).fetchone()


# ---------------------------------------------------------------- corrections


def record_correction(
    conn: sqlite3.Connection,
    query_id: int,
    original_answer: str | None,
    corrected_answer: str,
    corrected_by: str | None,
) -> int:
    cursor = conn.execute(
        "INSERT INTO corrections (query_id, original_answer, corrected_answer, "
        "corrected_by, timestamp) VALUES (?, ?, ?, ?, ?)",
        (query_id, original_answer, corrected_answer, corrected_by, utcnow()),
    )
    return int(cursor.lastrowid)


def list_corrections(
    conn: sqlite3.Connection,
    query_id: int | None = None,
    corrected_by: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    clauses, params = [], []
    if query_id is not None:
        clauses.append("c.query_id = ?")
        params.append(query_id)
    if corrected_by:
        clauses.append("c.corrected_by = ?")
        params.append(corrected_by)
    if since:
        clauses.append("c.timestamp >= ?")
        params.append(since)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    return conn.execute(
        f"""
        SELECT c.*, q.query_text, q.confidence
        FROM corrections c
        JOIN query_log q ON q.id = c.query_id
        {where}
        ORDER BY c.timestamp DESC, c.id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()


# ------------------------------------------------------------------ documents


def get_document(conn: sqlite3.Connection, document_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()


def get_document_chunks(conn: sqlite3.Connection, document_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, chunk_index, text, source_anchor, char_count FROM chunks "
        "WHERE document_id = ? ORDER BY chunk_index",
        (document_id,),
    ).fetchall()


def get_document_people(conn: sqlite3.Connection, document_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT p.id, p.name, p.title, p.department, p.email, dp.role "
        "FROM document_people dp JOIN people p ON p.id = dp.person_id "
        "WHERE dp.document_id = ? ORDER BY dp.role, p.name",
        (document_id,),
    ).fetchall()


def get_document_decisions(conn: sqlite3.Connection, document_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, text, decided_by, evidence, evidence_verified FROM decisions "
        "WHERE document_id = ? ORDER BY id",
        (document_id,),
    ).fetchall()


def get_document_action_items(conn: sqlite3.Connection, document_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, text, owner, due_date, evidence, evidence_verified FROM action_items "
        "WHERE document_id = ? ORDER BY id",
        (document_id,),
    ).fetchall()


def find_person(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT id, name, title, department, email FROM people WHERE name = ? COLLATE NOCASE",
        (name.strip(),),
    ).fetchone()


# ------------------------------------------------------------------- metrics


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(fraction * (len(ordered) - 1))))
    return ordered[index]


def metrics_snapshot(conn: sqlite3.Connection, window: int = 50) -> dict:
    """Everything /metrics serves, in one pass over the instrumentation tables.

    Two horizons on purpose: all-time numbers are the baseline, and the trailing
    `window` is what moves first when quality degrades. A routing rate that is
    5% all-time and 40% over the last 50 queries is the signal you want to see
    before users start complaining.
    """
    totals = conn.execute(
        "SELECT COUNT(*) AS total, AVG(confidence) AS avg_confidence, "
        "SUM(routed) AS routed FROM query_log"
    ).fetchone()
    total_queries = int(totals["total"] or 0)

    recent = conn.execute(
        "SELECT id, confidence, routed, latency_ms FROM query_log "
        "ORDER BY id DESC LIMIT ?",
        (window,),
    ).fetchall()
    recent_ids = [int(row["id"]) for row in recent]
    recent_confidences = [float(row["confidence"]) for row in recent if row["confidence"] is not None]
    recent_latencies = [float(row["latency_ms"]) for row in recent if row["latency_ms"] is not None]

    corrected_queries = int(
        conn.execute("SELECT COUNT(DISTINCT query_id) AS n FROM corrections").fetchone()["n"] or 0
    )
    recent_corrected_ids: set[int] = set()
    if recent_ids:
        placeholders = ",".join("?" * len(recent_ids))
        recent_corrected_ids = {
            int(row["query_id"])
            for row in conn.execute(
                f"SELECT DISTINCT query_id FROM corrections WHERE query_id IN ({placeholders})",
                recent_ids,
            )
        }
    recent_corrected = len(recent_corrected_ids)

    # The first-30-days headline metric (see the README): a query that was
    # answered, stayed answered, and never had to reach a human. Counted per
    # query rather than by adding two rates, which would double-count a routed
    # query that someone then corrected.
    clean_recent = sum(
        1
        for row in recent
        if not int(row["routed"]) and int(row["id"]) not in recent_corrected_ids
    )
    clean_total = int(
        conn.execute(
            "SELECT COUNT(*) AS n FROM query_log q WHERE q.routed = 0 AND NOT EXISTS "
            "(SELECT 1 FROM corrections c WHERE c.query_id = q.id)"
        ).fetchone()["n"]
        or 0
    )

    trend = [
        {
            "date": row["day"],
            "queries": int(row["queries"]),
            "avg_confidence": round(float(row["avg_confidence"]), 4)
            if row["avg_confidence"] is not None
            else None,
            "routing_rate": round(float(row["routed"] or 0) / int(row["queries"]), 4),
        }
        for row in conn.execute(
            "SELECT substr(timestamp, 1, 10) AS day, COUNT(*) AS queries, "
            "AVG(confidence) AS avg_confidence, SUM(routed) AS routed "
            "FROM query_log GROUP BY day ORDER BY day DESC LIMIT 14"
        )
    ]

    weakest = [
        {
            "query_id": int(row["id"]),
            "query_text": row["query_text"],
            "confidence": round(float(row["confidence"]), 4) if row["confidence"] is not None else None,
            "routed": bool(row["routed"]),
            "timestamp": row["timestamp"],
        }
        for row in conn.execute(
            "SELECT id, query_text, confidence, routed, timestamp FROM query_log "
            "ORDER BY confidence ASC, id DESC LIMIT 5"
        )
    ]

    gap_counts = {
        row["status"]: int(row["n"])
        for row in conn.execute("SELECT status, COUNT(*) AS n FROM gaps GROUP BY status")
    }

    run = conn.execute(
        "SELECT * FROM ingestion_runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    corpus = conn.execute(
        "SELECT COUNT(*) AS documents, AVG(enrichment_confidence) AS avg_confidence, "
        "MIN(enrichment_confidence) AS min_confidence FROM documents"
    ).fetchone()
    by_method = {
        row["enrichment_method"]: int(row["n"])
        for row in conn.execute(
            "SELECT enrichment_method, COUNT(*) AS n FROM documents GROUP BY enrichment_method"
        )
    }
    chunk_count = int(conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()["n"])
    low_confidence_documents = [
        {
            "document_id": int(row["id"]),
            "source_path": row["source_path"],
            "enrichment_confidence": round(float(row["enrichment_confidence"]), 4),
            "quality_flags": json.loads(row["quality_flags"] or "[]"),
        }
        for row in conn.execute(
            "SELECT id, source_path, enrichment_confidence, quality_flags FROM documents "
            "WHERE enrichment_confidence < 0.5 ORDER BY enrichment_confidence LIMIT 10"
        )
    ]

    def rate(numerator: float, denominator: float) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    return {
        "generated_at": utcnow(),
        "queries": {
            "total": total_queries,
            "avg_confidence": round(float(totals["avg_confidence"]), 4)
            if totals["avg_confidence"] is not None
            else None,
            "routing_rate": rate(float(totals["routed"] or 0), total_queries),
            "correction_rate": rate(corrected_queries, total_queries),
            "answered_without_intervention": rate(clean_total, total_queries),
            "recent": {
                "window": window,
                "count": len(recent),
                "avg_confidence": round(sum(recent_confidences) / len(recent_confidences), 4)
                if recent_confidences
                else None,
                "routing_rate": rate(sum(int(row["routed"]) for row in recent), len(recent)),
                "correction_rate": rate(recent_corrected, len(recent)),
                "answered_without_intervention": rate(clean_recent, len(recent)),
                "latency_p50_ms": _percentile(recent_latencies, 0.50),
                "latency_p95_ms": _percentile(recent_latencies, 0.95),
            },
            "confidence_trend": trend,
            "lowest_confidence": weakest,
        },
        "gaps": {
            "open": gap_counts.get("open", 0),
            "resolved": gap_counts.get("resolved", 0),
            "total": sum(gap_counts.values()),
        },
        "corrections": {
            "total": int(conn.execute("SELECT COUNT(*) AS n FROM corrections").fetchone()["n"]),
            "corrected_queries": corrected_queries,
        },
        "ingestion": {
            "last_run": dict(run) if run is not None else None,
            "documents": int(corpus["documents"] or 0),
            "chunks": chunk_count,
            "enrichment_methods": by_method,
            "enrichment_confidence_avg": round(float(corpus["avg_confidence"]), 4)
            if corpus["avg_confidence"] is not None
            else None,
            "enrichment_confidence_min": round(float(corpus["min_confidence"]), 4)
            if corpus["min_confidence"] is not None
            else None,
            "fell_back": int(
                conn.execute(
                    "SELECT COUNT(*) AS n FROM enrichment_log WHERE fell_back = 1"
                ).fetchone()["n"]
            ),
            "low_confidence_documents": low_confidence_documents,
        },
    }
