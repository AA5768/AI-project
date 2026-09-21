"""POST /query -- the core endpoint (PROJECT_INSTRUCTIONS.md Part 2 section 1).

The response shape is identical whether the winning chunk came from a
transcript or a spreadsheet, and whether the query was answered or routed: the
caller reads `confidence`, then `answer`/`citations` or `routing`. Nothing about
the source format leaks into the contract.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import db
from app.config import settings
from app.query.service import answer_query

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=8, ge=1, le=25)


class Citation(BaseModel):
    """A pointer into the corpus. Every field resolves to a stored row --
    `document_id` to `documents`, `chunk_id` to `chunks` -- so a client can
    always open the source behind a claim via GET /documents/{id}."""

    chunk_id: int
    document_id: int
    source_path: str
    source_type: str
    title: str | None = None
    author_or_attendees: list[str] = []
    anchor: str
    date: str | None = None
    excerpt: str
    score: float
    source_confidence: float
    quality_flags: list[str] = []


class Claim(BaseModel):
    """One sentence of the answer plus the citations it rests on, by index."""

    text: str
    citations: list[int] = []


class Routing(BaseModel):
    person: str
    person_id: int | None = None
    title: str | None = None
    department: str | None = None
    email: str | None = None
    role: str
    rationale: str
    matched_content: str
    matched_document_id: int | None = None
    matched_source_path: str | None = None
    matched_anchor: str | None = None
    draft_question: str
    reason: str
    gap_id: int | None = None


class QueryResponse(BaseModel):
    query_id: int
    answer: str | None = None
    confidence: float
    confidence_threshold: float
    confidence_breakdown: dict = {}
    claims: list[Claim] = []
    citations: list[Citation] = []
    derived_metadata: dict = {}
    routing: Routing | None = None
    gap_id: int | None = None
    latency_ms: int = 0


@router.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, conn: sqlite3.Connection = Depends(db)) -> QueryResponse:
    if not request.text.strip():
        raise HTTPException(status_code=422, detail="query text is empty")

    outcome = answer_query(conn, request.text, top_k=request.top_k)
    return QueryResponse(
        query_id=outcome.query_id,
        answer=outcome.answer,
        confidence=outcome.confidence,
        confidence_threshold=settings.confidence_threshold,
        confidence_breakdown=outcome.confidence_breakdown,
        claims=[Claim(**claim) for claim in outcome.claims],
        citations=[Citation(**citation) for citation in outcome.citations],
        derived_metadata=outcome.derived_metadata,
        routing=Routing(**outcome.routing) if outcome.routing else None,
        gap_id=outcome.gap_id,
        latency_ms=outcome.latency_ms,
    )
