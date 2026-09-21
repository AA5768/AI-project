"""Per-document derived metadata (PROJECT_INSTRUCTIONS.md Part 1 section 3).

Primary path is Claude Haiku with a constrained JSON schema. Attendees, authors
and dates are NOT sent to the model as things to produce -- they are parsed from
the file and passed in as context only, so the stored values stay verbatim and a
citation can never name someone the source doesn't.

Every document falls back to `heuristics.enrich_heuristically` on any failure,
and the fallback is recorded in the enrichment log rather than swallowed --
a run that quietly degraded to regexes is exactly the quality degradation Part 2's
/metrics endpoint is supposed to surface.
"""

import logging

from app.config import settings
from app.enrichment.grounding import ground_items
from app.enrichment.heuristics import enrich_heuristically
from app.enrichment.schema import DocumentEnrichment, EnrichmentResult
from app.enrichment.taxonomy import PRIORITIES, QUALITY_FLAGS, TOPIC_DOMAINS
from app.ingestion.common import Document

logger = logging.getLogger(__name__)

# Haiku's context is 200K; documents in this corpus are far smaller, but cap
# anyway so one pathological file can't blow up a batch run.
MAX_DOC_CHARS = 60_000

SYSTEM_PROMPT = f"""You extract structured metadata from internal documents at \
Meridian Microsystems, a ~120-person semiconductor equipment automation company \
(wafer-handling robots and EFEMs, a tri-temperature device test handler, and an \
equipment-connectivity/OEE SaaS).

Rules:
- Ground every field in the document text. Never infer facts that are not present.
- `evidence` must be a verbatim substring of the document, under 200 characters,
  copied character-for-character from ONE continuous passage. Never join two
  separate passages with an ellipsis, never merge lines from different speakers,
  and never tidy up the wording. A quote that cannot be found in the document is
  discarded, so a shorter exact quote is always better than a longer edited one.
- A decision is a choice that was actually made, not a proposal under discussion.
- An action item has something to be done. Only set `owner` if the document names
  the person; leave it null otherwise. Do not guess owners from context.
- topic_domain must be exactly one of: {", ".join(TOPIC_DOMAINS)}
- priority must be exactly one of: {", ".join(PRIORITIES)}
- quality_flags may contain any of: {", ".join(QUALITY_FLAGS)}
- Do NOT set `unattributed`. Whether the file records an author or attendees is
  determined mechanically from the file and will be applied for you.
- Be honest in `source_quality`. Documents that are vague, undated, stale, or
  self-contradictory should score low. This number gates whether downstream
  answers are trusted or escalated to a human, so inflating it causes real harm.
- If the document is too thin to support any answer, say so via the `sparse` flag
  and a low `source_quality` rather than inventing content."""


def _build_user_prompt(document: Document) -> str:
    people = ", ".join(document.attendees_or_author) or "(none recorded in the file)"
    body = document.raw_text[:MAX_DOC_CHARS]
    truncated = "\n[... truncated ...]" if len(document.raw_text) > MAX_DOC_CHARS else ""
    return (
        f"Source file: {document.source_path}\n"
        f"Source type: {document.source_type}\n"
        f"Title: {document.title or '(none)'}\n"
        f"Date recorded in file: {document.date or '(none)'}\n"
        f"Attendees/author recorded in file: {people}\n"
        f"(The people and date above are already stored verbatim. Do not restate "
        f"or correct them -- they are context for reading the document.)\n\n"
        f"--- DOCUMENT ---\n{body}{truncated}\n--- END DOCUMENT ---"
    )


def _coerce(enrichment: DocumentEnrichment) -> DocumentEnrichment:
    """Clamp model output to the controlled vocabularies rather than trusting it."""
    if enrichment.topic_domain not in TOPIC_DOMAINS:
        enrichment.topic_domain = "other"
    if enrichment.priority not in PRIORITIES:
        enrichment.priority = "unspecified"
    enrichment.quality_flags = [f for f in enrichment.quality_flags if f in QUALITY_FLAGS]
    return enrichment


def _ground_evidence(document: Document, enrichment: DocumentEnrichment) -> int:
    """Replace every quote with real source text. See enrichment/grounding.py."""
    _, dropped_d = ground_items(document.raw_text, enrichment.decisions)
    _, dropped_a = ground_items(document.raw_text, enrichment.action_items)
    total = dropped_d + dropped_a
    if total:
        logger.info(
            "%s: %d evidence quote(s) could not be located in the source and were dropped",
            document.source_path,
            total,
        )
    return total


def _apply_mechanical_flags(
    document: Document, enrichment: DocumentEnrichment
) -> DocumentEnrichment:
    """Own the flags that are facts about the file, not judgements about it.

    Whether a file records an author or attendees is knowable from the parse, and
    the model gets it wrong -- Haiku flagged a transcript with three named
    attendees as `unattributed`. Anything that feeds the confidence penalty needs
    to be right, so this flag is set here for both paths and never inherited.
    """
    flags = [f for f in enrichment.quality_flags if f != "unattributed"]
    if not document.attendees_or_author:
        flags.append("unattributed")
    enrichment.quality_flags = list(dict.fromkeys(flags))
    return enrichment


def _postprocess(document: Document, enrichment: DocumentEnrichment) -> DocumentEnrichment:
    """Everything that must hold regardless of which extraction path produced it."""
    _ground_evidence(document, enrichment)
    return _apply_mechanical_flags(document, enrichment)


def score_confidence(document: Document, enrichment: DocumentEnrichment, method: str) -> float:
    """How much to trust this document's derived metadata, on 0..1.

    Blends three independent signals so no single one can dominate:
      - the extraction method (a model reading prose beats regex cues),
      - how the model rated the source itself,
      - structural completeness of what came back.
    Part 2 folds this into query confidence, which is what gates routing.
    """
    base = 0.80 if method == "llm" else 0.40

    quality = enrichment.source_quality

    completeness = 0.0
    if len(enrichment.summary.strip()) > 60:
        completeness += 0.4
    if enrichment.decisions or enrichment.action_items:
        completeness += 0.3
    if document.attendees_or_author:
        completeness += 0.2
    if document.date:
        completeness += 0.1

    score = 0.45 * base + 0.35 * quality + 0.20 * completeness

    # Flags that mean "do not lean on this document".
    penalties = {"sparse": 0.20, "stale": 0.12, "contradictory": 0.10, "draft": 0.08,
                 "unattributed": 0.05}
    for flag in set(enrichment.quality_flags):
        score -= penalties.get(flag, 0.0)

    # Extraction that could not be tied back to the source text is a direct
    # signal that this document's metadata is less trustworthy. Run after
    # grounding, where unlocatable quotes have already been set to None.
    items = [*enrichment.decisions, *enrichment.action_items]
    if items:
        ungrounded = sum(1 for item in items if not item.evidence)
        score -= 0.25 * (ungrounded / len(items))

    return round(max(0.05, min(1.0, score)), 4)


def _enrich_with_llm(document: Document) -> DocumentEnrichment:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.parse(
        model=settings.enrichment_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_prompt(document)}],
        output_format=DocumentEnrichment,
    )
    parsed = response.parsed_output
    if parsed is None:
        raise ValueError(f"model returned no parseable output (stop_reason={response.stop_reason})")
    return _coerce(parsed)


def enrich_document(document: Document, use_llm: bool | None = None) -> EnrichmentResult:
    """Derive metadata for one document.

    `use_llm=None` means "use the LLM if a key is configured". Pass True/False to
    force a path -- the ingestion CLI exposes this as --llm / --no-llm.
    """
    should_use_llm = settings.has_api_key if use_llm is None else use_llm

    if should_use_llm:
        if not settings.has_api_key:
            raise RuntimeError(
                "LLM enrichment requested but ANTHROPIC_API_KEY is empty. "
                "Set it in .env, or run with --no-llm to use the heuristic fallback."
            )
        try:
            enrichment = _postprocess(document, _enrich_with_llm(document))
            return EnrichmentResult(
                enrichment=enrichment,
                method="llm",
                model=settings.enrichment_model,
                confidence=score_confidence(document, enrichment, "llm"),
            )
        except Exception as exc:  # noqa: BLE001 - one bad document must not kill the run
            logger.warning("LLM enrichment failed for %s: %s", document.source_path, exc)
            enrichment = _postprocess(document, enrich_heuristically(document))
            return EnrichmentResult(
                enrichment=enrichment,
                method="heuristic",
                confidence=score_confidence(document, enrichment, "heuristic"),
                fell_back=True,
                error=f"{type(exc).__name__}: {exc}",
            )

    enrichment = _postprocess(document, enrich_heuristically(document))
    return EnrichmentResult(
        enrichment=enrichment,
        method="heuristic",
        confidence=score_confidence(document, enrichment, "heuristic"),
    )
