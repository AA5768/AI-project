"""End-to-end ingestion: data/ -> populated SQLite with intact traceability.

This is Part 1's exit criteria expressed as assertions. Runs with --no-llm so it
needs no API key and no network beyond the cached embedding model.
"""

import json

import pytest

from app.db.connection import get_connection
from app.db.repository import resolve_person, upsert_person
from app.enrichment.enrich import score_confidence
from app.enrichment.heuristics import enrich_heuristically
from app.ingestion.parsers.transcript_parser import parse_transcript
from app.ingestion.pipeline import run


@pytest.fixture(scope="module")
def _model_warm():
    """Loading the embedding model is the slow part; do it once per module."""
    from app.retrieval.embeddings import get_model

    get_model()


@pytest.fixture
def ingested(tmp_path, corpus, _model_warm):
    db = tmp_path / "test.db"
    summary = run(data_dir=corpus, db_path=db, use_llm=False, reset=True)
    conn = get_connection(db)
    yield summary, conn
    conn.close()


def test_every_file_is_ingested(ingested):
    summary, _ = ingested
    assert summary["files_found"] == 5
    assert summary["documents"] == 5
    assert summary["parse_failures"] == 0
    assert summary["chunks"] > 5


def test_source_paths_are_repo_relative_posix(ingested):
    _, conn = ingested
    paths = [r["source_path"] for r in conn.execute("SELECT source_path FROM documents")]
    assert all("\\" not in p for p in paths), paths
    assert all(p.startswith("data/") for p in paths), paths


def test_every_chunk_resolves_to_a_document_and_an_anchor(ingested):
    _, conn = ingested
    orphans = conn.execute(
        "SELECT COUNT(*) FROM chunks c LEFT JOIN documents d ON d.id = c.document_id "
        "WHERE d.id IS NULL OR TRIM(COALESCE(c.source_anchor, '')) = ''"
    ).fetchone()[0]
    assert orphans == 0


def test_both_retrieval_indexes_cover_every_chunk(ingested):
    _, conn = ingested
    chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    assert conn.execute("SELECT COUNT(*) FROM chunk_vectors").fetchone()[0] == chunks
    assert conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == chunks
    assert conn.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL").fetchone()[0] == 0


def test_vector_search_returns_the_relevant_chunk(ingested):
    from app.retrieval.embeddings import embed_one, serialize

    _, conn = ingested
    vector = serialize(embed_one("why did the end effector pilot slip?"))
    rows = conn.execute(
        "SELECT v.chunk_id, d.source_path FROM chunk_vectors v "
        "JOIN chunks c ON c.id = v.chunk_id JOIN documents d ON d.id = c.document_id "
        "WHERE v.embedding MATCH ? AND k = 3 ORDER BY v.distance",
        (vector,),
    ).fetchall()
    assert rows
    assert "standup.md" in rows[0]["source_path"]


def test_keyword_search_returns_the_relevant_chunk(ingested):
    _, conn = ingested
    rows = conn.execute(
        "SELECT d.source_path FROM chunks_fts JOIN chunks c ON c.id = chunks_fts.rowid "
        "JOIN documents d ON d.id = c.document_id WHERE chunks_fts MATCH ? "
        "ORDER BY bm25(chunks_fts) LIMIT 1",
        ("telemetry AND SLA",),
    ).fetchall()
    assert rows and "escalation.docx" in rows[0]["source_path"]


def test_citation_chain_reaches_a_named_person(ingested):
    _, conn = ingested
    row = conn.execute(
        "SELECT d.source_path, d.attendees_or_author, c.source_anchor "
        "FROM chunks c JOIN documents d ON d.id = c.document_id "
        "WHERE d.source_path LIKE '%standup%' LIMIT 1"
    ).fetchone()
    assert "Priya Raman" in json.loads(row["attendees_or_author"])
    assert row["source_anchor"]


def test_people_directory_enriches_titles(ingested):
    _, conn = ingested
    row = conn.execute("SELECT title, department FROM people WHERE name = 'Priya Raman'").fetchone()
    assert row["title"] == "VP Engineering"
    assert row["department"] == "Engineering"


def test_no_phantom_half_name_people(ingested):
    _, conn = ingested
    names = {r["name"] for r in conn.execute("SELECT name FROM people")}
    # "Dana will produce an RCA" must resolve onto the attendee, not create "Dana".
    assert "Dana Okafor" in names
    assert "Dana" not in names


def test_reingest_is_idempotent(tmp_path, corpus, _model_warm):
    db = tmp_path / "idem.db"
    first = run(data_dir=corpus, db_path=db, use_llm=False, reset=True)
    second = run(data_dir=corpus, db_path=db, use_llm=False, reset=False)
    assert first["documents"] == second["documents"]

    conn = get_connection(db)
    try:
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] == first["documents"]
        chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        assert chunks == second["chunks"]
        # Vector rows must not accumulate: vec0 is not covered by ON DELETE CASCADE.
        assert conn.execute("SELECT COUNT(*) FROM chunk_vectors").fetchone()[0] == chunks
        assert conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0] == chunks
        # Both runs are retained for trending.
        assert conn.execute("SELECT COUNT(*) FROM ingestion_runs").fetchone()[0] == 2
    finally:
        conn.close()


def test_instrumentation_rows_are_written(ingested):
    summary, conn = ingested
    run_row = conn.execute(
        "SELECT * FROM ingestion_runs WHERE id = ?", (summary["run_id"],)
    ).fetchone()
    assert run_row["finished_at"] is not None
    assert run_row["doc_count"] == 5
    assert run_row["enrichment_confidence_avg"] is not None
    assert run_row["duration_ms"] >= 0
    assert conn.execute("SELECT COUNT(*) FROM enrichment_log").fetchone()[0] == 5


def test_sparse_document_scores_below_a_substantive_one(ingested):
    _, conn = ingested
    sparse = conn.execute(
        "SELECT enrichment_confidence, quality_flags FROM documents "
        "WHERE source_path LIKE '%sparse%'"
    ).fetchone()
    standup = conn.execute(
        "SELECT enrichment_confidence FROM documents WHERE source_path LIKE '%standup%'"
    ).fetchone()
    assert sparse["enrichment_confidence"] < standup["enrichment_confidence"]
    flags = json.loads(sparse["quality_flags"])
    assert "sparse" in flags and "unattributed" in flags


def test_heuristic_confidence_is_capped_below_llm_confidence(corpus):
    doc = parse_transcript(corpus / "transcripts" / "standup.md")
    enrichment = enrich_heuristically(doc)
    heuristic = score_confidence(doc, enrichment, "heuristic")
    llm = score_confidence(doc, enrichment, "llm")
    assert heuristic < llm
    assert 0.0 < heuristic <= 1.0


def test_resolve_person_refuses_to_guess_between_two_matches(tmp_path):
    from app.db.connection import init_db

    db = tmp_path / "people.db"
    init_db(db)
    conn = get_connection(db)
    try:
        upsert_person(conn, "Dana Okafor")
        assert resolve_person(conn, "Dana") == resolve_person(conn, "Dana Okafor")

        upsert_person(conn, "Dana Whitfield")
        ambiguous = resolve_person(conn, "Dana")
        assert conn.execute(
            "SELECT name FROM people WHERE id = ?", (ambiguous,)
        ).fetchone()["name"] == "Dana"
    finally:
        conn.close()


def test_empty_data_dir_produces_a_clean_empty_run(tmp_path, _model_warm):
    empty = tmp_path / "empty"
    empty.mkdir()
    summary = run(data_dir=empty, db_path=tmp_path / "e.db", use_llm=False, reset=True)
    assert summary["files_found"] == 0
    assert summary["documents"] == 0
    assert summary["confidence_avg"] is None
