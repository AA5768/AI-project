"""Hybrid retrieval: sqlite-vec cosine top-k + FTS5 keyword fallback, merged
into a single ranked chunk list with a confidence score. See
PROJECT_INSTRUCTIONS.md Part 2 §1.
"""

from dataclasses import dataclass


@dataclass
class RetrievedChunk:
    chunk_id: int
    document_id: int
    text: str
    source_anchor: str
    score: float


def search(query_text: str, top_k: int = 8) -> list[RetrievedChunk]:
    raise NotImplementedError


def compute_confidence(chunks: list[RetrievedChunk]) -> float:
    raise NotImplementedError
