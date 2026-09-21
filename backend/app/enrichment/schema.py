"""Structured shape of per-document derived metadata.

This is the contract in both directions: the LLM is constrained to emit it
(via output_config json_schema), and the heuristic fallback constructs the same
object, so persistence and the query API never need to know which path ran.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.enrichment.taxonomy import PRIORITIES, QUALITY_FLAGS, TOPIC_DOMAINS

# Built from the taxonomy so the controlled vocabulary is declared once. These
# become `enum` in the JSON schema the SDK sends, which makes the constraint the
# model's problem rather than something we clean up afterwards -- `_coerce` in
# enrich.py stays as defence in depth for the heuristic path and schema drift.
TopicDomain = Literal[tuple(TOPIC_DOMAINS)]  # type: ignore[valid-type]
Priority = Literal[tuple(PRIORITIES)]  # type: ignore[valid-type]
QualityFlag = Literal[tuple(QUALITY_FLAGS)]  # type: ignore[valid-type]


class DerivedDecision(BaseModel):
    text: str = Field(description="The decision, stated as a complete sentence.")
    decided_by: str | None = Field(
        default=None,
        description="Name of the person who made the call, only if the source names them.",
    )
    # Required of the model (no default) but nullable, because grounding clears
    # any quote it cannot locate in the source rather than persisting it.
    evidence: str | None = Field(
        description=(
            "A short verbatim quote, copied exactly from the document, containing "
            "this decision. It must be one continuous span -- do not join separate "
            "passages with an ellipsis."
        )
    )


class DerivedActionItem(BaseModel):
    text: str = Field(description="What needs to be done, as a complete sentence.")
    owner: str | None = Field(
        default=None, description="Name of the owner, only if the source names them."
    )
    due_date: str | None = Field(
        default=None,
        description="Due date exactly as written in the source (e.g. 'end of Q3', '2026-04-14').",
    )
    evidence: str | None = Field(
        description=(
            "A short verbatim quote, copied exactly from the document, containing "
            "this action item. It must be one continuous span -- do not join "
            "separate passages with an ellipsis."
        )
    )


class DocumentEnrichment(BaseModel):
    topic_domain: TopicDomain = Field(description="The single best-fitting domain.")
    priority: Priority = Field(
        description="How urgent the content is. Use 'unspecified' when the source gives no signal."
    )
    summary: str = Field(description="Two to four sentences. No preamble.")
    decisions: list[DerivedDecision] = Field(default_factory=list)
    action_items: list[DerivedActionItem] = Field(default_factory=list)
    quality_flags: list[QualityFlag] = Field(
        default_factory=list,
        description="Every flag that applies to this document; empty list if none do.",
    )
    source_quality: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "How well this document supports confident answers: 1.0 = specific, "
            "attributed, internally consistent; 0.2 = vague, undated, or "
            "self-contradictory."
        ),
    )


class EnrichmentResult(BaseModel):
    """What the pipeline persists: the derived metadata plus how it was produced."""

    enrichment: DocumentEnrichment
    method: str  # llm | heuristic
    model: str | None = None
    confidence: float
    fell_back: bool = False
    error: str | None = None
