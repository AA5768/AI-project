"""LLM-derived structured metadata per document (topic_domain, priority, summary,
decisions[], action_items[]) via Claude Haiku. See PROJECT_INSTRUCTIONS.md Part 1 §3.
"""

from dataclasses import dataclass

from app.ingestion.common import Document


@dataclass
class Enrichment:
    topic_domain: str
    priority: str | None
    summary: str
    decisions: list[str]
    action_items: list[str]


def enrich_document(document: Document) -> Enrichment:
    raise NotImplementedError
