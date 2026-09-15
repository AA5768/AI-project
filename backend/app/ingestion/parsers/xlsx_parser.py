from pathlib import Path

from openpyxl import load_workbook

from app.ingestion.common import Document, Section


def parse_xlsx(path: Path) -> Document:
    wb = load_workbook(path, data_only=True)
    sections = []
    for sheet in wb.worksheets:
        for row in sheet.iter_rows():
            values = [str(c.value) for c in row if c.value is not None]
            if not values:
                continue
            first_cell, last_cell = row[0].coordinate, row[-1].coordinate
            sections.append(
                Section(
                    text=" | ".join(values),
                    anchor=f"sheet:{sheet.title}!{first_cell}:{last_cell}",
                )
            )
    raw_text = "\n".join(s.text for s in sections)
    return Document(
        source_path=str(path),
        source_type="xlsx",
        raw_text=raw_text,
        sections=sections,
    )
