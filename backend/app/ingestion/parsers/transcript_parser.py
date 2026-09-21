"""Markdown + YAML frontmatter meeting transcripts.

Groups the dialogue into speaker turns rather than raw lines, because a turn is
the smallest unit that still makes sense when quoted back as a citation.
Attendees and date come from the frontmatter verbatim -- enrichment never
re-derives them.
"""

import re
from pathlib import Path

import frontmatter

from app.ingestion.common import Document, Section

# Matches "Priya Raman: ...", "**Priya Raman:** ..." and "**Priya Raman**: ...".
# The bold markers can close on either side of the colon, so both positions are
# optional -- miss the post-colon one and every turn starts with a stray "**".
SPEAKER_RE = re.compile(
    r"^\s{0,3}(?:\*\*)?([A-Z][\w.'\-]*(?:\s+[A-Z][\w.'\-]*){0,3})(?:\*\*)?\s*:\s*(?:\*\*)?\s*(.*)$"
)
HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*)$")

# Labels that look exactly like a one-word speaker ("Action: ship the hotfix").
# Attributing those to a person named "Action" would put a fabricated name on a
# citation, which is the one thing the traceability chain must never do.
NOT_SPEAKERS = {
    "action", "actions", "action item", "action items", "agenda", "attendees",
    "date", "decision", "decisions", "note", "notes", "next", "next steps",
    "present", "recording", "summary", "todo", "to-do", "topic", "time",
    "location", "apologies", "follow up", "follow-up", "context", "background",
}


def _normalise_people(value: object) -> list[str]:
    """Frontmatter attendees may be a list, a comma string, or a list of dicts."""
    if value is None:
        return []
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    if isinstance(value, dict):
        value = [value]
    people: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = item.get("name") or item.get("attendee")
            if name:
                people.append(str(name).strip())
        elif item is not None:
            people.append(str(item).strip())
    return [p for p in people if p]


def parse_transcript(path: Path, source_path: str | None = None) -> Document:
    post = frontmatter.load(path)
    lines = post.content.splitlines()

    sections: list[Section] = []
    heading: str | None = None
    current: Section | None = None

    def close() -> None:
        nonlocal current
        if current and current.text.strip():
            sections.append(current)
        current = None

    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            close()
            continue

        matched_heading = HEADING_RE.match(line)
        if matched_heading:
            close()
            heading = matched_heading.group(2).strip()
            # scope = the heading itself, so it merges with the turns beneath it
            # instead of becoming a one-line orphan chunk.
            sections.append(
                Section(
                    text=heading,
                    kind="line",
                    locator_start=str(lineno),
                    locator_end=str(lineno),
                    scope=heading,
                )
            )
            continue

        matched_speaker = SPEAKER_RE.match(line)
        if matched_speaker and matched_speaker.group(1).strip().lower() not in NOT_SPEAKERS:
            close()
            speaker, said = matched_speaker.group(1).strip(), matched_speaker.group(2).strip()
            current = Section(
                text=said,
                kind="line",
                locator_start=str(lineno),
                locator_end=str(lineno),
                scope=heading,
                speaker=speaker,
            )
            continue

        if current is not None:
            # Continuation of the same speaker turn.
            current.text = f"{current.text}\n{stripped}".strip()
            current.locator_end = str(lineno)
        else:
            sections.append(
                Section(
                    text=stripped,
                    kind="line",
                    locator_start=str(lineno),
                    locator_end=str(lineno),
                    scope=heading,
                )
            )

    close()

    attendees = _normalise_people(
        post.get("attendees") or post.get("participants") or post.get("present")
    )
    date = post.get("date")

    return Document(
        source_path=source_path or str(path),
        source_type="transcript",
        raw_text=post.content,
        sections=sections,
        title=str(post.get("title") or post.get("meeting") or path.stem),
        attendees_or_author=attendees,
        date=str(date) if date is not None else None,
    )
