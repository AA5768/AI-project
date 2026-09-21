"""Correction capture (PROJECT_INSTRUCTIONS.md Part 2 section 4).

A correction is stored against the `query_log` row it corrects, with the
original answer copied in at write time. Keeping the original here rather than
only in query_log means the pair stays readable even if the query is re-run
later: what the system said, what a human said instead, and who said it.
"""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import db
from app.db import repository

router = APIRouter(tags=["corrections"])


class CorrectionRequest(BaseModel):
    query_id: int
    corrected_answer: str = Field(min_length=1)
    corrected_by: str = Field(min_length=1, max_length=200)


def _serialize(row: sqlite3.Row) -> dict:
    return dict(row)


@router.post("/corrections", status_code=201)
def create_correction(request: CorrectionRequest, conn: sqlite3.Connection = Depends(db)):
    query = repository.get_query(conn, request.query_id)
    if query is None:
        raise HTTPException(status_code=404, detail=f"no query with id {request.query_id}")

    correction_id = repository.record_correction(
        conn,
        query_id=request.query_id,
        original_answer=query["answer"],
        corrected_answer=request.corrected_answer,
        corrected_by=request.corrected_by,
    )
    conn.commit()
    rows = repository.list_corrections(conn, query_id=request.query_id, limit=50)
    created = next((row for row in rows if int(row["id"]) == correction_id), None)
    return _serialize(created) if created is not None else {"id": correction_id}


@router.get("/corrections")
def list_corrections(
    query_id: int | None = None,
    corrected_by: str | None = None,
    since: str | None = Query(default=None, description="ISO-8601 timestamp, inclusive."),
    limit: int = Query(default=100, ge=1, le=500),
    conn: sqlite3.Connection = Depends(db),
):
    return [_serialize(row) for row in repository.list_corrections(
        conn, query_id=query_id, corrected_by=corrected_by, since=since, limit=limit
    )]
