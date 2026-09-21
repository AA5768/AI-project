"""Parser-level invariants. These are the ones that, if they break, silently
produce citations that point at the wrong place or name the wrong person.
"""

import json

from app.ingestion.chunking import chunk_sections
from app.ingestion.parsers.docx_parser import parse_docx
from app.ingestion.parsers.pptx_parser import parse_pptx
from app.ingestion.parsers.transcript_parser import parse_transcript
from app.ingestion.parsers.xlsx_parser import parse_xlsx


def test_transcript_keeps_attendees_verbatim(corpus):
    doc = parse_transcript(corpus / "transcripts" / "standup.md")
    assert doc.attendees_or_author == ["Priya Raman", "Dana Okafor", "Marcus Lindqvist"]
    assert doc.date == "2026-03-04"
    assert doc.source_type == "transcript"


def test_transcript_strips_bold_markers_from_both_label_forms(corpus):
    doc = parse_transcript(corpus / "transcripts" / "standup.md")
    speakers = {s.speaker for s in doc.sections if s.speaker}
    assert {"Dana Okafor", "Priya Raman"} <= speakers
    # "**Name:** text" and "**Name**: text" must both yield clean text.
    assert not any(s.text.lstrip().startswith("*") for s in doc.sections)


def test_transcript_does_not_invent_a_speaker_from_a_label_line(corpus):
    doc = parse_transcript(corpus / "transcripts" / "standup.md")
    # "Action: Marcus to notify the customer." must not create a speaker "Action".
    assert "Action" not in {s.speaker for s in doc.sections if s.speaker}


def test_transcript_multiline_turn_spans_a_line_range(corpus):
    doc = parse_transcript(corpus / "transcripts" / "standup.md")
    dana = next(s for s in doc.sections if s.speaker == "Dana Okafor")
    assert dana.locator_start != dana.locator_end
    assert dana.anchor.startswith("End effector status line ")


def test_docx_extracts_author_heading_scope_and_tables(corpus):
    doc = parse_docx(corpus / "office" / "escalation.docx")
    assert doc.attendees_or_author == ["Marcus Lindqvist"]
    assert any(s.kind == "table" for s in doc.sections)
    assert any(s.scope == "Problem" for s in doc.sections)


def test_pptx_separates_speaker_notes_from_the_slide(corpus):
    doc = parse_pptx(corpus / "office" / "roadmap.pptx")
    kinds = {s.kind for s in doc.sections}
    assert {"slide", "notes"} <= kinds
    notes = next(s for s in doc.sections if s.kind == "notes")
    assert "pre-audit" in notes.text
    assert notes.anchor == "notes 1"


def test_xlsx_repeats_the_header_without_duplicating_it_in_the_range(corpus):
    doc = parse_xlsx(corpus / "office" / "budget.xlsx")
    bands = [s for s in doc.sections if s.scope and s.scope.startswith("Budget")]
    assert bands, "expected banded rows for the Budget sheet"
    first = bands[0]
    # Header is context in the text, and is named in the scope, not the range.
    assert first.text.startswith("Line item | Quarter | Planned | Actual")
    assert first.text.count("Line item | Quarter") == 1
    assert "header row 1" in first.scope
    assert first.locator_start == "A2"
    assert "cells A2:D13" in first.anchor


def test_xlsx_covers_every_sheet(corpus):
    doc = parse_xlsx(corpus / "office" / "budget.xlsx")
    scopes = " ".join(s.scope or "" for s in doc.sections)
    assert "Budget" in scopes and "Headcount" in scopes


def test_chunking_merges_within_scope_and_splits_across_it(corpus):
    doc = parse_pptx(corpus / "office" / "roadmap.pptx")
    chunks = chunk_sections(doc.sections)
    assert chunks
    assert all(c.source_anchor.strip() for c in chunks)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # A slide and its notes are different kinds, so they never share a chunk.
    assert not any("slide" in c.source_anchor and "notes" in c.source_anchor for c in chunks)


def test_chunking_respects_the_hard_cap():
    from app.ingestion.common import Section

    long_section = Section(
        text=". ".join(f"Sentence number {i} about gripper torque" for i in range(400)),
        kind="paragraph",
        locator_start="1",
        locator_end="1",
    )
    chunks = chunk_sections([long_section], target_chars=500, max_chars=800)
    assert len(chunks) > 1
    assert all(len(c.text) <= 900 for c in chunks)
    # Every shard still cites the paragraph it came from.
    assert all(c.source_anchor == "paragraph 1" for c in chunks)


def test_sparse_transcript_has_no_attendees_and_still_parses(corpus):
    doc = parse_transcript(corpus / "transcripts" / "sparse.md")
    assert doc.attendees_or_author == []
    assert json.dumps(doc.attendees_or_author) == "[]"
