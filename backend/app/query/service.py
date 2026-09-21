"""The query pipeline: retrieve -> score -> answer or route -> log.

One function owns the order of operations so that every query, answered or
routed, leaves the same trail: a `query_log` row with the confidence that was
actually computed, and a `gaps` row whenever a human was asked instead. Routing
is not a special case bolted on the side -- it is the branch this function takes
when its own confidence says the corpus cannot support an answer.

Source type is invisible here on purpose (PROJECT_INSTRUCTIONS.md Part 2
section 6): a transcript chunk and a spreadsheet cell range go through the same
thresholds and come back in the same shape.
"""

import logging
import time
from dataclasses import dataclass, field

from app.config import settings
from app.db import repository
from app.query import routing as routing_module
from app.query.synthesis import AnswerDraft, synthesize
from app.retrieval.search import (
    ConfidenceSignal,
    RetrievedChunk,
    compute_confidence,
    is_confident,
    search,
)

logger = logging.getLogger(__name__)

TOP_K = 8

# Citations shown alongside a routed query: what the system did look at, so a
# reviewer can judge the routing decision rather than take it on trust.
ROUTED_CITATION_COUNT = 3

EXCERPT_CHARS = 700

# Retrieval confidence measures whether the corpus holds evidence on the topic;
# the grounded fraction of the drafted answer measures whether that evidence
# answers the question. Multiplying keeps both necessary: a fully grounded
# answer keeps its retrieval score, an ungrounded one keeps a third of it.
UNGROUNDED_FLOOR = 0.35

_PRIORITY_ORDER = {"high": 3, "medium": 2, "low": 1, "unspecified": 0}


@dataclass
class QueryOutcome:
    query_id: int
    answer: str | None
    confidence: float
    confidence_breakdown: dict
    claims: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    derived_metadata: dict = field(default_factory=dict)
    routing: dict | None = None
    gap_id: int | None = None
    latency_ms: int = 0


def _citation(chunk: RetrievedChunk) -> dict:
    """The citation shape. Every field is read off a real row -- nothing here is
    derived by a model, which is what makes a citation checkable."""
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "source_path": chunk.source_path,
        "source_type": chunk.source_type,
        "title": chunk.title,
        "author_or_attendees": chunk.attendees_or_author,
        "anchor": chunk.source_anchor,
        "date": chunk.date,
        "excerpt": chunk.text[:EXCERPT_CHARS],
        "score": chunk.score,
        "source_confidence": chunk.enrichment_confidence,
        "quality_flags": chunk.quality_flags,
    }


def _build_citations(
    chunks: list[RetrievedChunk], draft: AnswerDraft | None
) -> tuple[list[dict], list[dict]]:
    """Citations plus claims rewritten to index into them.

    Claims carry positions in the citation list rather than chunk ids so the UI
    can render "[1]" markers without a second lookup; the chunk id stays on the
    citation itself for anyone who needs the row.
    """
    by_id = {chunk.chunk_id: chunk for chunk in chunks}
    cited_ids: list[int] = []
    if draft is not None:
        for claim in draft.claims:
            for chunk_id in claim.chunk_ids:
                if chunk_id in by_id and chunk_id not in cited_ids:
                    cited_ids.append(chunk_id)

    if not cited_ids:
        cited_ids = [chunk.chunk_id for chunk in chunks[:ROUTED_CITATION_COUNT]]

    ordered = sorted((by_id[i] for i in cited_ids), key=lambda c: -c.score)
    citations = [_citation(chunk) for chunk in ordered]
    position = {chunk.chunk_id: index for index, chunk in enumerate(ordered)}

    claims = []
    if draft is not None:
        claims = [
            {
                "text": claim.text,
                "citations": [position[i] for i in claim.chunk_ids if i in position],
            }
            for claim in draft.claims
        ]
    return citations, claims


def _derived_metadata(
    chunks: list[RetrievedChunk], citations: list[dict], draft: AnswerDraft | None
) -> dict:
    """Document-level metadata for the cited sources -- the badges the UI shows.

    Read off `documents`, not re-derived at query time, so what the answer is
    labelled with is the same enrichment Part 1 persisted.
    """
    cited_document_ids = {citation["document_id"] for citation in citations}
    documents = [c for c in chunks if c.document_id in cited_document_ids]
    seen: dict[int, RetrievedChunk] = {}
    for chunk in documents:
        seen.setdefault(chunk.document_id, chunk)
    unique = list(seen.values())

    # Weighted by retrieval score, not counted: the badge should say what the
    # answer mostly rests on, and three weak sources should not outvote the one
    # the answer actually came from.
    domains: dict[str, float] = {}
    for chunk in unique:
        if chunk.topic_domain:
            domains[chunk.topic_domain] = domains.get(chunk.topic_domain, 0.0) + chunk.score

    priorities = [c.priority for c in unique if c.priority]
    dates = sorted(c.date for c in unique if c.date)

    return {
        "topic_domain": max(domains, key=lambda d: domains[d]) if domains else None,
        "topic_domains": sorted(domains, key=lambda d: -domains[d]),
        "priority": max(priorities, key=lambda p: _PRIORITY_ORDER.get(p, 0))
        if priorities
        else None,
        "source_types": sorted({c.source_type for c in unique}),
        "quality_flags": sorted({flag for c in unique for flag in c.quality_flags}),
        "date_range": {"earliest": dates[0], "latest": dates[-1]} if dates else None,
        "documents": [
            {
                "document_id": c.document_id,
                "source_path": c.source_path,
                "title": c.title,
                "date": c.date,
                "topic_domain": c.topic_domain,
                "priority": c.priority,
                "enrichment_confidence": c.enrichment_confidence,
                "quality_flags": c.quality_flags,
            }
            for c in unique
        ],
        "retrieved_chunks": len(chunks),
        "answer_method": draft.method if draft else None,
        "answer_model": draft.model if draft else None,
        "answer_support": round(draft.support, 4) if draft else 0.0,
        "caveat": draft.caveat if draft else None,
    }


def _grounding_multiplier(support: float) -> float:
    """What gate 2 does to the retrieval score: a fully grounded draft keeps it,
    a wholly ungrounded one keeps `UNGROUNDED_FLOOR` of it."""
    return UNGROUNDED_FLOOR + (1 - UNGROUNDED_FLOOR) * support


def _confidence_breakdown(signal: ConfidenceSignal, confidence: float, draft: AnswerDraft | None) -> dict:
    """The full derivation of the number the caller sees, both gates included.

    The retrieval signal alone cannot explain the final score: a query can
    retrieve well (`retrieval_confidence` 0.81) and still end up at 0.28 because
    the drafted answer turned out to be ungrounded. Reporting only the retrieval
    parts left the reader with two numbers and no term connecting them, so the
    grounding gate is spelled out here and `value` is the figure actually used:

        value = retrieval_confidence * grounding_multiplier

    `answer_support` and `grounding_multiplier` are None when retrieval fell
    short of the threshold on its own -- no draft was written, so grounding was
    never measured, and reporting 0.0 would read as "checked, found nothing".
    """
    grounded = draft is not None
    return {
        **signal.as_dict(),
        "value": confidence,
        "retrieval_confidence": signal.value,
        "answer_support": round(draft.support, 4) if grounded else None,
        "grounding_multiplier": round(_grounding_multiplier(draft.support), 4) if grounded else None,
        "ungrounded_floor": UNGROUNDED_FLOOR,
    }


def _routing_reason(signal: ConfidenceSignal, confidence: float, draft: AnswerDraft | None) -> str:
    threshold = settings.confidence_threshold
    if draft is None:
        # Gate 1: no draft was written, so `confidence` is still the retrieval score.
        head = (
            f"Retrieval confidence {confidence:.2f} is below the "
            f"{threshold:.2f} threshold"
        )
    elif not draft.answerable:
        head = (
            f"The retrieved sources are about this topic but do not answer the "
            f"question (confidence {confidence:.2f}, threshold {threshold:.2f})"
        )
    else:
        # Gate 2: the draft claimed an answer, but too little of it held up against
        # the sources. Naming both numbers keeps this from reading as a retrieval
        # failure, which is what the reader would otherwise assume.
        head = (
            f"The drafted answer was only partly supported by its sources, which "
            f"lowered confidence from {signal.value:.2f} to {confidence:.2f} "
            f"(threshold {threshold:.2f})"
        )
    detail = "; ".join(signal.reasons)
    return f"{head}: {detail}." if detail else f"{head}."


def _source_types(chunks: list[RetrievedChunk]) -> list[str]:
    return sorted({chunk.source_type for chunk in chunks})


def answer_query(conn, query_text: str, top_k: int = TOP_K) -> QueryOutcome:
    """Answer one question, or route it, and record what happened either way."""
    started = time.perf_counter()

    chunks = search(conn, query_text, top_k=top_k)
    signal = compute_confidence(chunks)

    draft: AnswerDraft | None = None
    confidence = signal.value

    # Gate 1 -- not enough evidence to be worth drafting anything. Routing here
    # costs no model call and produces no answer for anyone to be misled by.
    if is_confident(signal.value):
        draft = synthesize(query_text, chunks)
        # Gate 2 -- the draft's own grounding, mechanically checked in
        # synthesis.py, discounts the retrieval score.
        confidence = round(signal.value * _grounding_multiplier(draft.support), 4)

    answered = draft is not None and draft.answerable and is_confident(confidence)

    citations, claims = _build_citations(chunks, draft if answered else None)
    metadata = _derived_metadata(chunks, citations, draft)
    latency_ms = int((time.perf_counter() - started) * 1000)

    query_id = repository.log_query(
        conn,
        query_text=query_text,
        answer=draft.answer if answered else None,
        confidence=confidence,
        matched_chunk_ids=[citation["chunk_id"] for citation in citations],
        latency_ms=latency_ms,
        routed=not answered,
        source_types=_source_types(chunks),
    )

    outcome = QueryOutcome(
        query_id=query_id,
        answer=draft.answer if answered else None,
        confidence=confidence,
        confidence_breakdown=_confidence_breakdown(signal, confidence, draft),
        claims=claims,
        citations=citations,
        derived_metadata=metadata,
        latency_ms=latency_ms,
    )

    if answered:
        conn.commit()
        return outcome

    reason = _routing_reason(signal, confidence, draft)
    decision = routing_module.route(conn, query_text, chunks, signal, reason)

    outcome.gap_id = repository.record_gap(
        conn,
        query_id=query_id,
        reason=reason,
        suggested_routing_person=decision.person if decision else None,
        suggested_person_id=decision.person_id if decision else None,
        routing_rationale=decision.rationale if decision else None,
        matched_content=decision.matched_content if decision else None,
        draft_question=decision.draft_question if decision else None,
    )
    if decision is not None:
        outcome.routing = {**decision.as_dict(), "gap_id": outcome.gap_id}
    else:
        # Nothing matched well enough to name a person from the record. The gap
        # is still logged -- an unanswerable query with no obvious owner is the
        # most important thing on a review queue, not the least.
        outcome.derived_metadata["routing_unavailable"] = (
            "No document matched closely enough to identify someone the corpus "
            "connects to this question."
        )
    conn.commit()
    return outcome
