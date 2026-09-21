"""Enrichment invariants that hold on both the Claude path and the fallback.

The live-LLM test is opt-in (`RUN_LLM_TESTS=1`) so the default suite stays free
and offline; everything else here runs against the deterministic path.
"""

import os

import pytest

from app.enrichment.enrich import (
    _apply_mechanical_flags,
    _coerce,
    enrich_document,
    score_confidence,
)
from app.enrichment.heuristics import enrich_heuristically
from app.enrichment.taxonomy import PRIORITIES, QUALITY_FLAGS, TOPIC_DOMAINS
from app.ingestion.common import Document
from app.ingestion.parsers.transcript_parser import parse_transcript


def _doc(**kwargs) -> Document:
    base = dict(
        source_path="data/transcripts/x.md",
        source_type="transcript",
        raw_text=(
            "The end effector wafer placement repeatability drifts. "
            "We decided to hold the ship date."
        ),
        sections=[],
        attendees_or_author=["Priya Raman"],
        date="2026-03-04",
    )
    base.update(kwargs)
    return Document(**base)


def test_unattributed_is_owned_by_the_parser_not_the_model():
    """Haiku flagged a transcript with three named attendees as `unattributed`.
    The flag carries a confidence penalty, so it is set mechanically."""
    attributed = _doc(attendees_or_author=["Priya Raman"])
    enrichment = enrich_heuristically(attributed)
    enrichment.quality_flags = ["unattributed", "stale"]

    fixed = _apply_mechanical_flags(attributed, enrichment)
    assert "unattributed" not in fixed.quality_flags
    assert "stale" in fixed.quality_flags


def test_unattributed_is_added_when_the_file_names_nobody():
    anonymous = _doc(attendees_or_author=[])
    enrichment = enrich_heuristically(anonymous)
    enrichment.quality_flags = []

    fixed = _apply_mechanical_flags(anonymous, enrichment)
    assert "unattributed" in fixed.quality_flags


def test_mechanical_flags_do_not_duplicate():
    anonymous = _doc(attendees_or_author=[])
    enrichment = enrich_heuristically(anonymous)
    enrichment.quality_flags = ["unattributed", "unattributed", "sparse"]

    fixed = _apply_mechanical_flags(anonymous, enrichment)
    assert fixed.quality_flags.count("unattributed") == 1


def test_coerce_clamps_out_of_vocabulary_values():
    enrichment = enrich_heuristically(_doc())
    enrichment.topic_domain = "made_up_domain"
    enrichment.priority = "URGENT!!"
    enrichment.quality_flags = ["bogus", "stale"]

    coerced = _coerce(enrichment)
    assert coerced.topic_domain == "other"
    assert coerced.priority == "unspecified"
    assert coerced.quality_flags == ["stale"]


@pytest.mark.parametrize(
    "text, forbidden, why",
    [
        # "ate" (automated test equipment) fired 237 times across data/ with zero
        # real hits -- 51 of them inside the customer name "Northgate".
        ("The Northgate escalation update is due by that date. "
         "We attached the certificate and the candidate plate.",
         "test_cell_handler", "'ate' inside Northgate/update/date/certificate"),
        # "eda" (equipment data acquisition) inside the supplier name "Kaneda".
        ("Kaneda confirmed the allocation and the second source lead time.",
         "equipment_software", "'eda' inside Kaneda"),
        # "arr" (annual recurring revenue) and "capa" (corrective action).
        ("We are carrying extra buffer stock because capacity is constrained.",
         "sales_pipeline", "'arr' inside carrying, 'capa' inside capacity"),
        # "req" (requisition) and "api".
        ("The capital request has a requirement that requires approval.",
         "hiring_people", "'req' inside requirement/request, 'api' inside capital"),
    ],
)
def test_short_acronym_cues_do_not_match_inside_longer_words(text, forbidden, why):
    """Substring matching made short industry acronyms actively harmful."""
    from app.enrichment.heuristics import _classify_domain

    assert _classify_domain(text) != forbidden, why


def test_cue_matching_still_tolerates_simple_inflection():
    from app.enrichment.heuristics import _count_cue

    assert _count_cue("Two wafers were dropped.", "wafer") == 1
    assert _count_cue("The encoders failed.", "encoder") == 1
    assert _count_cue("Deployment is blocked.", "deploy") == 1
    assert _count_cue("Shipments slipped.", "shipment") == 1
    # ...but not inside an unrelated word.
    assert _count_cue("Northgate sent an update.", "ate") == 0
    assert _count_cue("Kaneda replied.", "eda") == 0


def test_multi_word_and_hyphenated_cues_match_either_spelling():
    from app.enrichment.heuristics import _count_cue

    assert _count_cue("The end effector was replaced.", "end effector") == 1
    assert _count_cue("The end-effector was replaced.", "end effector") == 1
    assert _count_cue("Running tri-temp soak now.", "tri-temp") == 1
    assert _count_cue("Running tri temp soak now.", "tri-temp") == 1


def test_heuristic_output_always_uses_the_controlled_vocabulary(corpus):
    for name in ("standup.md", "sparse.md"):
        doc = parse_transcript(corpus / "transcripts" / name)
        enrichment = enrich_heuristically(doc)
        assert enrichment.topic_domain in TOPIC_DOMAINS
        assert enrichment.priority in PRIORITIES
        assert all(f in QUALITY_FLAGS for f in enrichment.quality_flags)


def test_confidence_penalties_lower_the_score():
    doc = _doc()
    clean = enrich_heuristically(doc)
    clean.quality_flags = []
    flagged = enrich_heuristically(doc)
    flagged.quality_flags = ["sparse", "stale"]

    assert score_confidence(doc, flagged, "llm") < score_confidence(doc, clean, "llm")


def test_confidence_stays_in_range_at_both_extremes():
    worst = enrich_heuristically(_doc(attendees_or_author=[], date=None, raw_text="TBD"))
    worst.quality_flags = list(QUALITY_FLAGS)
    worst.source_quality = 0.0
    assert 0.0 < score_confidence(_doc(), worst, "heuristic") <= 1.0

    best = enrich_heuristically(_doc())
    best.quality_flags = []
    best.source_quality = 1.0
    best.summary = "A substantive summary that comfortably exceeds the length floor."
    assert score_confidence(_doc(), best, "llm") <= 1.0


def test_forced_llm_without_a_key_fails_loudly(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        enrich_document(_doc(), use_llm=True)


def test_llm_failure_falls_back_and_records_why(monkeypatch, corpus):
    import app.enrichment.enrich as enrich_module
    from app.config import settings

    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-not-a-real-key")

    def boom(_document):
        raise ConnectionError("proxy refused")

    monkeypatch.setattr(enrich_module, "_enrich_with_llm", boom)

    doc = parse_transcript(corpus / "transcripts" / "standup.md")
    result = enrich_document(doc, use_llm=True)

    assert result.method == "heuristic"
    assert result.fell_back is True
    assert "proxy refused" in (result.error or "")
    # A silently-degraded run is the failure mode /metrics must surface, so the
    # fallback must not inherit the LLM path's confidence.
    assert result.confidence < 0.6


@pytest.mark.skipif(
    os.environ.get("RUN_LLM_TESTS") != "1",
    reason="live Claude call; set RUN_LLM_TESTS=1 to enable",
)
def test_live_claude_enrichment_is_grounded_in_the_source(corpus):
    doc = parse_transcript(corpus / "transcripts" / "standup.md")
    result = enrich_document(doc, use_llm=True)

    assert result.method == "llm", result.error
    assert not result.fell_back

    enrichment = result.enrichment
    assert enrichment.topic_domain in TOPIC_DOMAINS
    assert enrichment.priority in PRIORITIES
    # The file names three attendees, so this flag must not be set.
    assert "unattributed" not in enrichment.quality_flags

    # Every cited evidence string must actually appear in the document.
    haystack = " ".join(doc.raw_text.split()).casefold()
    for item in [*enrichment.decisions, *enrichment.action_items]:
        needle = " ".join(item.evidence.split()).casefold()
        assert needle in haystack, f"fabricated evidence: {item.evidence!r}"
