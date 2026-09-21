"""GET /documents/{id} -- the other half of traceability
(PROJECT_INSTRUCTIONS.md Part 2 section 2).

A citation is only checkable if the thing it points at can be opened, so this
returns the full source context behind one: the stored raw text, every chunk
with its anchor, the verbatim author/attendee list, and the decisions and
action items enrichment derived from it.
"""

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import db
from app.db import repository

router = APIRouter(tags=["documents"])


@router.get("/documents/{document_id}")
def get_document(
    document_id: int,
    include_raw_text: bool = Query(
        default=True, description="Set false to skip the full source text."
    ),
    conn: sqlite3.Connection = Depends(db),
):
    row = repository.get_document(conn, document_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no document with id {document_id}")

    document = dict(row)
    document["attendees_or_author"] = json.loads(document.get("attendees_or_author") or "[]")
    document["quality_flags"] = json.loads(document.get("quality_flags") or "[]")
    if not include_raw_text:
        document.pop("raw_text", None)

    document["chunks"] = [dict(chunk) for chunk in repository.get_document_chunks(conn, document_id)]
    document["people"] = [dict(person) for person in repository.get_document_people(conn, document_id)]
    # Unverified evidence is withheld rather than shown: a quote that could not
    # be located in raw_text is precisely what a provenance view must not
    # present as source text.
    document["decisions"] = [
        dict(decision) for decision in repository.get_document_decisions(conn, document_id)
    ]
    document["action_items"] = [
        dict(action) for action in repository.get_document_action_items(conn, document_id)
    ]
    for item in [*document["decisions"], *document["action_items"]]:
        item["evidence_verified"] = bool(item["evidence_verified"])
        if not item["evidence_verified"]:
            item["evidence"] = None
    return document
