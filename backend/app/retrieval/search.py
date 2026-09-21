"""Hybrid retrieval: sqlite-vec cosine top-k + FTS5 keyword arm, merged into a
single ranked chunk list with a computed confidence. See PROJECT_INSTRUCTIONS.md
Part 2 section 1.

Both arms are needed for different failure modes. The vector arm answers
paraphrases ("who owns the particle problem" -> chunks that never say "owns"),
but it degrades on rare literal tokens -- part numbers, "SEMI S2", "nine pass
number" -- which is exactly where the keyword arm is strong. Fusing them keeps
recall on both, and the confidence score below is computed from the fused
result, never hardcoded, because it is what gates routing to a human.
"""

import json
import re
import sqlite3
from dataclasses import dataclass, field

from app.config import settings
from app.retrieval.embeddings import embed_one, serialize

# How many candidates each arm contributes before fusion. Wider than top_k so a
# chunk that only one arm likes can still win on the combined score.
CANDIDATE_K = 30

# all-MiniLM-L6-v2 cosine similarities sit in a compressed band. Measured over
# this corpus: an off-topic question ("parental leave policy") tops out at
# 0.24-0.28, while every question the corpus genuinely answers peaks at
# 0.61-0.66. Raw cosine is therefore useless as a 0..1 confidence; these two
# constants map the band that actually discriminates onto the full range.
# tests/test_search.py pins the separation they produce.
SIM_FLOOR = 0.20
SIM_CEIL = 0.70

# Weight between the arms when ranking. Semantic leads because it is the signal
# with absolute meaning; keyword is a rank-based nudge for literal matches.
SEMANTIC_WEIGHT = 0.70
KEYWORD_WEIGHT = 0.30

# A chunk has to clear this normalised similarity to count as corroboration.
CORROBORATION_FLOOR = 0.50
CORROBORATION_TARGET = 3  # distinct documents at which corroboration saturates


@dataclass
class RetrievedChunk:
    """One chunk plus the document context a citation needs.

    Carrying the document fields here (rather than re-querying per citation)
    keeps the traceability chain in one object: whoever renders this has the
    source_path, the verbatim author/attendee list and the anchor already.
    """

    chunk_id: int
    document_id: int
    chunk_index: int
    text: str
    source_anchor: str
    source_path: str
    source_type: str
    title: str | None
    date: str | None
    attendees_or_author: list[str]
    topic_domain: str | None
    priority: str | None
    quality_flags: list[str]
    enrichment_confidence: float
    semantic: float  # normalised cosine, 0..1
    keyword: float  # rank-derived FTS score, 0..1
    score: float  # fused ranking score, 0..1

    @property
    def cosine(self) -> float:
        """The un-normalised similarity, for debugging and metrics."""
        return SIM_FLOOR + self.semantic * (SIM_CEIL - SIM_FLOOR)


@dataclass
class ConfidenceSignal:
    """A confidence value together with the parts it was computed from.

    The breakdown is returned to the caller and stored with the gap, so a
    low-confidence routing decision can be explained ("one weak source, no
    corroboration") instead of asserted.
    """

    value: float
    top_similarity: float = 0.0
    support: float = 0.0
    corroboration: float = 0.0
    source_trust: float = 0.0
    matched_documents: int = 0
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "value": self.value,
            "top_similarity": round(self.top_similarity, 4),
            "support": round(self.support, 4),
            "corroboration": round(self.corroboration, 4),
            "source_trust": round(self.source_trust, 4),
            "matched_documents": self.matched_documents,
            "reasons": self.reasons,
        }


# ------------------------------------------------------------------- retrieval


_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9\-\.]*")


def _fts_match_expression(query_text: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression.

    Every token is double-quoted, which both escapes FTS operator characters
    (a bare `Helios-3` parses as NOT, `AND` as a keyword) and stops a user's
    punctuation from turning into a syntax error. OR rather than AND because
    this arm is for recall -- bm25 already ranks multi-term hits higher.
    """
    tokens = [t for t in _TOKEN_RE.findall(query_text) if len(t) > 1]
    return " OR ".join(f'"{t}"' for t in tokens)


def _keyword_candidates(conn: sqlite3.Connection, query_text: str, limit: int) -> dict[int, float]:
    """chunk_id -> 0..1 keyword score, derived from bm25 rank."""
    expression = _fts_match_expression(query_text)
    if not expression:
        return {}
    try:
        rows = conn.execute(
            "SELECT rowid AS chunk_id FROM chunks_fts WHERE chunks_fts MATCH ? "
            "ORDER BY bm25(chunks_fts) LIMIT ?",
            (expression, limit),
        ).fetchall()
    except sqlite3.OperationalError:
        # A malformed expression must degrade to semantic-only, not 500.
        return {}
    # Rank-derived rather than bm25-derived: bm25 is unbounded and corpus-
    # dependent, so its absolute value cannot be blended with a similarity.
    return {int(row["chunk_id"]): 1.0 / (1.0 + 0.25 * rank) for rank, row in enumerate(rows)}


def _vector_candidates(conn: sqlite3.Connection, vector: list[float], limit: int) -> dict[int, float]:
    """chunk_id -> cosine similarity, from the vec0 KNN index."""
    rows = conn.execute(
        "SELECT chunk_id, distance FROM chunk_vectors "
        "WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (serialize(vector), limit),
    ).fetchall()
    # Vectors are L2-normalised at encode time, so d^2 = 2 - 2cos.
    return {int(row["chunk_id"]): 1.0 - (float(row["distance"]) ** 2) / 2.0 for row in rows}


def _normalise_similarity(cosine: float) -> float:
    return max(0.0, min(1.0, (cosine - SIM_FLOOR) / (SIM_CEIL - SIM_FLOOR)))


def _load_chunks(conn: sqlite3.Connection, chunk_ids: list[int]) -> dict[int, sqlite3.Row]:
    if not chunk_ids:
        return {}
    placeholders = ",".join("?" * len(chunk_ids))
    rows = conn.execute(
        f"""
        SELECT c.id AS chunk_id, c.document_id, c.chunk_index, c.text, c.source_anchor,
               c.embedding, d.source_path, d.source_type, d.title, d.date,
               d.attendees_or_author, d.topic_domain, d.priority, d.quality_flags,
               d.enrichment_confidence
        FROM chunks c JOIN documents d ON d.id = c.document_id
        WHERE c.id IN ({placeholders})
        """,
        chunk_ids,
    ).fetchall()
    return {int(row["chunk_id"]): row for row in rows}


def _cosine_from_blob(blob: bytes | None, vector: list[float]) -> float:
    """Similarity for a chunk the KNN arm did not return (keyword-only hit)."""
    if not blob:
        return 0.0
    from app.retrieval.embeddings import deserialize

    stored = deserialize(blob)
    return sum(a * b for a, b in zip(stored, vector))


def search(
    conn: sqlite3.Connection,
    query_text: str,
    top_k: int = 8,
    candidate_k: int = CANDIDATE_K,
) -> list[RetrievedChunk]:
    """Rank chunks across both corpora for one query.

    Source type never enters the ranking or the returned shape -- a transcript
    line and a spreadsheet row compete on the same score and come back as the
    same object (PROJECT_INSTRUCTIONS.md Part 2 section 6).
    """
    query_text = query_text.strip()
    if not query_text:
        return []

    vector = embed_one(query_text)
    semantic_hits = _vector_candidates(conn, vector, candidate_k)
    keyword_hits = _keyword_candidates(conn, query_text, candidate_k)

    rows = _load_chunks(conn, list({*semantic_hits, *keyword_hits}))

    results: list[RetrievedChunk] = []
    for chunk_id, row in rows.items():
        cosine = semantic_hits.get(chunk_id)
        if cosine is None:
            cosine = _cosine_from_blob(row["embedding"], vector)
        semantic = _normalise_similarity(cosine)
        keyword = keyword_hits.get(chunk_id, 0.0)
        results.append(
            RetrievedChunk(
                chunk_id=chunk_id,
                document_id=int(row["document_id"]),
                chunk_index=int(row["chunk_index"]),
                text=row["text"],
                source_anchor=row["source_anchor"],
                source_path=row["source_path"],
                source_type=row["source_type"],
                title=row["title"],
                date=row["date"],
                attendees_or_author=json.loads(row["attendees_or_author"] or "[]"),
                topic_domain=row["topic_domain"],
                priority=row["priority"],
                quality_flags=json.loads(row["quality_flags"] or "[]"),
                enrichment_confidence=float(row["enrichment_confidence"]),
                semantic=round(semantic, 4),
                keyword=round(keyword, 4),
                score=round(SEMANTIC_WEIGHT * semantic + KEYWORD_WEIGHT * keyword, 4),
            )
        )

    results.sort(key=lambda c: (-c.score, -c.semantic, c.chunk_id))
    return results[:top_k]


# ------------------------------------------------------------------ confidence


def compute_confidence(chunks: list[RetrievedChunk]) -> ConfidenceSignal:
    """How much the retrieved evidence supports answering at all, on 0..1.

    Four independent signals, so no single one can carry a weak result:

      top_similarity  the best chunk actually looks like the question
      support         the next-best chunks do too (one lucky hit is not enough)
      corroboration   more than one document says it
      source_trust    the documents it came from were enriched confidently
                      (a stale, unattributed scratch file scores 0.29 and has
                      to drag an otherwise strong lexical match down)

    This is deliberately computed before synthesis: below the threshold we route
    to a human without asking the model to write anything, so there is no weak
    answer to be tempted by.

    What it cannot see is whether the evidence answers the *question* as opposed
    to merely being about the same topic -- "what is the nine pass number" pulls
    every Helios-3 chunk in the corpus and scores well on all four signals. That
    gap is closed by the second gate in app/query/service.py, which discounts
    this value by how much of the drafted answer is actually grounded.
    """
    if not chunks:
        return ConfidenceSignal(value=0.0, reasons=["retrieval returned no chunks"])

    ranked = sorted(chunks, key=lambda c: -c.score)
    top_similarity = max(c.semantic for c in ranked)
    support = sum(c.semantic for c in ranked[:3]) / min(3, len(ranked))

    strong = [c for c in ranked if c.semantic >= CORROBORATION_FLOOR]
    distinct_docs = {c.document_id for c in strong}
    corroboration = min(1.0, len(distinct_docs) / CORROBORATION_TARGET)

    weight_total = sum(c.score for c in ranked[:5]) or 1.0
    source_trust = (
        sum(c.enrichment_confidence * c.score for c in ranked[:5]) / weight_total
    )

    value = round(
        0.40 * top_similarity + 0.20 * support + 0.15 * corroboration + 0.25 * source_trust,
        4,
    )

    reasons = []
    if top_similarity < 0.5:
        reasons.append(
            f"best match is only a partial fit (similarity {ranked[0].cosine:.2f})"
        )
    if not distinct_docs:
        reasons.append("no document matched strongly enough to corroborate")
    elif len(distinct_docs) == 1:
        reasons.append(
            f"only one document supports this ({ranked[0].source_path}), nothing corroborates it"
        )
    if source_trust < 0.6:
        reasons.append(
            f"the matching sources are themselves low-quality "
            f"(enrichment confidence {source_trust:.2f}; "
            f"flags: {', '.join(sorted({f for c in ranked[:3] for f in c.quality_flags})) or 'none'})"
        )

    return ConfidenceSignal(
        value=value,
        top_similarity=top_similarity,
        support=support,
        corroboration=corroboration,
        source_trust=source_trust,
        matched_documents=len({c.document_id for c in ranked}),
        reasons=reasons,
    )


def is_confident(value: float) -> bool:
    return value >= settings.confidence_threshold
