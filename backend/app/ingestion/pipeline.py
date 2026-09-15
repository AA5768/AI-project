"""Ingestion entrypoint: data/ -> parsed Documents -> enrichment -> SQLite.

Run with: python -m app.ingestion.pipeline
"""

from pathlib import Path

from app.config import settings
from app.ingestion.common import Document
from app.ingestion.parsers.docx_parser import parse_docx
from app.ingestion.parsers.pptx_parser import parse_pptx
from app.ingestion.parsers.transcript_parser import parse_transcript
from app.ingestion.parsers.xlsx_parser import parse_xlsx

PARSERS = {
    ".md": parse_transcript,
    ".docx": parse_docx,
    ".pptx": parse_pptx,
    ".xlsx": parse_xlsx,
}


def discover_files(data_dir: Path) -> list[Path]:
    return [
        p
        for p in data_dir.rglob("*")
        if p.suffix.lower() in PARSERS and p.is_file()
    ]


def parse_all(data_dir: Path) -> list[Document]:
    documents = []
    for path in discover_files(data_dir):
        parser = PARSERS[path.suffix.lower()]
        documents.append(parser(path))
    return documents


def run(data_dir: Path | None = None) -> None:
    documents = parse_all(data_dir or settings.data_dir)
    # TODO: enrichment (app.enrichment.enrich), embedding (app.retrieval.embeddings),
    # and persistence (app.db.connection) wire in here.
    print(f"Parsed {len(documents)} documents from {data_dir or settings.data_dir}")


if __name__ == "__main__":
    run()
