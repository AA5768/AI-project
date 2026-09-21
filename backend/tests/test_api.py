"""Part 2's exit criteria as assertions: query -> citation -> routing ->
correction -> gap retrieval -> metrics, through the real app.

Runs with no API key, so synthesis takes the deterministic extractive path and
the suite stays offline. The confidence threshold is moved per test rather than
relying on where the miniature corpus happens to land: what is being tested is
that the gate is wired to the computed score, not what that score is for five
toy documents.
"""

import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

ANSWERABLE = "what is blocking the end effector pilot?"
UNANSWERABLE = "what is our parental leave policy in Portugal?"


@pytest.fixture
def client(ingested_db, tmp_path, monkeypatch):
    """A client over a private copy of the shared corpus database.

    Copied per test because these exercise writes (query_log, gaps,
    corrections) and each test asserts on counts.
    """
    db = tmp_path / "api.db"
    shutil.copy(ingested_db, db)
    monkeypatch.setattr(settings, "db_path", db)
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    with TestClient(app) as test_client:
        yield test_client


def _ask(client, text: str, threshold: float, monkeypatch) -> dict:
    monkeypatch.setattr(settings, "confidence_threshold", threshold)
    response = client.post("/query", json={"text": text})
    assert response.status_code == 200, response.text
    return response.json()


# ----------------------------------------------------------------- answering


def test_answer_carries_citations_that_resolve_to_real_rows(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.0, monkeypatch)

    assert body["answer"]
    assert body["routing"] is None
    assert body["citations"]

    for citation in body["citations"]:
        document = client.get(f"/documents/{citation['document_id']}")
        assert document.status_code == 200
        assert document.json()["source_path"] == citation["source_path"]
        # The anchor must name a real location inside that document.
        anchors = {chunk["source_anchor"] for chunk in document.json()["chunks"]}
        assert citation["anchor"] in anchors


def test_claims_index_into_the_citation_list(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    assert body["claims"]
    for claim in body["claims"]:
        assert claim["text"]
        for index in claim["citations"]:
            assert 0 <= index < len(body["citations"])


def test_citation_names_the_people_the_source_records(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    citation = body["citations"][0]
    document = client.get(f"/documents/{citation['document_id']}").json()
    assert citation["author_or_attendees"] == document["attendees_or_author"]


def test_derived_metadata_comes_from_the_stored_enrichment(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    metadata = body["derived_metadata"]
    assert metadata["documents"]
    assert metadata["source_types"]
    document = client.get(f"/documents/{metadata['documents'][0]['document_id']}").json()
    assert metadata["documents"][0]["topic_domain"] == document["topic_domain"]


def test_confidence_is_computed_not_constant(client, monkeypatch):
    strong = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    weak = _ask(client, UNANSWERABLE, 0.0, monkeypatch)
    assert weak["confidence"] < strong["confidence"]
    assert strong["confidence_breakdown"]["top_similarity"] > 0


def test_breakdown_explains_the_confidence_it_reports(client, monkeypatch):
    """The breakdown must derive the number the caller was given.

    Regression: it used to carry only the retrieval signal, so a query that
    retrieved well but drafted an ungrounded answer reported `value` 0.81 next
    to a `confidence` of 0.28, with no field in between accounting for the gap.
    """
    body = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    breakdown = body["confidence_breakdown"]

    assert breakdown["value"] == body["confidence"]
    assert breakdown["retrieval_confidence"] >= breakdown["value"]
    product = breakdown["retrieval_confidence"] * breakdown["grounding_multiplier"]
    assert breakdown["value"] == pytest.approx(product, abs=1e-4)


def test_breakdown_reports_no_grounding_when_no_draft_was_written(client, monkeypatch):
    """Gate 1 routing never calls the model, so grounding is unmeasured, not 0."""
    body = _ask(client, UNANSWERABLE, 0.99, monkeypatch)
    breakdown = body["confidence_breakdown"]

    assert breakdown["answer_support"] is None
    assert breakdown["grounding_multiplier"] is None
    assert breakdown["value"] == breakdown["retrieval_confidence"] == body["confidence"]


def test_response_shape_is_identical_across_source_types(client, monkeypatch):
    """A spreadsheet answer and a transcript answer are the same object."""
    transcript = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    spreadsheet = _ask(client, "how many open engineering reqs are there?", 0.0, monkeypatch)
    assert {c["source_type"] for c in spreadsheet["citations"]} != set()
    assert set(transcript) == set(spreadsheet)
    assert set(transcript["citations"][0]) == set(spreadsheet["citations"][0])


def test_empty_query_is_rejected(client):
    assert client.post("/query", json={"text": "   "}).status_code == 422


# ------------------------------------------------------------------- routing


def test_low_confidence_routes_instead_of_answering(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.99, monkeypatch)

    assert body["answer"] is None
    routing = body["routing"]
    assert routing, body
    assert routing["draft_question"]
    assert routing["matched_content"]
    assert body["gap_id"]


def test_routing_rationale_quotes_the_content_that_chose_the_person(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.99, monkeypatch)
    routing = body["routing"]

    # The person is a row in `people`, reached through the matched document.
    document = client.get(f"/documents/{routing['matched_document_id']}").json()
    assert routing["person"] in {person["name"] for person in document["people"]}

    # And the rationale quotes text that is actually in one of that document's
    # stored chunks -- the same rows a citation would point at.
    quoted = " ".join(routing["rationale"].split('"')[1].split())[:60]
    stored = [" ".join(chunk["text"].split()) for chunk in document["chunks"]]
    assert any(quoted in text for text in stored), quoted
    assert " ".join(routing["matched_content"].split())[:60] in " ".join(stored)


def test_nothing_relevant_means_no_routee_is_invented(client, monkeypatch):
    body = _ask(client, UNANSWERABLE, 0.99, monkeypatch)
    assert body["answer"] is None
    assert body["routing"] is None
    assert body["gap_id"], "the gap is still recorded"
    assert body["derived_metadata"]["routing_unavailable"]


def test_routing_send_refuses_an_unknown_recipient(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.99, monkeypatch)
    payload = {"query_id": body["query_id"], "person": "Nobody Atall", "question": "hi"}
    assert client.post("/routing/send", json=payload).status_code == 404

    payload["person"] = body["routing"]["person"]
    sent = client.post("/routing/send", json=payload)
    assert sent.status_code == 200
    assert sent.json()["simulated"] is True


# ----------------------------------------------------------- gaps/corrections


def test_gap_is_recorded_with_its_query_and_can_be_resolved(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.99, monkeypatch)

    gaps = client.get("/gaps", params={"status": "open"}).json()
    assert [gap for gap in gaps if gap["id"] == body["gap_id"]]
    gap = next(gap for gap in gaps if gap["id"] == body["gap_id"])
    assert gap["query_text"] == ANSWERABLE
    assert gap["reason"]

    patched = client.patch(f"/gaps/{gap['id']}", json={"status": "resolved"})
    assert patched.status_code == 200
    assert patched.json()["resolved_at"]

    assert not [g for g in client.get("/gaps", params={"status": "open"}).json() if g["id"] == gap["id"]]
    assert [g for g in client.get("/gaps", params={"status": "resolved"}).json() if g["id"] == gap["id"]]


def test_gap_rejects_an_unknown_status(client):
    assert client.get("/gaps", params={"status": "banana"}).status_code == 422
    assert client.patch("/gaps/1", json={"status": "banana"}).status_code == 422


def test_correction_is_tied_to_the_original_answer(client, monkeypatch):
    body = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    response = client.post(
        "/corrections",
        json={
            "query_id": body["query_id"],
            "corrected_answer": "It was the gripper, not the controller.",
            "corrected_by": "priya.raman",
        },
    )
    assert response.status_code == 201
    correction = response.json()
    assert correction["original_answer"] == body["answer"]
    assert correction["query_text"] == ANSWERABLE

    listed = client.get("/corrections", params={"query_id": body["query_id"]}).json()
    assert [c for c in listed if c["id"] == correction["id"]]


def test_correction_against_an_unknown_query_is_rejected(client):
    response = client.post(
        "/corrections",
        json={"query_id": 999999, "corrected_answer": "x", "corrected_by": "y"},
    )
    assert response.status_code == 404


def test_unknown_document_is_404(client):
    assert client.get("/documents/999999").status_code == 404


# ------------------------------------------------------------------- metrics


def test_metrics_reflect_what_actually_happened(client, monkeypatch):
    answered = _ask(client, ANSWERABLE, 0.0, monkeypatch)
    _ask(client, ANSWERABLE, 0.99, monkeypatch)
    client.post(
        "/corrections",
        json={
            "query_id": answered["query_id"],
            "corrected_answer": "corrected",
            "corrected_by": "tester",
        },
    )

    metrics = client.get("/metrics").json()
    queries = metrics["queries"]
    assert queries["total"] == 2
    assert queries["routing_rate"] == 0.5
    assert queries["correction_rate"] == 0.5
    assert queries["answered_without_intervention"] == 0.0
    assert queries["recent"]["latency_p50_ms"] is not None
    assert queries["confidence_trend"]

    assert metrics["gaps"]["open"] == 1
    assert metrics["corrections"]["total"] == 1

    ingestion = metrics["ingestion"]
    assert ingestion["documents"] == 5
    assert ingestion["chunks"] > 0
    assert ingestion["last_run"]["parse_failures"] == 0
    assert ingestion["enrichment_methods"] == {"heuristic": 5}
    assert metrics["confidence_threshold"] == settings.confidence_threshold


def test_metrics_are_serveable_on_an_untouched_database(client):
    metrics = client.get("/metrics").json()
    assert metrics["queries"]["total"] == 0
    assert metrics["queries"]["routing_rate"] is None
    assert metrics["ingestion"]["documents"] == 5


# --------------------------------------------------------------------- CORS


@pytest.mark.parametrize(
    "origin",
    [
        "http://localhost:5173",
        "http://localhost:5174",  # where Vite lands when 5173 is taken
        "http://127.0.0.1:8080",
    ],
)
def test_any_localhost_port_may_call_the_api(client, origin):
    """The dev server does not own a fixed port.

    `allow_origins` was pinned to 5173, so starting Vite anywhere else -- which
    it does by itself when 5173 is busy -- failed every request on CORS and
    surfaced as "Cannot reach the API", pointing at the wrong problem.
    """
    preflight = client.options(
        "/query",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200, preflight.text
    assert preflight.headers["access-control-allow-origin"] == origin


@pytest.mark.parametrize(
    "origin",
    ["http://localhost.example.com", "https://evil.test", "http://notlocalhost:5173"],
)
def test_a_non_local_origin_is_still_refused(client, origin):
    """Permissive about the port, not about the host."""
    preflight = client.options(
        "/query",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in preflight.headers


def test_an_explicit_allowlist_overrides_the_localhost_default():
    """The escape hatch for running this anywhere but a laptop."""
    from app.config import Settings

    configured = Settings(cors_allow_origins="https://kb.example.com, https://kb2.example.com")
    assert configured.cors_origins == ["https://kb.example.com", "https://kb2.example.com"]
    assert Settings(cors_allow_origins="").cors_origins == []
