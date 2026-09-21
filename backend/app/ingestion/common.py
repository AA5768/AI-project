"""Common internal representation that both file families converge on.

Transcripts and Office files are parsed by different code, but everything
downstream of the parser -- chunking, enrichment, embedding, persistence -- sees
only `Document`/`Section`, so the business rules apply identically regardless of
where the content came from (PROJECT_INSTRUCTIONS.md Part 1 section 2).
"""

from dataclasses import dataclass, field

# Locators that read as a range with a colon (spreadsheet cells) rather than a dash.
_COLON_RANGE_KINDS = {"cells"}


@dataclass
class Section:
    """One structurally-anchored piece of a source file.

    The locator pair is what makes a citation checkable: a reader given
    "slide 4" or "Budget cells A7:D12" can open the file and find the text.
    """

    text: str
    kind: str  # line | paragraph | slide | notes | table | cells
    locator_start: str
    locator_end: str
    scope: str | None = None  # sheet name, slide title, or nearest heading
    speaker: str | None = None  # transcripts only

    @property
    def anchor(self) -> str:
        sep = ":" if self.kind in _COLON_RANGE_KINDS else "-"
        if self.locator_start == self.locator_end:
            span = f"{self.kind} {self.locator_start}"
        else:
            span = f"{self.kind} {self.locator_start}{sep}{self.locator_end}"
        return f"{self.scope} {span}" if self.scope else span

    def mergeable_with(self, other: "Section") -> bool:
        return self.kind == other.kind and self.scope == other.scope


@dataclass
class Document:
    source_path: str  # repo-relative
    source_type: str  # transcript | docx | pptx | xlsx
    raw_text: str
    sections: list[Section] = field(default_factory=list)
    title: str | None = None
    # Verbatim from the source -- never re-derived or guessed by the LLM.
    attendees_or_author: list[str] = field(default_factory=list)
    date: str | None = None


@dataclass
class Chunk:
    index: int
    text: str
    source_anchor: str

    @property
    def char_count(self) -> int:
        return len(self.text)
