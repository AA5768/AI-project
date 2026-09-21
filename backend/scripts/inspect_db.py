"""Part 1 exit criteria: prove the populated DB has correct traceability chains
without needing the API.

    python -m scripts.inspect_db            (from backend/)

Checks, not just counts -- an orphaned chunk or a citation that resolves to no
author is the exact failure that would make Part 2's provenance fake.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.db.connection import get_connection  # noqa: E402


def _rule(title: str) -> None:
    print(f"\n{title}\n{'-' * max(len(title), 52)}")


def _scalar(conn, sql: str, *params) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=settings.db_path)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"No database at {args.db}. Run: python -m app.ingestion.pipeline --reset")
        return 1

    conn = get_connection(args.db)
    print(f"Database: {args.db}")

    _rule("Corpus")
    rows = conn.execute(
        "SELECT source_type, COUNT(*) n, SUM(enrichment_confidence) s FROM documents "
        "GROUP BY source_type ORDER BY source_type"
    ).fetchall()
    if not rows:
        print("  (empty -- nothing ingested yet)")
    for row in rows:
        print(f"  {row['source_type']:<12} {row['n']:>3} docs   avg conf {row['s'] / row['n']:.2f}")
    print(f"  {'TOTAL':<12} {_scalar(conn, 'SELECT COUNT(*) FROM documents'):>3} docs, "
          f"{_scalar(conn, 'SELECT COUNT(*) FROM chunks')} chunks, "
          f"{_scalar(conn, 'SELECT COUNT(*) FROM people')} people")

    _rule("Derived metadata")
    for row in conn.execute(
        "SELECT topic_domain, priority, COUNT(*) n FROM documents "
        "GROUP BY topic_domain, priority ORDER BY n DESC"
    ):
        print(f"  {row['topic_domain']:<26} {row['priority']:<12} {row['n']}")
    print(f"  decisions extracted:    {_scalar(conn, 'SELECT COUNT(*) FROM decisions')}")
    print(f"  action items extracted: {_scalar(conn, 'SELECT COUNT(*) FROM action_items')}")

    _rule("Enrichment confidence distribution")
    buckets = conn.execute(
        """
        SELECT CASE
                 WHEN enrichment_confidence < 0.4 THEN '0.0-0.4 (low)'
                 WHEN enrichment_confidence < 0.6 THEN '0.4-0.6'
                 WHEN enrichment_confidence < 0.8 THEN '0.6-0.8'
                 ELSE '0.8-1.0 (high)'
               END bucket, COUNT(*) n
        FROM documents GROUP BY bucket ORDER BY bucket
        """
    ).fetchall()
    for row in buckets:
        print(f"  {row['bucket']:<18} {'#' * row['n']} {row['n']}")

    _rule("Traceability integrity")
    checks = [
        ("chunks with no parent document",
         "SELECT COUNT(*) FROM chunks c LEFT JOIN documents d ON d.id = c.document_id "
         "WHERE d.id IS NULL"),
        ("chunks with no embedding",
         "SELECT COUNT(*) FROM chunks WHERE embedding IS NULL"),
        ("chunks missing from the vec0 index",
         "SELECT COUNT(*) FROM chunks c LEFT JOIN chunk_vectors v ON v.chunk_id = c.id "
         "WHERE v.chunk_id IS NULL"),
        ("chunks with a blank source anchor",
         "SELECT COUNT(*) FROM chunks WHERE TRIM(COALESCE(source_anchor,'')) = ''"),
        ("documents with no chunks",
         "SELECT COUNT(*) FROM documents d LEFT JOIN chunks c ON c.document_id = d.id "
         "WHERE c.id IS NULL"),
        ("documents with no author or attendee",
         "SELECT COUNT(*) FROM documents WHERE attendees_or_author IN ('[]','','null')"),
        # Owners are name-resolved onto existing people ("Dana" -> "Dana Okafor"),
        # so check the link exists rather than that the literal string is a person.
        # Only owners that do name a known person are required to have an edge:
        # enrichment also yields owners that are departments or placeholders, and
        # those deliberately stay text (see repository.resolve_person).
        ("owned actions with no action_owner link",
         "SELECT COUNT(*) FROM action_items a "
         "WHERE a.owner IS NOT NULL AND TRIM(a.owner) <> '' "
         "  AND EXISTS (SELECT 1 FROM people p WHERE p.name = a.owner COLLATE NOCASE "
         "              OR p.name LIKE a.owner || ' %') "
         "  AND NOT EXISTS (SELECT 1 FROM document_people dp "
         "                  JOIN people p2 ON p2.id = dp.person_id "
         "                  WHERE dp.document_id = a.document_id AND dp.role = 'action_owner' "
         "                    AND (p2.name = a.owner COLLATE NOCASE "
         "                         OR p2.name LIKE a.owner || ' %'))"),
        # Informational: a department or a "TBD" recorded as an owner. Visible on
        # the action item, absent from the routing graph, which is the point.
        ("action owners that are not people (kept as text)",
         "SELECT COUNT(DISTINCT a.owner) FROM action_items a "
         "WHERE a.owner IS NOT NULL AND TRIM(a.owner) <> '' "
         "  AND NOT EXISTS (SELECT 1 FROM people p WHERE p.name = a.owner COLLATE NOCASE "
         "                  OR p.name LIKE a.owner || ' %')"),
        ("document_people rows with a dangling person",
         "SELECT COUNT(*) FROM document_people dp LEFT JOIN people p ON p.id = dp.person_id "
         "WHERE p.id IS NULL"),
    ]
    # Corpus properties worth seeing, not bugs: a deliberately unattributed
    # document, and an owner the source named as a team rather than a person.
    INFORMATIONAL = ("no author or attendee", "are not people")

    failures = 0
    for label, sql in checks:
        count = _scalar(conn, sql)
        fatal = count > 0 and not any(marker in label for marker in INFORMATIONAL)
        failures += 1 if fatal else 0
        mark = "FAIL" if fatal else ("warn" if count else "ok  ")
        print(f"  [{mark}] {label:<42} {count}")

    _rule("FTS + vector index")
    fts = _scalar(conn, "SELECT COUNT(*) FROM chunks_fts")
    vec = _scalar(conn, "SELECT COUNT(*) FROM chunk_vectors")
    chunks = _scalar(conn, "SELECT COUNT(*) FROM chunks")
    print(f"  chunks={chunks}  fts_rows={fts}  vector_rows={vec}")
    if chunks and (fts != chunks or vec != chunks):
        print("  [FAIL] index row counts do not match chunks")
        failures += 1

    _rule("Sample citation chain (first 3 chunks)")
    for row in conn.execute(
        "SELECT c.id, c.source_anchor, d.source_path, d.attendees_or_author, d.topic_domain, "
        "       SUBSTR(c.text, 1, 90) snippet "
        "FROM chunks c JOIN documents d ON d.id = c.document_id ORDER BY c.id LIMIT 3"
    ):
        people = ", ".join(json.loads(row["attendees_or_author"])) or "(none)"
        print(f"  chunk {row['id']}  {row['source_path']}  @ {row['source_anchor']}")
        print(f"          people: {people}")
        print(f"          domain: {row['topic_domain']}")
        print(f"          text:   {row['snippet'].replace(chr(10), ' ')}...")

    _rule("Ingestion runs (instrumentation)")
    for row in conn.execute(
        "SELECT id, started_at, enrichment_method, doc_count, chunk_count, parse_failures, "
        "enrichment_failures, enrichment_confidence_avg, duration_ms "
        "FROM ingestion_runs ORDER BY id DESC LIMIT 5"
    ):
        avg = row["enrichment_confidence_avg"]
        print(
            f"  run {row['id']:<3} {row['started_at']}  {row['enrichment_method']:<10}"
            f" docs={row['doc_count']:<3} chunks={row['chunk_count']:<4}"
            f" parse_fail={row['parse_failures']} enrich_fallback={row['enrichment_failures']}"
            f" avg_conf={avg if avg is None else round(avg, 3)} {row['duration_ms']}ms"
        )
    errors = conn.execute(
        "SELECT stage, source_path, SUBSTR(error, 1, 100) e FROM ingestion_errors "
        "ORDER BY id DESC LIMIT 5"
    ).fetchall()
    if errors:
        print("  recent errors:")
        for row in errors:
            print(f"    [{row['stage']}] {row['source_path']}: {row['e']}")

    conn.close()
    print(f"\n{'PASS -- traceability chains intact' if not failures else f'{failures} INTEGRITY FAILURE(S)'}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
