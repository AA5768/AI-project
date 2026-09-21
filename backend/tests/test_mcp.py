"""The MCP surface, and the property that makes having two surfaces safe.

There is exactly one thing worth testing hard here: that MCP and HTTP are two
transports over one implementation, not two implementations. A second surface
that drifts from the first is worse than no second surface -- the assistant and
the web app would disagree about whether a question is answerable, and only one
of them would be logged the way the metrics assume.
"""

import json
import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

ANSWERABLE = "what is blocking the end effector pilot?"
UNANSWERABLE = "what is our parental leave policy in Portugal?"


@pytest.fixture
def db(ingested_db, tmp_path, monkeypatch):
    """A private copy of the shared corpus: these tests write query_log rows."""
    path = tmp_path / "mcp.db"
    shutil.copy(ingested_db, path)
    monkeypatch.setattr(settings, "db_path", path)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    return path


async def _call(tool: str, **arguments) -> str:
    from app.mcp_server import mcp

    result = await mcp.call_tool(tool, arguments)
    return result.content[0].text


def _payload(text: str) -> dict:
    """The JSON half of an `ask` response, after the rendered prose."""
    return json.loads(text.split("\n---\n", 1)[1])


@pytest.mark.anyio
async def test_the_tools_are_registered(db):
    from app.mcp_server import mcp

    names = {tool.name for tool in await mcp.list_tools()}
    assert names == {"ask", "read_document", "open_gaps", "health"}


@pytest.mark.anyio
async def test_ask_matches_the_http_endpoint_decision_for_decision(db, monkeypatch):
    """Same question, same corpus, same verdict, same citations.

    Asserted on both branches, because the branch is the thing that could
    diverge: an assistant told a question is answerable when the web app routes
    it would confidently repeat an answer a human was meant to supply.
    """
    monkeypatch.setattr(settings, "confidence_threshold", 0.0)
    with TestClient(app) as client:
        answered_http = client.post("/query", json={"text": ANSWERABLE}).json()
    answered_mcp = _payload(await _call("ask", question=ANSWERABLE))

    assert (answered_mcp["answer"] is None) == (answered_http["answer"] is None)
    assert answered_mcp["confidence"] == answered_http["confidence"]
    assert [c["chunk_id"] for c in answered_mcp["citations"]] == [
        c["chunk_id"] for c in answered_http["citations"]
    ]

    monkeypatch.setattr(settings, "confidence_threshold", 0.99)
    with TestClient(app) as client:
        routed_http = client.post("/query", json={"text": ANSWERABLE}).json()
    routed_mcp = _payload(await _call("ask", question=ANSWERABLE))

    assert routed_mcp["answer"] is None and routed_http["answer"] is None
    assert (routed_mcp["routing"] is None) == (routed_http["routing"] is None)
    if routed_mcp["routing"]:
        assert routed_mcp["routing"]["person"] == routed_http["routing"]["person"]


@pytest.mark.anyio
async def test_ask_logs_the_query_like_any_other_caller(db):
    """MCP traffic has to reach /metrics, or the instrumentation measures the
    web app rather than the system."""
    from app.db.connection import get_connection

    before = _count(db, "SELECT COUNT(*) AS n FROM query_log")
    await _call("ask", question=ANSWERABLE)
    assert _count(db, "SELECT COUNT(*) AS n FROM query_log") == before + 1

    conn = get_connection(db)
    try:
        row = conn.execute(
            "SELECT query_text, confidence, routed FROM query_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row["query_text"] == ANSWERABLE
    assert row["confidence"] is not None


@pytest.mark.anyio
async def test_an_unanswerable_question_records_a_gap_and_names_nobody(db, monkeypatch):
    monkeypatch.setattr(settings, "confidence_threshold", 0.99)
    text = await _call("ask", question=UNANSWERABLE)
    payload = _payload(text)

    assert payload["answer"] is None
    assert payload["routing"] is None
    assert payload["gap_id"]
    assert "Not answerable from the corpus" in text

    gaps = json.loads(await _call("open_gaps"))
    assert any(gap["id"] == payload["gap_id"] for gap in gaps)


@pytest.mark.anyio
async def test_read_document_opens_the_source_behind_a_citation(db, monkeypatch):
    monkeypatch.setattr(settings, "confidence_threshold", 0.0)
    payload = _payload(await _call("ask", question=ANSWERABLE))
    citation = payload["citations"][0]

    document = json.loads(await _call("read_document", document_id=citation["document_id"]))
    assert document["source_path"] == citation["source_path"]
    assert citation["anchor"] in {chunk["source_anchor"] for chunk in document["chunks"]}
    assert "raw_text" not in document  # off by default

    full = json.loads(
        await _call("read_document", document_id=citation["document_id"], include_raw_text=True)
    )
    assert full["raw_text"]


@pytest.mark.anyio
async def test_read_document_withholds_unverified_evidence(db):
    """Same rule as the HTTP route: a quote that could not be located verbatim
    in the source is not shown as source text."""
    from app.db.connection import get_connection

    conn = get_connection(db)
    try:
        ids = [int(r["id"]) for r in conn.execute("SELECT id FROM documents")]
    finally:
        conn.close()

    for document_id in ids:
        document = json.loads(await _call("read_document", document_id=document_id))
        for item in [*document["decisions"], *document["action_items"]]:
            if not item["evidence_verified"]:
                assert item["evidence"] is None


@pytest.mark.anyio
async def test_read_document_reports_a_missing_id_rather_than_raising(db):
    assert "No document with id 999999" in await _call("read_document", document_id=999999)


@pytest.mark.anyio
async def test_health_returns_the_same_snapshot_as_the_metrics_endpoint(db):
    with TestClient(app) as client:
        http = client.get("/metrics").json()
    mcp_snapshot = json.loads(await _call("health"))
    assert mcp_snapshot["confidence_threshold"] == http["confidence_threshold"]
    assert set(mcp_snapshot) == set(http)


def _count(db_path, sql: str) -> int:
    from app.db.connection import get_connection

    conn = get_connection(db_path)
    try:
        return int(conn.execute(sql).fetchone()["n"])
    finally:
        conn.close()


@pytest.fixture
def anyio_backend():
    return "asyncio"
