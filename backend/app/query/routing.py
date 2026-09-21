"""Who to ask when the corpus cannot answer (PROJECT_INSTRUCTIONS.md Part 2
section 3).

The routee is never chosen by asking a model "who would know this?". It is
chosen by walking the same FK chain the citations use --
chunks -> documents -> document_people -> people -- so the suggested person is
always someone the corpus demonstrably records as attached to the best-matching
content, and the rationale can quote the passage that put them there. The model
is only used to phrase the draft question, which is the one part a human edits
before it is sent anyway.
"""

import logging
import sqlite3
from dataclasses import dataclass

from app.config import settings
from app.query.claude import get_client
from app.retrieval.search import ConfidenceSignal, RetrievedChunk

logger = logging.getLogger(__name__)

# How strongly each recorded relationship implies "this person can answer".
# An author owns what the document says; an action owner was handed a piece of
# it by name; an attendee was merely in the room.
ROLE_WEIGHTS = {"author": 1.0, "action_owner": 0.85, "attendee": 0.45}

# Added on top of the role weight when the person's full name appears in the
# matched passage itself. Being the one talking about the thing that matched is
# the most direct evidence available, and it is checkable -- the name is in the
# text the rationale quotes. Without it, an attendee list of twelve dilutes the
# one person who actually spoke to the subject.
MENTION_BONUS = 0.8

# people rows come from two places: the directory in data/people.yaml, and names
# lifted out of action items ("Dana will produce the RCA"). The latter can be a
# fragment or, occasionally, not a person at all, so a row with no department is
# discounted -- pickable when nothing better exists, never preferred.
UNDIRECTORIED_FACTOR = 0.5

# Chunks considered when attributing people. Past this the matches are weak
# enough that their attendee lists are noise.
ATTRIBUTION_DEPTH = 5

# Below this normalised similarity, nothing in the corpus is about the question
# and whoever is attached to the least-bad match is just the person nearest an
# unrelated paragraph. Naming them would be the same fabrication as inventing
# an answer, so the gap is logged without a routee.
MIN_ATTRIBUTION_SIMILARITY = 0.25

MATCHED_CONTENT_CHARS = 600


@dataclass
class RoutingDecision:
    person: str
    person_id: int | None
    title: str | None
    department: str | None
    email: str | None
    role: str  # how the corpus connects them to the matched content
    rationale: str
    matched_content: str
    matched_document_id: int | None
    matched_source_path: str | None
    matched_anchor: str | None
    draft_question: str
    reason: str  # why this query was routed at all

    def as_dict(self) -> dict:
        return {
            "person": self.person,
            "person_id": self.person_id,
            "title": self.title,
            "department": self.department,
            "email": self.email,
            "role": self.role,
            "rationale": self.rationale,
            "matched_content": self.matched_content,
            "matched_document_id": self.matched_document_id,
            "matched_source_path": self.matched_source_path,
            "matched_anchor": self.matched_anchor,
            "draft_question": self.draft_question,
            "reason": self.reason,
        }


@dataclass
class _Candidate:
    person_id: int
    name: str
    title: str | None
    department: str | None
    email: str | None
    score: float = 0.0
    best_role: str = "attendee"
    best_chunk: RetrievedChunk | None = None
    named_in_best_chunk: bool = False
    documents: set[int] = None  # type: ignore[assignment]


def _people_for_documents(
    conn: sqlite3.Connection, document_ids: list[int]
) -> dict[int, list[sqlite3.Row]]:
    if not document_ids:
        return {}
    placeholders = ",".join("?" * len(document_ids))
    rows = conn.execute(
        f"""
        SELECT dp.document_id, dp.role, p.id AS person_id, p.name, p.title,
               p.department, p.email
        FROM document_people dp JOIN people p ON p.id = dp.person_id
        WHERE dp.document_id IN ({placeholders})
        """,
        document_ids,
    ).fetchall()
    by_document: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        by_document.setdefault(int(row["document_id"]), []).append(row)
    return by_document


def choose_routee(conn: sqlite3.Connection, chunks: list[RetrievedChunk]) -> _Candidate | None:
    """Rank the people the corpus attaches to the best-matching documents.

    Scored per document rather than per chunk, using that document's strongest
    chunk, so a long file does not out-vote a precise one just by having more
    pieces.
    """
    considered = chunks[:ATTRIBUTION_DEPTH]
    if not considered:
        return None

    best_chunk_per_document: dict[int, RetrievedChunk] = {}
    for chunk in considered:
        current = best_chunk_per_document.get(chunk.document_id)
        if current is None or chunk.score > current.score:
            best_chunk_per_document[chunk.document_id] = chunk

    people_by_document = _people_for_documents(conn, list(best_chunk_per_document))

    candidates: dict[int, _Candidate] = {}
    for document_id, chunk in best_chunk_per_document.items():
        for row in people_by_document.get(document_id, []):
            person_id = int(row["person_id"])
            candidate = candidates.get(person_id)
            if candidate is None:
                candidate = _Candidate(
                    person_id=person_id,
                    name=row["name"],
                    title=row["title"],
                    department=row["department"],
                    email=row["email"],
                    documents=set(),
                )
                candidates[person_id] = candidate

            role = row["role"]
            # Full name only: transcripts label speakers "Ingrid Lund:", while a
            # bare first name is ambiguous across the directory.
            named = candidate.name.casefold() in chunk.text.casefold()
            contribution = chunk.score * (
                ROLE_WEIGHTS.get(role, 0.3) + (MENTION_BONUS if named else 0.0)
            )
            if not candidate.department:
                contribution *= UNDIRECTORIED_FACTOR
            candidate.score += contribution
            candidate.documents.add(document_id)

            # The evidence shown to the user is the strongest passage this
            # person is attached to, with the role that attaches them to it.
            better = candidate.best_chunk is None or chunk.score > candidate.best_chunk.score
            same_chunk_stronger_role = (
                candidate.best_chunk is not None
                and chunk.chunk_id == candidate.best_chunk.chunk_id
                and ROLE_WEIGHTS.get(role, 0.3) > ROLE_WEIGHTS.get(candidate.best_role, 0.3)
            )
            if better or same_chunk_stronger_role:
                candidate.best_chunk = chunk
                candidate.best_role = role
                candidate.named_in_best_chunk = named

    if not candidates:
        return None
    return max(candidates.values(), key=lambda c: (c.score, len(c.documents), c.name))


def _describe(candidate: _Candidate) -> str:
    detail = ", ".join(part for part in (candidate.title, candidate.department) if part)
    return f"{candidate.name} ({detail})" if detail else candidate.name


def _evidence_excerpt(candidate: _Candidate) -> str:
    """The passage to quote back. When the person is named in the matched text,
    quote the line that names them -- that is the evidence, not the paragraph
    it happens to sit in."""
    chunk = candidate.best_chunk
    if candidate.named_in_best_chunk:
        needle = candidate.name.casefold()
        for line in chunk.text.splitlines():
            if needle in line.casefold():
                return " ".join(line.split())[:260]
    return " ".join(chunk.text.split())[:260]


_ROLE_PHRASES = {
    "author": "is recorded as the author of",
    "attendee": "is recorded as an attendee of",
    "action_owner": "is named as the owner of an action item in",
}

_ROLE_NOUNS = {
    "author": "its author",
    "attendee": "an attendee",
    "action_owner": "the owner of an action item in it",
}


def _build_rationale(candidate: _Candidate, signal: ConfidenceSignal) -> str:
    chunk = candidate.best_chunk
    excerpt = _evidence_excerpt(candidate)

    if candidate.named_in_best_chunk:
        lead = (
            f"{_describe(candidate)} is named in the passage that matched this "
            f"question -- {chunk.source_path} ({chunk.source_anchor}), where the "
            f"corpus also records them as "
            f'{_ROLE_NOUNS.get(candidate.best_role, "involved")}: "{excerpt}".'
        )
    else:
        lead = (
            f"{_describe(candidate)} "
            f"{_ROLE_PHRASES.get(candidate.best_role, 'is linked to')} "
            f"{chunk.source_path} ({chunk.source_anchor}), the closest match the "
            f'corpus has to this question: "{excerpt}".'
        )
    parts = [lead]
    if len(candidate.documents) > 1:
        parts.append(
            f"They are attached to {len(candidate.documents)} of the matching sources, "
            f"more than anyone else."
        )
    if signal.reasons:
        parts.append(f"Routing rather than answering because {signal.reasons[0]}.")
    return " ".join(parts)


def _fallback_draft(query_text: str, candidate: _Candidate) -> str:
    first_name = candidate.name.split()[0]
    source = candidate.best_chunk.source_path if candidate.best_chunk else "our records"
    return (
        f"Hi {first_name} — the knowledge base doesn't have a confident answer to "
        f'this: "{query_text.strip()}" The closest thing we have is {source}, which '
        f"you're attached to. Do you know the answer, or who owns it? Happy to write "
        f"it up so it's searchable next time."
    )


def _draft_question(query_text: str, candidate: _Candidate) -> str:
    """Phrase the question for a human to review and edit before sending."""
    if not settings.has_api_key or candidate.best_chunk is None:
        return _fallback_draft(query_text, candidate)

    chunk = candidate.best_chunk
    prompt = (
        f"A colleague asked our internal knowledge base this question, and it "
        f"could not answer confidently:\n\n{query_text.strip()}\n\n"
        f"We are forwarding it to {_describe(candidate)}, who is the "
        f"{candidate.best_role.replace('_', ' ')} of the closest matching "
        f"document, {chunk.source_path} ({chunk.source_anchor}):\n\n"
        f"---\n{chunk.text[:1200]}\n---\n\n"
        f"Write the message to send them. Requirements: address them by first "
        f"name; state the question plainly; say in one clause why they are being "
        f"asked, referring to the document; ask whether they know the answer or "
        f"who owns it. Three sentences at most, no subject line, no sign-off, no "
        f"preamble — output only the message."
    )
    try:
        response = get_client().messages.create(
            model=settings.synthesis_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return text or _fallback_draft(query_text, candidate)
    except Exception as exc:  # noqa: BLE001 - a templated question still routes
        logger.warning("draft question generation failed: %s", exc)
        return _fallback_draft(query_text, candidate)


def route(
    conn: sqlite3.Connection,
    query_text: str,
    chunks: list[RetrievedChunk],
    signal: ConfidenceSignal,
    reason: str,
) -> RoutingDecision | None:
    """Build the routing block for a query that could not be answered.

    Returns None when retrieval found nothing that is actually about the
    question: there is then no matched content to justify a person, and naming
    one anyway would be exactly the fabrication this endpoint exists to avoid.
    The caller records the gap without a routee.
    """
    if not chunks or signal.top_similarity < MIN_ATTRIBUTION_SIMILARITY:
        return None

    candidate = choose_routee(conn, chunks)
    if candidate is None or candidate.best_chunk is None:
        return None

    chunk = candidate.best_chunk
    return RoutingDecision(
        person=candidate.name,
        person_id=candidate.person_id,
        title=candidate.title,
        department=candidate.department,
        email=candidate.email,
        role=candidate.best_role,
        rationale=_build_rationale(candidate, signal),
        matched_content=chunk.text[:MATCHED_CONTENT_CHARS],
        matched_document_id=chunk.document_id,
        matched_source_path=chunk.source_path,
        matched_anchor=chunk.source_anchor,
        draft_question=_draft_question(query_text, candidate),
        reason=reason,
    )
