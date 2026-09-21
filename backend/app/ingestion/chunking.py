"""Section -> Chunk. Groups adjacent sections up to a target size and keeps the
combined structural anchor, so a retrieved chunk still points at a real place in
the file.

Deliberately not fixed-width token slicing: a transcript speaker turn or a slide
is the unit a person would cite, and splitting mid-turn produces citations that
are technically correct and practically useless.
"""

from app.config import settings
from app.ingestion.common import Chunk, Section


def _merge_anchor(group: list[Section]) -> str:
    first, last = group[0], group[-1]
    if len(group) == 1 or not first.mergeable_with(last):
        if len(group) == 1:
            return first.anchor
        return "; ".join(dict.fromkeys(s.anchor for s in group))
    merged = Section(
        text="",
        kind=first.kind,
        locator_start=first.locator_start,
        locator_end=last.locator_end,
        scope=first.scope,
    )
    return merged.anchor


def _render(group: list[Section]) -> str:
    parts = []
    for section in group:
        if section.speaker:
            parts.append(f"{section.speaker}: {section.text}")
        else:
            parts.append(section.text)
    return "\n".join(parts).strip()


def _split_oversized(section: Section, max_chars: int) -> list[Section]:
    """Break a single section that is longer than the hard cap on paragraph, then
    sentence, then hard-character boundaries. Locators stay put -- the whole piece
    came from one place, so every shard cites that same place."""
    if len(section.text) <= max_chars:
        return [section]

    pieces: list[str] = []
    buffer = ""
    for para in section.text.split("\n"):
        candidate = f"{buffer}\n{para}" if buffer else para
        if len(candidate) <= max_chars:
            buffer = candidate
            continue
        if buffer:
            pieces.append(buffer)
        while len(para) > max_chars:
            cut = para.rfind(". ", 0, max_chars)
            cut = cut + 1 if cut > max_chars // 2 else max_chars
            pieces.append(para[:cut].strip())
            para = para[cut:].lstrip()
        buffer = para
    if buffer:
        pieces.append(buffer)

    return [
        Section(
            text=piece,
            kind=section.kind,
            locator_start=section.locator_start,
            locator_end=section.locator_end,
            scope=section.scope,
            speaker=section.speaker,
        )
        for piece in pieces
        if piece.strip()
    ]


def chunk_sections(
    sections: list[Section],
    target_chars: int | None = None,
    max_chars: int | None = None,
) -> list[Chunk]:
    target = target_chars or settings.chunk_target_chars
    hard_cap = max_chars or settings.chunk_max_chars

    expanded: list[Section] = []
    for section in sections:
        if section.text.strip():
            expanded.extend(_split_oversized(section, hard_cap))

    chunks: list[Chunk] = []
    group: list[Section] = []
    size = 0

    def flush() -> None:
        nonlocal group, size
        if not group:
            return
        text = _render(group)
        if text:
            chunks.append(
                Chunk(index=len(chunks), text=text, source_anchor=_merge_anchor(group))
            )
        group, size = [], 0

    for section in expanded:
        # Start a new chunk when adding this section would overshoot the target,
        # or when the structural context changes (new slide, new sheet, new heading).
        if group and (
            size + len(section.text) > target or not group[-1].mergeable_with(section)
        ):
            flush()
        group.append(section)
        size += len(section.text)

    flush()
    return chunks
