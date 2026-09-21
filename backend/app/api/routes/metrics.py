"""GET /metrics -- the degradation tripwire (PROJECT_INSTRUCTIONS.md Part 2
section 5).

Everything here is aggregated from rows the system already writes on its own:
`query_log` for confidence/routing/latency, `corrections` and `gaps` for what
humans had to fix, `ingestion_runs`/`enrichment_log` for whether the corpus
behind it is still healthy. Nothing is sampled or estimated, so the numbers a
lead sees are the numbers that happened.
"""

import sqlite3

from fastapi import APIRouter, Depends, Query

from app.api.deps import db
from app.config import settings
from app.db import repository

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
def get_metrics(
    window: int = Query(
        default=50, ge=1, le=1000, description="How many recent queries the trailing view covers."
    ),
    conn: sqlite3.Connection = Depends(db),
):
    snapshot = repository.metrics_snapshot(conn, window=window)
    snapshot["confidence_threshold"] = settings.confidence_threshold
    return snapshot
