"""Who a routed query reaches, and when it should reach nobody.

Routing is the one place the system puts a real person's name on a guess, so
the interesting tests are the negative ones: the corpus is full of people, and
every query retrieves *something*, which means "name the person nearest the
best match" always has an answer and is almost always wrong for a question the
corpus does not cover.
"""

import pytest

from app.db.connection import get_connection
from app.query.routing import MIN_ATTRIBUTION_SIMILARITY, route
from app.retrieval.search import compute_confidence, search


@pytest.fixture(scope="module")
def conn(ingested_db):
    connection = get_connection(ingested_db)
    yield connection
    connection.close()


def _route(conn, query_text):
    chunks = search(conn, query_text)
    signal = compute_confidence(chunks)
    return route(conn, query_text, chunks, signal, reason="test"), chunks, signal


def test_a_question_the_corpus_covers_reaches_a_real_person(conn):
    decision, _, _ = _route(conn, "why is the end effector blocking the pilot?")
    assert decision is not None
    assert decision.person
    assert decision.matched_content
    # The rationale quotes the passage that chose them, not a summary of it.
    assert decision.matched_source_path


def test_the_quoted_passage_must_itself_be_about_the_question(conn):
    """The floor applies to the chunk the rationale is built from.

    route() checked the corpus-wide best similarity and then built its case on
    whichever chunk the chosen person scored highest on -- a different chunk.
    A query could clear the floor on one paragraph and be justified by another
    that was nowhere near it. On the real corpus this routed "what is our
    parental leave policy?" to the author of a test-cell integration spec,
    quoting a paragraph about open questions on a device handler.

    Ranking fuses keyword overlap with semantic similarity, so the chunk that
    leads can have a semantic similarity of zero: literal tokens like "what"
    and "we" are enough when nothing matches on meaning.
    """
    for off_topic in (
        "what is our parental leave policy?",
        "which firm audits our financial statements?",
        "how much holiday do engineers get?",
    ):
        decision, chunks, _ = _route(conn, off_topic)
        if decision is None:
            continue
        chunk = next(
            c for c in chunks if c.source_anchor == decision.matched_anchor
        )
        assert chunk.semantic >= MIN_ATTRIBUTION_SIMILARITY, (
            f"{off_topic!r} named {decision.person} from a passage at "
            f"similarity {chunk.semantic:.2f}"
        )


def test_no_routee_still_records_the_question(conn):
    """Declining to name someone is not declining to notice.

    route() returning None is what the caller turns into a gap with
    routing_unavailable; a question nobody owns is the most important row on a
    review queue, not a silent drop.
    """
    decision, chunks, signal = _route(conn, "what is our parental leave policy?")
    assert decision is None
    assert chunks, "retrieval still ran -- the gap has matched content to show"
    assert signal.value < 0.55
