"""Force every `evidence` quote to be real text from the source file.

Claude is told to quote verbatim and mostly does, but across a 37-document run
it paraphrased ~4% of quotes: stitching two non-adjacent spans with an ellipsis,
merging lines from two speakers, or trimming a clause. Those read as citations
and are not -- a UI that highlights the quote in the source finds nothing, which
is precisely the fabricated provenance Part 1 exists to prevent.

So the model's quote is treated as a *pointer*, never as the citation itself.
We locate the span it refers to and store the file's own bytes. Anything that
cannot be located is dropped rather than persisted as an unverifiable quote.
"""

import difflib

# Folded 1:1 so character offsets survive and map back to the original text.
_FOLD = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", " ": " ",
}

MIN_RATIO = 0.70


def _collapse(text: str) -> tuple[str, list[int]]:
    """Whitespace-collapsed, punctuation-folded, casefolded text plus a map from
    each output character back to its index in `text`."""
    chars: list[str] = []
    index_map: list[int] = []
    at_space = True
    for i, char in enumerate(text):
        folded = _FOLD.get(char, char)
        if folded.isspace():
            if at_space:
                continue
            chars.append(" ")
            index_map.append(i)
            at_space = True
        else:
            chars.append(folded.casefold())
            index_map.append(i)
            at_space = False
    while chars and chars[-1] == " ":
        chars.pop()
        index_map.pop()
    return "".join(chars), index_map


def _span(raw_text: str, index_map: list[int], start: int, length: int) -> str:
    first = index_map[start]
    last = index_map[min(start + length, len(index_map)) - 1]
    return raw_text[first : last + 1].strip()


def ground_evidence(
    raw_text: str, evidence: str | None, min_ratio: float = MIN_RATIO
) -> tuple[str | None, bool]:
    """Resolve `evidence` to a verbatim span of `raw_text`.

    Returns `(span, exact)`. `span` is text copied out of the source, so it is
    always findable in the file. `exact` is True when the model quoted correctly
    and False when the span had to be recovered by fuzzy match. `(None, False)`
    means the quote could not be located and must not be presented as a citation.
    """
    if not evidence or not evidence.strip() or not raw_text.strip():
        return None, False

    haystack, index_map = _collapse(raw_text)
    needle, _ = _collapse(evidence)
    if not needle or not haystack:
        return None, False

    found = haystack.find(needle)
    if found != -1:
        return _span(raw_text, index_map, found, len(needle)) or None, True

    # Anchor on the longest shared run, then score a same-length window around it.
    matcher = difflib.SequenceMatcher(None, haystack, needle, autojunk=False)
    anchor = matcher.find_longest_match(0, len(haystack), 0, len(needle))
    if anchor.size == 0:
        return None, False

    start = max(0, anchor.a - anchor.b)
    window = haystack[start : start + len(needle)]
    if difflib.SequenceMatcher(None, window, needle, autojunk=False).ratio() < min_ratio:
        return None, False

    return _span(raw_text, index_map, start, len(window)) or None, False


def ground_items(raw_text: str, items: list) -> tuple[list, int]:
    """Rewrite each item's `evidence` to a real source span in place.

    Items whose quote cannot be located keep their text -- the extracted decision
    may still be correct -- but lose the evidence, so nothing downstream can cite
    them. Returns the surviving items and how many lost their evidence.
    """
    dropped = 0
    for item in items:
        span, _exact = ground_evidence(raw_text, getattr(item, "evidence", None))
        if span is None:
            dropped += 1
        item.evidence = span
    return items, dropped
