"""Gap retrieval and triage (PROJECT_INSTRUCTIONS.md Part 2 section 4).

Gaps are written by the query path whenever confidence fell below threshold,
and read here as a work queue: what was asked, why the system could not answer,
who it suggested, and whether anyone has closed it out.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import db
from app.db import repository

router = APIRouter(tags=["gaps"])

STATUSES = {"open", "resolved"}


class GapStatusUpdate(BaseModel):
    status: str


@router.get("/gaps")
def list_gaps(
    status: str | None = Query(default=None, description="open | resolved"),
    since: str | None = Query(default=None, description="ISO-8601 timestamp, inclusive."),
    limit: int = Query(default=100, ge=1, le=500),
    conn: sqlite3.Connection = Depends(db),
):
    if status is not None and status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(STATUSES)}")
    return [dict(row) for row in repository.list_gaps(conn, status=status, since=since, limit=limit)]


@router.patch("/gaps/{gap_id}")
def update_gap(gap_id: int, update: GapStatusUpdate, conn: sqlite3.Connection = Depends(db)):
    if update.status not in STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(STATUSES)}")
    row = repository.set_gap_status(conn, gap_id, update.status)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no gap with id {gap_id}")
    conn.commit()
    return dict(row)
