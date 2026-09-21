"""Answer synthesis with per-claim citation mapping (PROJECT_INSTRUCTIONS.md
Part 2 section 1).

The model is asked for a list of claims, each carrying the chunk ids it came
from, rather than for prose with citation markers to be parsed out afterwards.
Two things fall out of that:

  - every sentence shown to a user is individually traceable to rows in
    `chunks`, so the UI can highlight a claim and open its source;
  - a claim whose chunk ids are not in the retrieved set is detectably
    ungrounded. The fraction that survives that check is the second half of the
    confidence score, which is what stops a fluent answer about the right topic
    from passing as an answer to the question actually asked.

No API key is not a failure mode: the extractive fallback returns the best
matching passage verbatim, which is still a citable answer, and scores itself
lower.
"""

import logging
import re
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.config import settings
from app.query.claude import get_client
from app.retrieval.search import RetrievedChunk

logger = logging.getLogger(__name__)

# Extractive answers are real source text, so they are fully grounded, but they
# are a quoted passage rather than an answer to the question. The discount keeps
# a keyless deployment honest instead of letting it report full confidence.
EXTRACTIVE_SUPPORT = 0.75

MAX_CHUNK_CHARS = 1800

SYSTEM_PROMPT = """You answer questions about internal documents at Meridian \
Microsystems, a ~120-person semiconductor equipment automation company, using \
ONLY the numbered sources supplied with each question.

Rules:
- Every claim must come from the sources. Never use outside knowledge, and never
  fill a gap with something plausible.
- Each claim must list the source numbers it is drawn from. A claim with no
  source is not allowed; split a sentence rather than leave part of it uncited.
- `answerable` is about the question, not the topic. Set it false, with no
  claims, whenever the sources do not state the answer -- including when they
  discuss the subject at length, record the answer as an open question, or give
  an estimate or an adjacent figure instead. Never write an answer that
  describes what the sources fail to say; that question belongs with a person,
  and saying so is the correct outcome, not a failure.
- The sources disagree with each other sometimes. When they do, prefer the more
  recent and the higher-confidence one, say which you used, and record the
  disagreement in `caveat` naming both sources. Do not silently average them.
- Note in `caveat` when the only supporting source is marked stale, draft, or
  sparse.
- Be specific and brief: numbers, dates and names as the source states them.
  Two to five claims is typical. No preamble, no restating the question."""


class SynthesizedClaim(BaseModel):
    text: str = Field(
        description="One self-contained sentence of the answer, stated as fact."
    )
    source_numbers: list[int] = Field(
        description="The numbers of the sources this sentence is drawn from. Never empty."
    )


class SynthesizedAnswer(BaseModel):
    answerable: bool = Field(
        description="True only if the sources actually answer the question asked."
    )
    claims: list[SynthesizedClaim] = Field(
        default_factory=list,
        description="The answer, one sentence per claim, in reading order. Empty if not answerable.",
    )
    caveat: str | None = Field(
        default=None,
        description=(
            "One sentence naming a conflict between sources, or a staleness/draft "
            "warning, that a reader needs in order to use this answer safely. "
            "Null when there is nothing to warn about."
        ),
    )


@dataclass
class Claim:
    text: str
    chunk_ids: list[int]


@dataclass
class AnswerDraft:
    """What synthesis produced, plus how much of it survived grounding."""

    answerable: bool
    answer: str | None
    claims: list[Claim] = field(default_factory=list)
    caveat: str | None = None
    support: float = 0.0  # 0..1, the grounded fraction, method-discounted
    method: str = "llm"  # llm | extractive
    model: str | None = None
    dropped_citations: int = 0
    error: str | None = None


def _format_sources(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for number, chunk in enumerate(chunks, start=1):
        flags = ", ".join(chunk.quality_flags) or "none"
        people = ", ".join(chunk.attendees_or_author) or "(not recorded in the file)"
        text = chunk.text[:MAX_CHUNK_CHARS]
        blocks.append(
            f"[{number}] {chunk.source_path} ({chunk.source_type}) | {chunk.source_anchor}\n"
            f"    date: {chunk.date or 'unknown'} | author/attendees: {people}\n"
            f"    source quality flags: {flags} | source confidence: "
            f"{chunk.enrichment_confidence:.2f}\n"
            f"---\n{text}\n---"
        )
    return "\n\n".join(blocks)


def _build_user_prompt(query_text: str, chunks: list[RetrievedChunk]) -> str:
    return (
        f"Question: {query_text}\n\n"
        f"Sources ({len(chunks)}, ordered by retrieval score, most relevant first):\n\n"
        f"{_format_sources(chunks)}"
    )


def _ground(
    parsed: SynthesizedAnswer, chunks: list[RetrievedChunk]
) -> tuple[list[Claim], int]:
    """Map source numbers back to real chunk ids, dropping anything invented.

    The model is given 1-based positions, not chunk ids, so a hallucinated
    citation is almost always an out-of-range number -- cheap to detect and
    impossible to confuse with a valid row.
    """
    claims: list[Claim] = []
    dropped = 0
    for claim in parsed.claims:
        chunk_ids = []
        for number in claim.source_numbers:
            if 1 <= number <= len(chunks):
                chunk_ids.append(chunks[number - 1].chunk_id)
            else:
                dropped += 1
        text = claim.text.strip()
        if text:
            claims.append(Claim(text=text, chunk_ids=list(dict.fromkeys(chunk_ids))))
    return claims, dropped


def _grounded_fraction(claims: list[Claim]) -> float:
    if not claims:
        return 0.0
    return sum(1 for claim in claims if claim.chunk_ids) / len(claims)


def _extractive(query_text: str, chunks: list[RetrievedChunk]) -> AnswerDraft:
    """Offline path: quote the best passage instead of writing prose about it."""
    if not chunks:
        return AnswerDraft(answerable=False, answer=None, method="extractive")

    top = chunks[0]
    # Two sentences is enough to be useful and short enough to stay verbatim.
    sentences = re.split(r"(?<=[.!?])\s+", top.text.strip())
    excerpt = " ".join(sentences[:2]).strip() or top.text[:400].strip()
    claim = Claim(text=excerpt, chunk_ids=[top.chunk_id])
    return AnswerDraft(
        answerable=True,
        answer=excerpt,
        claims=[claim],
        caveat=(
            "Extracted verbatim from the best-matching passage: no API key is "
            "configured, so this answer was not synthesised across sources."
        ),
        support=EXTRACTIVE_SUPPORT,
        method="extractive",
    )


def _synthesize_with_llm(query_text: str, chunks: list[RetrievedChunk]) -> AnswerDraft:
    response = get_client().messages.parse(
        model=settings.synthesis_model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(query_text, chunks)}],
        output_format=SynthesizedAnswer,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError(f"model returned no parseable output (stop_reason={response.stop_reason})")

    claims, dropped = _ground(parsed, chunks)
    grounded = _grounded_fraction(claims)
    answerable = parsed.answerable and bool(claims) and grounded > 0
    answer = " ".join(claim.text for claim in claims) if claims else None

    return AnswerDraft(
        answerable=answerable,
        answer=answer if answerable else None,
        claims=claims if answerable else [],
        caveat=parsed.caveat,
        support=grounded if answerable else 0.0,
        method="llm",
        model=settings.synthesis_model,
        dropped_citations=dropped,
    )


def synthesize(query_text: str, chunks: list[RetrievedChunk]) -> AnswerDraft:
    """Draft an answer from retrieved chunks, or report that they do not answer.

    Falls back to the extractive path on any model failure, for the same reason
    enrichment does: one bad call should degrade the answer, not 500 the query.
    """
    if not chunks:
        return AnswerDraft(answerable=False, answer=None, support=0.0)

    if not settings.has_api_key:
        return _extractive(query_text, chunks)

    try:
        return _synthesize_with_llm(query_text, chunks)
    except Exception as exc:  # noqa: BLE001 - degrade, never fail the query
        logger.warning("synthesis failed for %r: %s", query_text[:80], exc)
        draft = _extractive(query_text, chunks)
        draft.error = f"{type(exc).__name__}: {exc}"
        draft.caveat = (
            "Extracted verbatim from the best-matching passage: answer synthesis "
            "failed, so sources were not compared."
        )
        return draft
