from pathlib import Path

from pptx import Presentation

from app.ingestion.common import Document, Section


def parse_pptx(path: Path) -> Document:
    prs = Presentation(path)
    sections = []
    for slide_num, slide in enumerate(prs.slides, start=1):
        texts = [
            shape.text_frame.text
            for shape in slide.shapes
            if shape.has_text_frame and shape.text_frame.text.strip()
        ]
        if texts:
            sections.append(
                Section(text="\n".join(texts), anchor=f"slide:{slide_num}")
            )
    raw_text = "\n\n".join(s.text for s in sections)
    return Document(
        source_path=str(path),
        source_type="pptx",
        raw_text=raw_text,
        sections=sections,
    )
