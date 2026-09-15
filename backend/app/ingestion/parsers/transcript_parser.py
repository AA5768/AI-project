from pathlib import Path

import frontmatter

from app.ingestion.common import Document, Section


def parse_transcript(path: Path) -> Document:
    post = frontmatter.load(path)
    lines = post.content.splitlines()
    sections = [
        Section(text=line, anchor=f"line:{i + 1}")
        for i, line in enumerate(lines)
        if line.strip()
    ]
    return Document(
        source_path=str(path),
        source_type="transcript",
        raw_text=post.content,
        sections=sections,
        attendees_or_author=post.get("attendees", []),
        date=post.get("date"),
    )
