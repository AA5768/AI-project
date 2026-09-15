from dataclasses import dataclass, field


@dataclass
class Section:
    text: str
    anchor: str  # e.g. "line:12-18", "slide:3", "sheet:Budget!A1:C4"


@dataclass
class Document:
    source_path: str
    source_type: str  # transcript | docx | pptx | xlsx
    raw_text: str
    sections: list[Section] = field(default_factory=list)
    attendees_or_author: list[str] = field(default_factory=list)
    date: str | None = None
