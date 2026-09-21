# API Reference

HTTP contract for the Meridian Microsystems Knowledge API
(`backend/app/main.py`, FastAPI).

- **Base URL (dev):** `http://localhost:8000`
- **Content type:** `application/json` on every request body and response
- **Auth:** none. The service is a single-tenant local app; put it behind
  something else before exposing it.
- **Interactive docs:** `GET /docs` (Swagger UI), `GET /openapi.json`

## Conventions

| Topic | Rule |
| --- | --- |
| Timestamps | ISO-8601 UTC, second precision, e.g. `2026-09-21T09:14:03+00:00`. Written by `repository.utcnow()`. |
| Ids | Integers, SQLite `AUTOINCREMENT` rowids. |
| Confidence | Float `0.0–1.0`, rounded to 4 dp. Compare against `confidence_threshold` (default `0.55`, `Settings.confidence_threshold`). |
| Enums | `source_type`: `transcript \| docx \| pptx \| xlsx`. `priority`: `high \| medium \| low \| unspecified`. `role`: `author \| attendee \| action_owner`. `topic_domain` / `quality_flags`: see `backend/app/enrichment/taxonomy.py`. |
| Errors | FastAPI shape. `HTTPException` → `{"detail": "<string>"}`. Request-validation failures → `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` with status `422`. |
| CORS | `settings.cors_allow_origins` (comma-separated) when set; otherwise any `http://localhost:*` / `http://127.0.0.1:*` origin. Credentials are never accepted. |

### Status codes used

| Code | When |
| --- | --- |
| `200` | Success. |
| `201` | `POST /corrections` only. |
| `404` | A referenced row does not exist (`document_id`, `query_id`, `gap_id`, or a `person` name not in the corpus). |
| `422` | Body or query-parameter validation failed, including empty/whitespace query text and an out-of-range `status`. |

---

## Endpoint index

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness probe. |
| `POST` | `/query` | Ask a question: answer with citations, or route to a human. |
| `GET` | `/documents/{document_id}` | Full provenance behind a citation. |
| `POST` | `/routing/send` | Simulated hand-off of a routed question. |
| `GET` | `/gaps` | Unanswered-question work queue. |
| `PATCH` | `/gaps/{gap_id}` | Open/resolve a gap. |
| `POST` | `/corrections` | Record a human correction of an answer. |
| `GET` | `/corrections` | List corrections. |
| `GET` | `/metrics` | Quality and degradation snapshot. |

---

## `GET /health`

Liveness only — it does not touch the database.

```json
{ "status": "ok" }
```

---

## `POST /query`

The core endpoint. Runs hybrid retrieval, computes confidence, and then either
synthesises an answer or routes the question to a person. **The response shape
is the same either way**; the caller branches on `confidence` vs
`confidence_threshold`, or equivalently on `answer !== null`.

Source format never leaks into the contract: a spreadsheet cell range and a
transcript turn come back as the same `Citation`.

### Request

| Field | Type | Required | Constraints |
| --- | --- | --- | --- |
| `text` | string | yes | 1–2000 chars, not whitespace-only |
| `top_k` | integer | no | 1–25, default `8` |

```bash
curl -s localhost:8000/query -H 'Content-Type: application/json' \
  -d '{"text":"Why did the Helios-3 particle excursion happen?"}'
```

### Response `200`

| Field | Type | Notes |
| --- | --- | --- |
| `query_id` | int | Row in `query_log`. Pass this to `/corrections` and `/routing/send`. |
| `answer` | string \| null | `null` whenever the question was routed. |
| `confidence` | float | Final score, **after** the grounding gate. |
| `confidence_threshold` | float | The threshold this deployment used. |
| `confidence_breakdown` | object | See below. |
| `claims` | `Claim[]` | Empty when routed. |
| `citations` | `Citation[]` | Never empty when retrieval returned anything — a routed query still shows the top 3 chunks it looked at. |
| `derived_metadata` | object | See below. |
| `routing` | `Routing` \| null | Present only when routed *and* a person could be justified. |
| `gap_id` | int \| null | Row in `gaps`; set on every routed query, including ones with no routee. |
| `latency_ms` | int | Server-side wall clock for the whole pipeline. |

#### `Claim`

| Field | Type | Notes |
| --- | --- | --- |
| `text` | string | One self-contained sentence of the answer. |
| `citations` | int[] | **Indices into the `citations` array**, not chunk ids. |

#### `Citation`

Every field is read off a stored row — nothing here is model-generated, which
is what makes a citation checkable.

| Field | Type | Notes |
| --- | --- | --- |
| `chunk_id` | int | `chunks.id`. |
| `document_id` | int | Open it with `GET /documents/{id}`. |
| `source_path` | string | Repo-relative POSIX path. |
| `source_type` | string | `transcript \| docx \| pptx \| xlsx`. |
| `title` | string \| null | |
| `author_or_attendees` | string[] | Verbatim from the file, never inferred. |
| `anchor` | string | Human-resolvable locator: `"lines 12-18"`, `"slide 3"`, `"Budget cells A4:D9"`. |
| `date` | string \| null | As recorded in the source. |
| `excerpt` | string | First 700 chars of the chunk. |
| `score` | float | Fused retrieval score, `0–1`. |
| `source_confidence` | float | `documents.enrichment_confidence`. |
| `quality_flags` | string[] | e.g. `["stale","draft"]`. |

#### `Routing`

| Field | Type | Notes |
| --- | --- | --- |
| `person`, `person_id` | string, int \| null | Chosen by walking `chunks → documents → document_people → people`, never by asking a model. |
| `title`, `department`, `email` | string \| null | From `people` (seeded by `data/people.yaml`). |
| `role` | string | How the corpus connects them: `author \| attendee \| action_owner`. |
| `rationale` | string | Quotes the passage that justifies the pick. |
| `matched_content` | string | Up to 600 chars of the matched chunk. |
| `matched_document_id`, `matched_source_path`, `matched_anchor` | | Where that passage lives. |
| `draft_question` | string | Message for a human to edit before sending. LLM-phrased when a key is set, templated otherwise. |
| `reason` | string | Why the query was routed at all. |
| `gap_id` | int \| null | Same value as the top-level `gap_id`. |

#### `confidence_breakdown`

Two gates produce the final number:

```
confidence = retrieval_confidence × grounding_multiplier
grounding_multiplier = 0.35 + 0.65 × answer_support
```

| Field | Type | Notes |
| --- | --- | --- |
| `value` | float | The figure actually used — identical to top-level `confidence`. |
| `retrieval_confidence` | float | Gate 1, from `compute_confidence`. |
| `top_similarity`, `support`, `corroboration`, `source_trust` | float | The four retrieval signals, weighted `0.40 / 0.20 / 0.15 / 0.25`. |
| `matched_documents` | int | Distinct documents in the retrieved set. |
| `reasons` | string[] | Plain-language weaknesses, e.g. *"only one document supports this"*. |
| `answer_support` | float \| null | Gate 2: the grounded fraction of the draft. `null` when retrieval fell short on its own, so no draft was ever written. |
| `grounding_multiplier` | float \| null | `null` for the same reason. |
| `ungrounded_floor` | float | `0.35`. |

#### `derived_metadata`

| Field | Type | Notes |
| --- | --- | --- |
| `topic_domain` | string \| null | Score-weighted winner across cited documents. |
| `topic_domains` | string[] | All of them, strongest first. |
| `priority` | string \| null | Highest across cited documents. |
| `source_types` | string[] | Which corpora the answer drew on. |
| `quality_flags` | string[] | Union across cited documents. |
| `date_range` | `{earliest, latest}` \| null | |
| `documents` | object[] | Per cited document: `document_id`, `source_path`, `title`, `date`, `topic_domain`, `priority`, `enrichment_confidence`, `quality_flags`. |
| `retrieved_chunks` | int | How many chunks were considered. |
| `answer_method` | `"llm" \| "extractive"` \| null | `extractive` = no API key, or synthesis failed. |
| `answer_model` | string \| null | |
| `answer_support` | float | |
| `caveat` | string \| null | Source conflict or staleness warning a reader needs. |
| `routing_unavailable` | string | **Only present** when the query was routed and nothing matched closely enough to name a person. |

### Errors

- `422` — empty/whitespace `text`, `text` over 2000 chars, `top_k` out of range.

---

## `GET /documents/{document_id}`

The other half of traceability: everything behind a citation, so a claim can be
checked against the file.

| Query param | Type | Default | Notes |
| --- | --- | --- | --- |
| `include_raw_text` | bool | `true` | Set `false` to omit the full source text. |

### Response `200`

All columns of the `documents` row, plus:

| Field | Type | Notes |
| --- | --- | --- |
| `attendees_or_author` | string[] | Parsed from the stored JSON. |
| `quality_flags` | string[] | Parsed from the stored JSON. |
| `raw_text` | string | Omitted when `include_raw_text=false`. |
| `chunks` | object[] | `id`, `chunk_index`, `text`, `source_anchor`, `char_count`, in reading order. |
| `people` | object[] | `id`, `name`, `title`, `department`, `email`, `role`. |
| `decisions` | object[] | `id`, `text`, `decided_by`, `evidence`, `evidence_verified`. |
| `action_items` | object[] | `id`, `text`, `owner`, `due_date`, `evidence`, `evidence_verified`. |

Scalar document fields: `id`, `source_path`, `source_type`, `title`, `date`,
`topic_domain`, `priority`, `summary`, `enrichment_method`, `enrichment_model`,
`enrichment_confidence`, `ingested_at`.

> **Evidence rule.** `evidence_verified` is a boolean. When it is `false`, the
> model's quote could not be located in `raw_text`, and `evidence` is forced to
> `null` in the response — an unverifiable quote is exactly what a provenance
> view must not display as source text.

### Errors

- `404` — `{"detail": "no document with id 999"}`

---

## `POST /routing/send`

Simulated hand-off. Delivery is a stub that logs, but the **addressing is
real**: the recipient is looked up in `people`, so sending to someone the corpus
has never recorded fails here rather than silently going nowhere. The gap stays
`open` — sending is not answering.

### Request

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `query_id` | int | yes | Must exist in `query_log`. |
| `person` | string | yes | Matched case-insensitively against `people.name`. |
| `question` | string | yes | Usually the edited `routing.draft_question`. |
| `gap_id` | int \| null | no | Carried through for the log line. |

### Response `200`

```json
{
  "status": "sent",
  "simulated": true,
  "to": "dana.okafor@meridianmicro.example",
  "person": "Dana Okafor",
  "query_id": 42,
  "gap_id": 17,
  "question": "Hi Dana — ..."
}
```

`to` is the person's email, falling back to their name when the directory has
no address.

### Errors

- `404` — unknown `query_id`.
- `404` — `{"detail": "'Nobody' is not someone the corpus records; refusing to send"}`

---

## `GET /gaps`

The review queue: questions the system could not answer, newest first, joined to
the query that produced them.

| Query param | Type | Default | Notes |
| --- | --- | --- | --- |
| `status` | string | — | `open` or `resolved`. Anything else → `422`. |
| `since` | string | — | ISO-8601, inclusive, compared against `created_at`. |
| `limit` | int | `100` | 1–500. |

### Response `200` — array of

| Field | Source | Notes |
| --- | --- | --- |
| `id`, `query_id`, `reason`, `status`, `created_at`, `resolved_at` | `gaps` | `resolved_at` is `null` while open. |
| `suggested_routing_person`, `suggested_person_id`, `routing_rationale`, `matched_content`, `draft_question` | `gaps` | All `null` when no routee could be justified. |
| `query_text`, `confidence`, `query_timestamp` | `query_log` | The join is the point: a bare reason string is untriageable. |
| `person_title`, `person_department`, `person_email` | `people` | `null` when there is no suggested person. |

---

## `PATCH /gaps/{gap_id}`

### Request

```json
{ "status": "resolved" }
```

`status` must be `open` or `resolved`. Setting `resolved` stamps `resolved_at`;
setting `open` clears it back to `null`.

### Response `200`

The updated `gaps` row (no join).

### Errors

- `422` — `{"detail": "status must be one of ['open', 'resolved']"}`
- `404` — unknown `gap_id`.

---

## `POST /corrections`

Stores what a human said instead of what the system said. The original answer is
copied in at write time, so the pair stays readable even if the query is re-run
later.

### Request

| Field | Type | Required | Constraints |
| --- | --- | --- | --- |
| `query_id` | int | yes | Must exist in `query_log`. |
| `corrected_answer` | string | yes | Non-empty. |
| `corrected_by` | string | yes | 1–200 chars. |

### Response `201`

The stored row joined to its query: `id`, `query_id`, `original_answer`,
`corrected_answer`, `corrected_by`, `timestamp`, `query_text`, `confidence`.

### Errors

- `404` — unknown `query_id`.

---

## `GET /corrections`

| Query param | Type | Default | Notes |
| --- | --- | --- | --- |
| `query_id` | int | — | Exact match. |
| `corrected_by` | string | — | Exact match (case-sensitive). |
| `since` | string | — | ISO-8601, inclusive, compared against `timestamp`. |
| `limit` | int | `100` | 1–500. |

Returns an array of the same shape as `POST /corrections`, newest first.

---

## `GET /metrics`

The degradation tripwire. Everything is aggregated from rows the system already
writes — nothing is sampled or estimated.

| Query param | Type | Default | Notes |
| --- | --- | --- | --- |
| `window` | int | `50` | 1–1000. How many recent queries the trailing view covers. |

### Response `200`

```jsonc
{
  "generated_at": "2026-09-21T09:14:03+00:00",
  "confidence_threshold": 0.55,
  "queries": {
    "total": 128,
    "avg_confidence": 0.6112,
    "routing_rate": 0.2031,
    "correction_rate": 0.0391,
    "answered_without_intervention": 0.7734,
    "recent": {
      "window": 50, "count": 50,
      "avg_confidence": 0.58, "routing_rate": 0.26,
      "correction_rate": 0.04, "answered_without_intervention": 0.72,
      "latency_p50_ms": 1840, "latency_p95_ms": 4210
    },
    "confidence_trend": [
      { "date": "2026-09-21", "queries": 12, "avg_confidence": 0.61, "routing_rate": 0.25 }
    ],
    "lowest_confidence": [
      { "query_id": 91, "query_text": "...", "confidence": 0.18, "routed": true,
        "timestamp": "2026-09-20T16:02:11+00:00" }
    ]
  },
  "gaps":        { "open": 14, "resolved": 12, "total": 26 },
  "corrections": { "total": 6, "corrected_queries": 5 },
  "ingestion": {
    "last_run": { /* the whole ingestion_runs row, or null */ },
    "documents": 37,
    "chunks": 412,
    "enrichment_methods": { "llm": 35, "heuristic": 2 },
    "enrichment_confidence_avg": 0.72,
    "enrichment_confidence_min": 0.31,
    "fell_back": 2,
    "low_confidence_documents": [
      { "document_id": 18, "source_path": "data/office/...", 
        "enrichment_confidence": 0.29, "quality_flags": ["sparse","unattributed"] }
    ]
  }
}
```

Notes on the numbers:

- **Two horizons on purpose.** All-time figures are the baseline; the trailing
  `window` is what moves first. A routing rate of 5% all-time and 40% over the
  last 50 queries is the signal you want before users complain.
- `answered_without_intervention` is counted **per query** (answered, and never
  corrected), not by subtracting two rates — adding them would double-count a
  routed query that someone then corrected.
- Every rate is `null` rather than `0` when its denominator is zero.
- `confidence_trend` is at most the last 14 days, newest first.
- `low_confidence_documents` lists up to 10 documents under `0.5`.

---

## Frontend client

`frontend/src/api/client.js` is the only place the UI knows the API exists.

| Method | Calls |
| --- | --- |
| `api.health()` | `GET /health` |
| `api.query(text)` | `POST /query` |
| `api.getDocument(id)` | `GET /documents/{id}` |
| `api.sendRouting(payload)` | `POST /routing/send` |
| `api.listCorrections()` | `GET /corrections` |
| `api.createCorrection(payload)` | `POST /corrections` |
| `api.listGaps(status)` | `GET /gaps?status=` |
| `api.updateGap(id, status)` | `PATCH /gaps/{id}` |
| `api.getMetrics()` | `GET /metrics` |

Behaviour worth knowing:

- Base URL comes from `VITE_API_BASE_URL`, defaulting to `http://localhost:8000`.
- **GETs retry twice** on a network-level failure (150 ms, 300 ms backoff).
  Writes never retry — a correction stored twice is worse than an error message.
- Errors are thrown as `Error` with a renderable message: FastAPI's `detail`
  when present (validation arrays are joined by `; `), otherwise a
  "cannot reach the API" hint naming the uvicorn command.
- `Content-Type` is only sent on requests with a body, to keep GETs free of a
  CORS preflight.

---

## Smoke test

`scripts/smoke_test.sh` exercises the whole contract end to end against a
running server.
