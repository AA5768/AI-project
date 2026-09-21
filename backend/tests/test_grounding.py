"""Evidence grounding: a stored quote must always be findable in the source file.

Cases here are taken from real Haiku output over the data/ corpus, where ~4% of
quotes were paraphrases that would have shipped as unverifiable citations.
"""

from app.enrichment.grounding import ground_evidence, ground_items
from app.enrichment.schema import DerivedActionItem, DerivedDecision

SOURCE = (
    "Priya Raman: I can live with that. Northgate gets the OEE change in the\n"
    "release, and Aisha picks the week she briefs them.\n\n"
    "Marcus Feld: Agreed. I’ll send the “draft” by the twenty—fourth.\n"
)


def test_exact_quote_is_returned_as_source_text():
    span, exact = ground_evidence(SOURCE, "Northgate gets the OEE change in the release")
    assert exact is True
    assert span in " ".join(SOURCE.split()) or span.replace("\n", " ") in SOURCE.replace("\n", " ")
    assert "Northgate gets the OEE change" in span


def test_quote_spanning_a_line_break_is_recovered_verbatim():
    """The model quotes with a space where the file has a newline."""
    span, exact = ground_evidence(
        SOURCE, "Northgate gets the OEE change in the release, and Aisha picks the week"
    )
    assert exact is True
    assert span in SOURCE  # the file's own bytes, newline included


def test_smart_punctuation_still_matches():
    span, exact = ground_evidence(SOURCE, "I'll send the \"draft\" by the twenty-fourth.")
    assert exact is True
    assert "’" in span and "“" in span  # original curly characters preserved


def test_paraphrase_that_prepends_words_is_repaired_to_the_real_span():
    """Real failure: Haiku wrote 'Agreed. Northgate gets...' but 'Agreed.' is a
    different speaker's line. The stored quote must be what the file says."""
    span, exact = ground_evidence(
        SOURCE, "Agreed. Northgate gets the OEE change in the release, and Aisha picks the week"
    )
    assert span is not None
    assert exact is False
    assert span in SOURCE
    assert not span.startswith("Agreed.")


def test_stitched_quote_across_distant_spans_is_rejected():
    """Real failure: two non-adjacent fragments joined with an ellipsis. There is
    no single source span for it, so it must not become a citation."""
    span, exact = ground_evidence(
        SOURCE,
        "I am writing D1 through D5 for the containment section of the report... "
        "then I need the final draft by the twenty-fourth to send to the customer",
    )
    assert span is None
    assert exact is False


def test_wholly_invented_quote_is_rejected():
    span, exact = ground_evidence(SOURCE, "We approved a 40% price increase for all customers.")
    assert span is None
    assert exact is False


def test_empty_inputs_are_handled():
    assert ground_evidence(SOURCE, None) == (None, False)
    assert ground_evidence(SOURCE, "   ") == (None, False)
    assert ground_evidence("", "anything") == (None, False)


def test_ground_items_rewrites_in_place_and_counts_drops():
    items = [
        DerivedDecision(
            text="Ship the OEE change.",
            evidence="Northgate gets the OEE change in the release",
        ),
        DerivedActionItem(
            text="Do something imaginary.",
            evidence="We approved a 40% price increase for all customers.",
        ),
    ]
    returned, dropped = ground_items(SOURCE, items)

    assert dropped == 1
    assert returned[0].evidence is not None and returned[0].evidence in SOURCE
    # The extraction survives; only the unverifiable quote is removed.
    assert returned[1].evidence is None
    assert returned[1].text == "Do something imaginary."


def test_ungrounded_evidence_lowers_document_confidence():
    from app.enrichment.enrich import score_confidence
    from app.enrichment.schema import DocumentEnrichment
    from app.ingestion.common import Document

    doc = Document(
        source_path="data/transcripts/x.md",
        source_type="transcript",
        raw_text=SOURCE,
        sections=[],
        attendees_or_author=["Priya Raman"],
        date="2026-04-23",
    )
    common = dict(
        topic_domain="equipment_software",
        priority="medium",
        summary="A summary long enough to clear the completeness floor comfortably.",
        quality_flags=[],
        source_quality=0.8,
    )
    grounded = DocumentEnrichment(
        **common, decisions=[DerivedDecision(text="d", evidence="real quote")]
    )
    ungrounded = DocumentEnrichment(
        **common, decisions=[DerivedDecision(text="d", evidence=None)]
    )

    assert score_confidence(doc, ungrounded, "llm") < score_confidence(doc, grounded, "llm")
