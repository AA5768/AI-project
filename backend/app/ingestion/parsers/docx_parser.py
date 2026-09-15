from pathlib import Path

from docx import Document as DocxDocument

from app.ingestion.common import Document, Section


def parse_docx(path: Path) -> Document:
    docx = DocxDocument(path)
    sections = [
        Section(text=p.text, anchor=f"paragraph:{i}")
        for i, p in enumerate(docx.paragraphs)
        if p.text.strip()
    ]
    raw_text = "\n".join(s.text for s in sections)
    return Document(
        source_path=str(path),
        source_type="docx",
        raw_text=raw_text,
        sections=sections,
    )
