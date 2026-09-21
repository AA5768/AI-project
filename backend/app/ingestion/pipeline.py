"""Ingestion entrypoint: data/ -> parse -> chunk -> enrich -> embed -> SQLite.

One pipeline for both file families. Everything past the parser is format-blind,
which is what lets Part 2 apply identical confidence and citation rules whether a
chunk came out of a transcript or a spreadsheet.

    python -m app.ingestion.pipeline --reset
    python -m app.ingestion.pipeline --no-llm      # skip Claude, use heuristics
"""

import argparse
import logging
import time
from pathlib import Path

import yaml

from app.config import settings
from app.db import repository as repo
from app.db.connection import get_connection, init_db
from app.enrichment.enrich import enrich_document
from app.ingestion.chunking import chunk_sections
from app.ingestion.common import Document
from app.ingestion.parsers.docx_parser import parse_docx
from app.ingestion.parsers.pptx_parser import parse_pptx
from app.ingestion.parsers.transcript_parser import parse_transcript
from app.ingestion.parsers.xlsx_parser import parse_xlsx
from app.retrieval.embeddings import embed

logger = logging.getLogger(__name__)

PARSERS = {
    ".md": parse_transcript,
    ".docx": parse_docx,
    ".pptx": parse_pptx,
    ".xlsx": parse_xlsx,
}

# Office apps leave lock files (~$foo.docx) next to open documents.
SKIP_PREFIXES = ("~$", ".")


def discover_files(data_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in data_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in PARSERS
        and not p.name.startswith(SKIP_PREFIXES)
    )


def _relative(path: Path, root: Path) -> str:
    """Store repo-relative POSIX paths so citations are identical on every machine."""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_people_directory(data_dir: Path) -> dict[str, dict]:
    """Optional data/people.yaml: {name: {title, department, email}}.

    Titles and departments are what make Part 2's routing rationale readable
    ("Dana Okafor, Staff Firmware Engineer") instead of a bare name. Absent file
    is fine -- people are still created from attendee lines.
    """
    path = data_dir / "people.yaml"
    if not path.exists():
        return {}
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        logger.warning("Could not parse %s: %s", path, exc)
        return {}
    if isinstance(raw, list):
        raw = {entry["name"]: entry for entry in raw if isinstance(entry, dict) and "name" in entry}
    return {str(k): (v or {}) for k, v in raw.items()} if isinstance(raw, dict) else {}


def parse_file(path: Path, project_root: Path) -> Document:
    parser = PARSERS[path.suffix.lower()]
    return parser(path, source_path=_relative(path, project_root))


def run(
    data_dir: Path | None = None,
    db_path: Path | None = None,
    use_llm: bool | None = None,
    reset: bool = False,
    limit: int | None = None,
) -> dict:
    data_dir = Path(data_dir or settings.data_dir)
    db_path = Path(db_path or settings.db_path)
    project_root = data_dir.parent if data_dir.name == "data" else data_dir

    if reset and db_path.exists():
        db_path.unlink()
        logger.info("Removed existing database at %s", db_path)

    init_db(db_path)
    conn = get_connection(db_path)

    method = ("llm" if settings.has_api_key else "heuristic") if use_llm is None else (
        "llm" if use_llm else "heuristic"
    )
    started = time.perf_counter()
    run_id = repo.start_ingestion_run(conn, str(data_dir), method)
    conn.commit()

    files = discover_files(data_dir)
    if limit is not None:
        files = files[:limit]

    directory = load_people_directory(data_dir)
    for name, attrs in directory.items():
        repo.upsert_person(
            conn,
            name,
            title=attrs.get("title"),
            department=attrs.get("department"),
            email=attrs.get("email"),
        )
    conn.commit()

    doc_count = chunk_count = parse_failures = enrichment_failures = 0
    confidences: list[float] = []

    for path in files:
        try:
            document = parse_file(path, project_root)
        except Exception as exc:  # noqa: BLE001 - keep ingesting the rest of the corpus
            parse_failures += 1
            logger.error("Parse failed for %s: %s", path, exc)
            repo.log_ingestion_error(conn, run_id, path.name, "parse", f"{type(exc).__name__}: {exc}")
            conn.commit()
            continue

        chunks = chunk_sections(document.sections)
        if not chunks:
            parse_failures += 1
            logger.warning("No usable content in %s", path)
            repo.log_ingestion_error(
                conn, run_id, document.source_path, "parse", "produced zero chunks"
            )
            conn.commit()
            continue

        result = enrich_document(document, use_llm=use_llm)
        if result.fell_back:
            enrichment_failures += 1
            repo.log_ingestion_error(
                conn, run_id, document.source_path, "enrich", result.error or "unknown"
            )

        try:
            vectors = embed([c.text for c in chunks])
            repo.persist_document(conn, document, result, chunks, vectors)
        except Exception as exc:  # noqa: BLE001
            parse_failures += 1
            logger.error("Persist failed for %s: %s", path, exc)
            repo.log_ingestion_error(
                conn, run_id, document.source_path, "persist", f"{type(exc).__name__}: {exc}"
            )
            conn.rollback()
            continue

        repo.log_enrichment(conn, run_id, document.source_path, result)
        conn.commit()

        doc_count += 1
        chunk_count += len(chunks)
        confidences.append(result.confidence)
        logger.info(
            "%-55s %-10s %2d chunks  conf=%.2f  %s",
            document.source_path,
            document.source_type,
            len(chunks),
            result.confidence,
            result.method,
        )

    repo.rebuild_fts(conn)
    duration_ms = int((time.perf_counter() - started) * 1000)
    repo.finish_ingestion_run(
        conn, run_id, doc_count, chunk_count, parse_failures,
        enrichment_failures, confidences, duration_ms,
    )
    conn.commit()
    conn.close()

    summary = {
        "run_id": run_id,
        "data_dir": str(data_dir),
        "db_path": str(db_path),
        "enrichment_method": method,
        "files_found": len(files),
        "documents": doc_count,
        "chunks": chunk_count,
        "parse_failures": parse_failures,
        "enrichment_fallbacks": enrichment_failures,
        "confidence_avg": round(sum(confidences) / len(confidences), 4) if confidences else None,
        "confidence_min": round(min(confidences), 4) if confidences else None,
        "confidence_max": round(max(confidences), 4) if confidences else None,
        "duration_ms": duration_ms,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest data/ into the SQLite knowledge base.")
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None, dest="db_path")
    parser.add_argument("--reset", action="store_true", help="Delete the DB file first.")
    parser.add_argument("--limit", type=int, default=None, help="Ingest only the first N files.")
    llm_group = parser.add_mutually_exclusive_group()
    llm_group.add_argument(
        "--llm", dest="use_llm", action="store_true", default=None,
        help="Force Claude enrichment (fails if ANTHROPIC_API_KEY is unset).",
    )
    llm_group.add_argument(
        "--no-llm", dest="use_llm", action="store_false",
        help="Force the deterministic heuristic fallback.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-7s %(message)s",
    )

    summary = run(
        data_dir=args.data_dir,
        db_path=args.db_path,
        use_llm=args.use_llm,
        reset=args.reset,
        limit=args.limit,
    )

    print("\nIngestion summary")
    print("-" * 52)
    for key, value in summary.items():
        print(f"  {key:<24} {value}")
    if summary["files_found"] == 0:
        print(
            f"\n  No ingestible files under {summary['data_dir']}."
            "\n  Expected data/transcripts/*.md and data/office/*.docx|pptx|xlsx."
        )


if __name__ == "__main__":
    main()
