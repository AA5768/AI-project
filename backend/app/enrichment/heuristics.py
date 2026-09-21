"""Deterministic enrichment fallback -- no API key required.

Runs when the LLM path is unavailable or errors on a document. It produces the
same `DocumentEnrichment` shape but scores itself low, which is the point: a
document enriched this way should pull its query confidence down and be more
likely to route to a human. Cue-matching genuinely is worse than a model at
reading intent out of dialogue, and the confidence number is where that shows up.

Measured on the 37-document corpus in data/, using the Haiku-derived domain as
ground truth, this classifier agrees ~49% of the time. The residual error is
structural rather than fixable by better cues: the LLM labels a document by what
it is *for* (a budget review, an escalation) while keyword matching labels it by
what it *talks about*, and at a wafer-handling company every document talks about
wafer handling. Inverse-document-frequency weighting measured ~57%, but needs
corpus-wide statistics and a two-pass ingest -- not worth the complexity for a
path whose entire contract is "degraded, and says so".
"""

import re
from functools import lru_cache

from app.enrichment.schema import DerivedActionItem, DerivedDecision, DocumentEnrichment
from app.enrichment.taxonomy import (
    DOMAIN_CUES,
    HIGH_PRIORITY_CUES,
    LOW_PRIORITY_CUES,
)
from app.ingestion.common import Document

DECISION_CUES = re.compile(
    r"\b(we(?:'ll| will| are going to)|decided|decision|agreed|let's go with|"
    r"approved|sign(?:ing|ed) off|we're going with|final call|resolved to)\b",
    re.I,
)
ACTION_CUES = re.compile(
    r"\b(action item|action:|todo|to-do|follow up|follow-up|will take|"
    r"i'll |i will |can you |please |needs to|owns? this|by (?:end of )?"
    r"(?:monday|tuesday|wednesday|thursday|friday|next week|the week|q[1-4]))\b",
    re.I,
)
OWNER_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:will|to|owns|is going to|takes)\b")
# "They will, and I will hold the line" matches OWNER_RE and would create a
# person row called "They" that routing could later resolve against. A
# fabricated name on a citation is worse than no owner at all.
NOT_OWNERS = {
    "they", "we", "he", "she", "it", "this", "that", "these", "those", "you",
    "everyone", "someone", "nobody", "anyone", "somebody", "who", "there",
    "engineering", "product", "support", "finance", "operations", "sales",
}
DUE_RE = re.compile(
    r"\b(?:by|before|due)\s+((?:end of\s+)?(?:Q[1-4]|\w+day|next week|"
    r"\d{4}-\d{2}-\d{2}|\w+ \d{1,2}(?:st|nd|rd|th)?))\b",
    re.I,
)
DRAFT_RE = re.compile(r"\b(draft|wip|work in progress|tbd|placeholder|todo)\b", re.I)
STALE_RE = re.compile(r"\b(superseded|out of date|outdated|no longer accurate|deprecated|obsolete)\b", re.I)
CONTRADICTION_RE = re.compile(
    r"\b(contradict|doesn'?t match|disagree|inconsistent|conflicts? with|"
    r"that'?s not what|differs from)\b",
    re.I,
)

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


# Short industry acronyms are the whole point of this vocabulary, and plain
# substring matching makes them useless: "ate" (automated test equipment) fires
# 237 times across data/ with zero real hits -- 51 of them inside the customer
# name "Northgate", which would push every escalation document into
# test_cell_handler. Likewise "eda" inside the supplier "Kaneda", "arr" inside
# "carrying", "capa" inside "capacity", "api" inside "capital", "req" inside
# "requirement". Cues therefore match on word boundaries, with a small suffix
# allowance so "wafer" still finds "wafers" and "deploy" finds "deployment".
_SUFFIX = r"(?:s|es|ed|d|ing|ments?|ers?)?"


@lru_cache(maxsize=512)
def _cue_pattern(cue: str) -> re.Pattern[str]:
    parts = [re.escape(p) for p in re.split(r"[^a-z0-9]+", cue.lower()) if p]
    body = r"[\s\-]+".join(parts)
    return re.compile(rf"\b{body}{_SUFFIX}\b", re.I)


def _count_cue(text: str, cue: str) -> int:
    return len(_cue_pattern(cue).findall(text))


def _has_cue(text: str, cue: str) -> bool:
    return _cue_pattern(cue).search(text) is not None


def _classify_domain(text: str) -> str:
    """Rank by how many *distinct* cues appear, not raw occurrences.

    Counting occurrences lets structural boilerplate win: a budget spreadsheet
    with a "Quarter" column repeated on every band scores 20+ on the single
    product_roadmap cue "quarter" and beats finance_budget's several genuine
    matches. Distinct-cue breadth is the better signal; total occurrences only
    break ties.
    """
    scores: dict[str, tuple[int, int]] = {}
    for domain, cues in DOMAIN_CUES.items():
        hits = [_count_cue(text, cue) for cue in cues]
        distinct = sum(1 for h in hits if h)
        scores[domain] = (distinct, sum(hits))
    best = max(scores, key=lambda d: scores[d])
    return best if scores[best][0] > 0 else "other"


def _classify_priority(text: str) -> str:
    # Same boundary rule as domains: "p0" must not match inside a part number.
    if any(_has_cue(text, cue) for cue in HIGH_PRIORITY_CUES):
        return "high"
    if any(_has_cue(text, cue) for cue in LOW_PRIORITY_CUES):
        return "low"
    return "medium" if len(text) > 1500 else "unspecified"


def _candidate_sentences(document: Document) -> list[str]:
    sentences: list[str] = []
    for section in document.sections:
        prefix = f"{section.speaker}: " if section.speaker else ""
        for sentence in SENTENCE_SPLIT.split(section.text.replace("\n", " ")):
            sentence = sentence.strip()
            if 20 <= len(sentence) <= 400:
                sentences.append(prefix + sentence)
    return sentences


def _summarise(document: Document, sentences: list[str]) -> str:
    lead = [s for s in sentences[:12] if len(s) > 40][:3]
    if not lead:
        lead = sentences[:2]
    body = " ".join(lead) if lead else document.raw_text[:280].strip()
    return f"[Heuristic summary] {body}".strip()


def enrich_heuristically(document: Document) -> DocumentEnrichment:
    text = document.raw_text
    sentences = _candidate_sentences(document)

    decisions = [
        DerivedDecision(text=s, decided_by=None, evidence=s)
        for s in sentences
        if DECISION_CUES.search(s)
    ][:8]

    action_items: list[DerivedActionItem] = []
    for sentence in sentences:
        if not ACTION_CUES.search(sentence):
            continue
        owner_match = OWNER_RE.search(sentence)
        owner = owner_match.group(1) if owner_match else None
        if owner and owner.casefold() in NOT_OWNERS:
            owner = None
        due_match = DUE_RE.search(sentence)
        action_items.append(
            DerivedActionItem(
                text=sentence,
                owner=owner,
                due_date=due_match.group(1) if due_match else None,
                evidence=sentence,
            )
        )
        if len(action_items) >= 10:
            break

    flags: list[str] = []
    if len(text.strip()) < 400:
        flags.append("sparse")
    if not document.attendees_or_author:
        flags.append("unattributed")
    if DRAFT_RE.search(text):
        flags.append("draft")
    if STALE_RE.search(text):
        flags.append("stale")
    if CONTRADICTION_RE.search(text):
        flags.append("contradictory")

    return DocumentEnrichment(
        topic_domain=_classify_domain(text),
        priority=_classify_priority(text),
        summary=_summarise(document, sentences),
        decisions=decisions,
        action_items=action_items,
        quality_flags=flags,
        # Cue matching cannot tell a decision from someone describing one, so the
        # ceiling here is deliberately low.
        source_quality=0.35,
    )
