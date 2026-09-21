"""POST /routing/send -- the simulated hand-off to a human.

Delivery is out of scope (PROJECT_INSTRUCTIONS.md Part 3 section 2 says a stub
that logs is enough), but the addressing is not faked: the recipient is looked
up in `people`, so sending to someone the corpus has never heard of fails here
rather than silently going nowhere. The gap the question came from is left open
until a reviewer resolves it -- sending is not answering.
"""

import logging
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import db
from app.db import repository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["routing"])


class RoutingSendRequest(BaseModel):
    query_id: int
    person: str = Field(min_length=1)
    question: str = Field(min_length=1)
    gap_id: int | None = None


@router.post("/routing/send")
def send_routing(request: RoutingSendRequest, conn: sqlite3.Connection = Depends(db)):
    if repository.get_query(conn, request.query_id) is None:
        raise HTTPException(status_code=404, detail=f"no query with id {request.query_id}")

    person = repository.find_person(conn, request.person)
    if person is None:
        raise HTTPException(
            status_code=404,
            detail=f"{request.person!r} is not someone the corpus records; refusing to send",
        )

    recipient = person["email"] or person["name"]
    logger.info(
        "[routing:send] query_id=%s gap_id=%s to=%s question=%r",
        request.query_id,
        request.gap_id,
        recipient,
        request.question,
    )
    return {
        "status": "sent",
        "simulated": True,
        "to": recipient,
        "person": person["name"],
        "query_id": request.query_id,
        "gap_id": request.gap_id,
        "question": request.question,
    }
