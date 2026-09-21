"""Hybrid retrieval and the confidence signal that gates routing.

Runs against the shared miniature corpus with heuristic enrichment, so no API
key and no network beyond the cached embedding model.
"""

import pytest

from app.db.connection import get_connection
from app.retrieval.search import (
    RetrievedChunk,
    _fts_match_expression,
    compute_confidence,
    search,
)


@pytest.fixture(scope="module")
def conn(ingested_db):
    connection = get_connection(ingested_db)
    yield connection
    connection.close()


def _chunk(**overrides) -> RetrievedChunk:
    """A synthetic chunk for the pure-function confidence tests."""
    defaults = dict(
        chunk_id=1,
        document_id=1,
        chunk_index=0,
        text="text",
        source_anchor="line 1-2",
        source_path="data/transcripts/x.md",
        source_type="transcript",
        title="X",
        date="2026-03-04",
        attendees_or_author=["Priya Raman"],
        topic_domain="other",
        priority="medium",
        quality_flags=[],
        enrichment_confidence=0.8,
        semantic=0.8,
        keyword=0.5,
        score=0.7,
    )
    return RetrievedChunk(**{**defaults, **overrides})


# ------------------------------------------------------------------- retrieval


def test_semantic_arm_finds_a_paraphrase(conn):
    """No shared content word with the source, so only the vector arm can win."""
    results = search(conn, "why is the wafer robot gripper holding up the pilot?")
    assert results
    assert "standup.md" in results[0].source_path


def test_keyword_arm_finds_a_rare_literal_token(conn):
    results = search(conn, "SEV1")
    assert results
    assert "escalation.docx" in results[0].source_path
    assert results[0].keyword > 0


def test_results_are_ranked_by_fused_score(conn):
    results = search(conn, "telemetry ingestion lag")
    scores = [chunk.score for chunk in results]
    assert scores == sorted(scores, reverse=True)


def test_every_result_carries_its_traceability_fields(conn):
    for chunk in search(conn, "end effector repeatability"):
        assert chunk.source_path.startswith("data/")
        assert chunk.source_anchor
        assert chunk.document_id > 0
        assert 0.0 <= chunk.semantic <= 1.0


def test_top_k_is_respected(conn):
    assert len(search(conn, "wafer", top_k=2)) == 2


def test_empty_query_returns_nothing(conn):
    assert search(conn, "   ") == []


@pytest.mark.parametrize(
    "query",
    ['Helios-3 AND "unterminated', "NOT OR AND", "what about 2026-03-04?", "*", "-- drop"],
)
def test_operator_characters_do_not_break_the_keyword_arm(conn, query):
    """FTS5 treats bare AND/NOT/*/- as syntax; quoting every token stops a user's
    punctuation from turning into a 500."""
    search(conn, query)  # must not raise


def test_fts_expression_quotes_every_token():
    # Single characters are dropped as noise; everything else is quoted, so no
    # token can be read as an FTS operator.
    assert _fts_match_expression('Helios-3 AND "x"') == '"Helios-3" OR "AND"'
    assert _fts_match_expression("SEMI S2 spec") == '"SEMI" OR "S2" OR "spec"'
    assert _fts_match_expression("!!!") == ""


# ------------------------------------------------------------------ confidence


def test_off_topic_question_scores_far_below_an_answerable_one(conn):
    answerable = compute_confidence(search(conn, "what is blocking the end effector pilot?"))
    off_topic = compute_confidence(search(conn, "what is our parental leave policy in Portugal?"))
    assert off_topic.value < 0.4 < answerable.value
    assert off_topic.reasons  # and it can say why


def test_confidence_is_zero_with_no_chunks():
    signal = compute_confidence([])
    assert signal.value == 0.0
    assert signal.reasons


def test_low_quality_sources_drag_confidence_down():
    """Same retrieval, different source quality: the scratch-file version of an
    answer must not be as trusted as the attributed one."""
    trusted = [_chunk(chunk_id=1, enrichment_confidence=0.9)]
    untrusted = [_chunk(chunk_id=1, enrichment_confidence=0.25, quality_flags=["sparse"])]
    assert compute_confidence(untrusted).value < compute_confidence(trusted).value


def test_corroboration_rewards_agreement_across_documents():
    one_document = [_chunk(chunk_id=i, document_id=1) for i in range(3)]
    three_documents = [_chunk(chunk_id=i, document_id=i) for i in range(3)]
    assert compute_confidence(one_document).corroboration < 1.0
    assert compute_confidence(three_documents).corroboration == 1.0
    assert compute_confidence(one_document).value < compute_confidence(three_documents).value


def test_single_source_is_reported_as_a_reason():
    signal = compute_confidence([_chunk(document_id=1)])
    assert any("only one document" in reason for reason in signal.reasons)


def test_breakdown_is_serialisable_and_bounded(conn):
    signal = compute_confidence(search(conn, "what is blocking the end effector pilot?"))
    payload = signal.as_dict()
    assert set(payload) >= {"value", "top_similarity", "support", "corroboration", "source_trust"}
    assert all(0.0 <= payload[key] <= 1.0 for key in ("value", "top_similarity", "source_trust"))
