"""The second confidence gate: what happens to a drafted answer whose citations
do not check out.

The model is stubbed rather than called, so these pin the grounding rules
themselves -- the part that decides whether a fluent paragraph about the right
topic is allowed to be shown as an answer.
"""

import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.query import synthesis
from app.query.synthesis import (
    AnswerDraft,
    SynthesizedAnswer,
    SynthesizedClaim,
    _extractive,
    synthesize,
)
from app.retrieval.search import ConfidenceSignal, RetrievedChunk


def _chunk(chunk_id: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=chunk_id,
        chunk_index=0,
        text=f"Chunk {chunk_id}. The pilot slipped. A second sentence. A third.",
        source_anchor=f"line {chunk_id}",
        source_path=f"data/transcripts/{chunk_id}.md",
        source_type="transcript",
        title="T",
        date="2026-03-04",
        attendees_or_author=["Priya Raman"],
        topic_domain="other",
        priority="medium",
        quality_flags=[],
        enrichment_confidence=0.8,
        semantic=0.9,
        keyword=0.5,
        score=0.8,
    )


class _FakeResponse:
    def __init__(self, parsed):
        self.parsed_output = parsed
        self.stop_reason = "end_turn"


class _FakeClient:
    def __init__(self, parsed=None, error: Exception | None = None):
        self._parsed = parsed
        self._error = error
        self.messages = self

    def parse(self, **_kwargs):
        if self._error:
            raise self._error
        return _FakeResponse(self._parsed)


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")


def _stub(monkeypatch, parsed=None, error: Exception | None = None):
    monkeypatch.setattr(synthesis, "get_client", lambda: _FakeClient(parsed, error))


def test_valid_citations_are_mapped_to_chunk_ids(monkeypatch, with_key):
    chunks = [_chunk(11), _chunk(22)]
    _stub(
        monkeypatch,
        SynthesizedAnswer(
            answerable=True,
            claims=[
                SynthesizedClaim(text="The pilot slipped.", source_numbers=[1]),
                SynthesizedClaim(text="It was the gripper.", source_numbers=[2, 1]),
            ],
        ),
    )
    draft = synthesize("why did the pilot slip?", chunks)

    assert draft.answerable
    assert draft.support == 1.0
    assert draft.claims[0].chunk_ids == [11]
    assert draft.claims[1].chunk_ids == [22, 11]
    assert draft.answer == "The pilot slipped. It was the gripper."


def test_out_of_range_citations_are_dropped_and_counted(monkeypatch, with_key):
    _stub(
        monkeypatch,
        SynthesizedAnswer(
            answerable=True,
            claims=[
                SynthesizedClaim(text="Grounded.", source_numbers=[1]),
                SynthesizedClaim(text="Invented.", source_numbers=[9]),
            ],
        ),
    )
    draft = synthesize("q", [_chunk(11)])

    assert draft.dropped_citations == 1
    assert draft.claims[1].chunk_ids == []
    assert draft.support == 0.5  # half the answer is ungrounded


def test_a_wholly_ungrounded_answer_is_not_answerable(monkeypatch, with_key):
    _stub(
        monkeypatch,
        SynthesizedAnswer(
            answerable=True,
            claims=[SynthesizedClaim(text="Invented.", source_numbers=[42])],
        ),
    )
    draft = synthesize("q", [_chunk(11)])

    assert draft.answerable is False
    assert draft.answer is None
    assert draft.support == 0.0


def test_model_saying_it_cannot_answer_is_respected(monkeypatch, with_key):
    _stub(monkeypatch, SynthesizedAnswer(answerable=False, claims=[], caveat="not stated"))
    draft = synthesize("q", [_chunk(11)])

    assert draft.answerable is False
    assert draft.answer is None
    assert draft.caveat == "not stated"


def test_model_failure_degrades_to_the_extractive_path(monkeypatch, with_key):
    _stub(monkeypatch, error=RuntimeError("overloaded"))
    draft = synthesize("q", [_chunk(11)])

    assert draft.method == "extractive"
    assert draft.answer
    assert "overloaded" in draft.error
    assert draft.support < 1.0  # and it does not claim full confidence


def test_extractive_answer_is_verbatim_source_text():
    chunk = _chunk(11)
    draft = _extractive("q", [chunk])
    assert draft.answer in chunk.text
    assert draft.claims[0].chunk_ids == [11]


def test_no_chunks_means_no_answer():
    draft = synthesize("q", [])
    assert draft.answerable is False
    assert draft.support == 0.0


def test_an_unanswerable_draft_routes_even_at_a_zero_threshold(
    ingested_db, tmp_path, monkeypatch, with_key
):
    """Gate 2 in the wiring: retrieval can be as confident as you like, but an
    answer the sources do not support still goes to a human."""
    db = tmp_path / "gate2.db"
    shutil.copy(ingested_db, db)
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "confidence_threshold", 0.0)
    _stub(monkeypatch, SynthesizedAnswer(answerable=False, claims=[]))

    with TestClient(app) as client:
        body = client.post("/query", json={"text": "what is blocking the end effector pilot?"}).json()

    assert body["answer"] is None
    assert body["routing"]["person"]
    assert "do not answer the question" in body["routing"]["reason"]


def test_routing_reason_distinguishes_the_two_gates(monkeypatch):
    """Which gate failed decides where a reviewer should look.

    Gate 1 means the corpus is thin on the topic; gate 2 means the corpus had
    the material and the draft misused it. Both end up below the same
    threshold, and the reason text used to describe either as "retrieval
    confidence N is below the threshold" -- which labels the post-grounding
    number as a retrieval score and sends the reviewer after the wrong thing.
    """
    from app.query.service import _routing_reason

    monkeypatch.setattr(settings, "confidence_threshold", 0.55)
    signal = ConfidenceSignal(value=0.81, reasons=[])

    gate_one = _routing_reason(ConfidenceSignal(value=0.32, reasons=[]), 0.32, None)
    assert gate_one == "Retrieval confidence 0.32 is below the 0.55 threshold."

    unanswerable = _routing_reason(signal, 0.28, AnswerDraft(answerable=False, answer=None, support=0.0))
    assert "do not answer the question" in unanswerable

    discounted = _routing_reason(
        signal, 0.28, AnswerDraft(answerable=True, answer="a", support=0.0)
    )
    assert "only partly supported" in discounted
    # Both numbers named, so 0.28 cannot be mistaken for the retrieval score.
    assert "from 0.81 to 0.28" in discounted
