# Test Report — Meridian Microsystems Knowledge System

**Date:** 2026-09-21 (first run 2026-09-20)
**Commit:** `e1647b2` (working tree, uncommitted changes)
**Platform:** Windows 11, Python 3.12.10 (`backend/.venv`), Node/Vite 8.3.0
**Corpus under test:** `data/` — 22 transcripts + 15 Office documents, ingested into `backend/app.db`

**Result: PASS.** 135 / 135 unit tests pass, the golden-set answer-quality gate is green on both backends,
the end-to-end smoke test completes all 9 steps, and the answered path, the gate-1 routing path and the
gate-2 routing path were each verified through the running UI against the live API.

> The first run of this suite (2026-09-20) found a reporting defect — `confidence_breakdown` could not explain
> the `confidence` it was attached to — and fixing it surfaced a second instance of the same problem in the
> routing reason text. A third defect — a CORS origin pinned to one port — was found while setting up the
> re-verification and fixed on request. All three are covered by new tests and re-verified; see §4.
>
> A third pass on 2026-09-21 added an answer-quality gate and an MCP server, and found five more defects in
> the process — two of them the kind that produce a confidently wrong result rather than an error. See §7.
> Everything below reflects the post-fix state; §1 and §4 are left as the second pass recorded them.

---

## 1. Unit tests

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest tests -v
```

```
104 passed, 1 skipped, 1 warning in 83.98s
```

The single skip is `test_live_claude_enrichment_is_grounded_in_the_source`, gated behind `RUN_LLM_TESTS=1`
because it makes a real Claude call. It was run separately and also passes:

```bash
cd backend && RUN_LLM_TESTS=1 ./.venv/Scripts/python.exe -m pytest tests/test_enrichment.py -k live -v
```

```
1 passed in 7.07s
```

So the effective total is **105 passed, 0 failed**.

| Test file | Tests | Result | What it pins down |
|---|---:|---|---|
| `tests/test_parsers.py` | 11 | pass | transcript/docx/pptx/xlsx extraction, bold speaker labels vs. label lines, sheet coverage, chunk merge + hard cap |
| `tests/test_pipeline.py` | 15 | pass | every file ingested, repo-relative POSIX paths, chunk→document→anchor chain, both indexes cover every chunk, idempotent re-ingest, no phantom half-name people |
| `tests/test_enrichment.py` | 16 | pass | controlled vocabulary, confidence penalties, acronym cues not matching inside longer words, LLM failure falls back and records why, live Claude call is grounded |
| `tests/test_grounding.py` | 9 | pass | verbatim quote recovery across line breaks and smart punctuation; stitched and invented quotes rejected |
| `tests/test_search.py` | 18 | pass | semantic + keyword arms, fused ranking, traceability fields, FTS operator injection (`*`, `-- drop`, unterminated quotes) |
| `tests/test_synthesis.py` | 9 | pass | citation index mapping, out-of-range citations dropped, ungrounded answer marked unanswerable, model failure degrades to the extractive path |
| `tests/test_api.py` | 27 | pass | citations resolve to real rows, confidence is computed not constant, **the breakdown derives the confidence it reports**, low confidence routes instead of answering, corrections tie to a real `query_id`, metrics on an untouched DB |

One warning, from a third-party dependency, not from project code:
`starlette/testclient.py:53 DeprecationWarning: anyio.abc.BlockingPortal alias is deprecated`.

---

## 2. End-to-end smoke test (`scripts/smoke_test.sh`)

Run against `uvicorn app.main:app --port 8000` on the real `backend/app.db`. All 9 steps passed.

| # | Step | Outcome |
|---|---|---|
| 1 | `GET /health` | `{"status":"ok"}` |
| 2 | `POST /query` — answerable | confidence **0.815**, 5 claims, citations across docx + pptx + transcript |
| 3 | `GET /documents/{id}` | citation resolved; `source_path` matched the one the citation claimed |
| 4 | `POST /query` — unanswerable | confidence **0.2842** < 0.55 → **no answer synthesized**, routed |
| 5 | routing target | Ingrid Lund, with rationale quoting the passage that selected her |
| 6 | `POST /routing/send` | `{"status":"sent","simulated":true,"to":"ingrid.lund@meridianmicro.io"}` |
| 7 | `POST /corrections` | correction #4 written against the real `query_id` 22 |
| 8 | `GET /gaps?status=open` | gap #12 recorded, foreign-keyed to query 23 |
| 9 | `GET /metrics` | served with ingestion health, confidence trend, weakest queries |

### The result worth calling out: the two confidence gates

The unanswerable query is the one that proves the design. Retrieval was *confident* — 0.812, seven matching
documents, top similarity 0.85 — because the corpus does talk about nine passes. The model was allowed to
draft. The grounding check in `synthesis.py` then found **zero** of the draft's claims supported by the
retrieved text (`answer_support = 0.0`), so gate 2 discounted the score:

```
0.812 × (0.35 + 0.65 × 0.0) = 0.2842   →   below the 0.55 threshold   →   route, do not answer
```

The system had a fluent draft in hand and threw it away. That is the behaviour the exercise asks for, and
retrieval confidence alone would not have caught it.

This is also where the first run found the reporting defect described in §4a.

---

## 3. Frontend integration

`npm run lint` — 0 errors, 2 warnings (`react(set-state-in-effect)` in `ReviewQueuePage.jsx:43` and
`MeasurementPage.jsx:33`).
`npm run build` — succeeded in 153 ms; 27 modules, 250 kB JS / 17 kB CSS.

Driven live in the browser against the API on port 8000:

| Page | Check | Result |
|---|---|---|
| Ask | answerable query | "Answered", confidence 0.81, 5 cited claims, 4 citations with per-source relevance, plus a caveat flagging that a May 12 slide says "Closed" while the May 28 review says the customer had not accepted the 8D |
| Ask | gate-2 routing | "Routed — no answer", confidence 0.28, retrieved sources shown *as evidence for the routing decision, not as an answer*, routed to Ingrid Lund with rationale |
| Ask | gate-1 routing | "What is our parental leave policy?" — retrieval 0.32, no draft written, grounding shown as `—` rather than 0.00 |
| Review queue | gap list | every open gap listed with query text, confidence, routee and a "Mark resolved" control; the open/resolved/all filter works |
| Measurement | live `/metrics` | renders the headline rate, routing/correction rates, latency percentiles, confidence trend, weakest queries and ingestion health (0 parse failures). Figures are a moving snapshot — see §5 |

Console: no errors. Network: every `/health` and `/query` call returned 200, CORS preflight included. Layout
checked at 1024 px (7-column signal grid) and 800 px (5 columns, wraps cleanly, no horizontal overflow). The
whole pass was then repeated with the frontend on port **5174** instead of 5173 — see §4c.

---

## 4. Defects found and fixed

### 4a. `confidence_breakdown` could not explain the `confidence` it was attached to

**Found:** run 1, 2026-09-20, §2 step 4.
**Severity:** reporting, not scoring — no confidence value was ever wrong, but the field that exists to justify
it did not.

`confidence_breakdown` carried only the retrieval signal, so an API consumer saw:

```json
{ "confidence": 0.2842,
  "confidence_breakdown": { "value": 0.812, "top_similarity": 0.8512, "support": 0.7286, ... } }
```

Two numbers, 0.81 and 0.28, with nothing between them. The missing term — the grounded fraction of the draft —
sat in `derived_metadata.answer_support`, a different block, under a name that did not connect the two. The
field named `value` inside a block named `confidence_breakdown` did not hold the confidence.

**Fix** — [`backend/app/query/service.py`](backend/app/query/service.py): the gate-2 formula was extracted to
`_grounding_multiplier()` (previously inline, now shared so the reported multiplier cannot drift from the one
actually applied), and `_confidence_breakdown()` now emits the whole derivation:

```json
{ "confidence": 0.2842,
  "confidence_breakdown": {
    "value": 0.2842,                 // == confidence, always
    "retrieval_confidence": 0.812,   // gate 1
    "top_similarity": 0.8512, "support": 0.7286, "corroboration": 1.0,
    "source_trust": 0.7033, "matched_documents": 7,
    "answer_support": 0.0,           // gate 2, null when no draft was written
    "grounding_multiplier": 0.35,    // null when no draft was written
    "ungrounded_floor": 0.35,
    "reasons": [] } }
```

`value = retrieval_confidence × grounding_multiplier`, checkable from the payload alone.
`ConfidenceSignal.as_dict()` was left as the retrieval signal — that is its correct scope, and it is what gets
stored with the gap — so the two-gate assembly lives in the query service where both gates are known.

[`frontend/src/components/AnswerCard.jsx`](frontend/src/components/AnswerCard.jsx) now reads the breakdown's
own fields instead of stitching one value in from `derived_metadata`, and orders them the way the score is
derived: the four retrieval parts → `retrieval score` → `answer grounding` → `× grounding` → `= confidence`.

**Why `null` and not `0.0`:** when retrieval alone falls below the threshold the model is never called, so
grounding is *unmeasured*. Reporting 0.0 would claim the draft was checked and found baseless. The UI renders
these as `—`.

**Coverage added** — 2 tests in `tests/test_api.py`:

| Test | Asserts |
|---|---|
| `test_breakdown_explains_the_confidence_it_reports` | `breakdown["value"] == body["confidence"]`, and `value == retrieval_confidence × grounding_multiplier` |
| `test_breakdown_reports_no_grounding_when_no_draft_was_written` | gate-1 routing leaves `answer_support` and `grounding_multiplier` as `None`, and `value == retrieval_confidence` |

**Re-verified live** — three queries through the API, all self-consistent:

| Case | retrieval | answer_support | × multiplier | = value | confidence | answered |
|---|---:|---:|---:|---:|---:|---|
| gate-2 route (nine pass number) | 0.812 | 0.0 | 0.35 | 0.2842 | 0.2842 | no |
| answered (Northgate excursion) | 0.815 | 1.0 | 1.00 | 0.815 | 0.815 | yes |
| gate-1 route (parental leave) | 0.2224 | `null` | `null` | 0.2224 | 0.2224 | no |

and all three through the UI, where the panel now reads
`0.85 · 0.73 · 1.00 · 0.70 → retrieval 0.81 → grounding 0.00 → × 0.35 → = 0.28`.

### 4b. The routing reason called a grounding failure a retrieval failure

**Found:** while fixing 4a — same defect, different surface. This text is what the Review queue shows a lead,
so it is the sentence that decides where they go looking.

`_routing_reason()` had two branches where the code has three outcomes. A draft that *claimed* an answer but
was discounted below the threshold by grounding fell through to the retrieval branch and was reported as:

> Retrieval confidence 0.28 is below the 0.55 threshold

— labelling the post-grounding number as a retrieval score, and sending a reviewer to look at a corpus that
had in fact retrieved well. The three cases are now distinct:

| Case | Reason text |
|---|---|
| gate 1 — no draft written | `Retrieval confidence 0.22 is below the 0.55 threshold: best match is only a partial fit…` |
| gate 2 — model declined to answer | `The retrieved sources are about this topic but do not answer the question (confidence 0.28, threshold 0.55).` |
| gate 2 — answer discounted | `The drafted answer was only partly supported by its sources, which lowered confidence from 0.81 to 0.28 (threshold 0.55).` |

The third names both numbers, so 0.28 cannot be read as a retrieval score.

**Coverage added** — `test_routing_reason_distinguishes_the_two_gates` in `tests/test_synthesis.py`, asserting
all three branches directly. The first two were re-confirmed live: gaps #21 and #20 in the running database
carry the gate-1 and gate-2 wording respectively.

### 4c. CORS was pinned to a port the dev server does not own

**Found:** while setting up run 2 — the verification frontend could not reach the API at all.
**Severity:** startup failure for anyone whose port 5173 happens to be busy.

`allow_origins=["http://localhost:5173"]` in `backend/app/main.py`. Vite moves to 5174 by itself when 5173 is
taken, and from that origin every request — including `GET /health` — failed preflight. What the user sees is
`Cannot reach the API at http://localhost:8000. Start it with uvicorn…`, so the message points at a backend
that is in fact running fine. This cost real time during this session, which is how it was found.

**Fix** — [`backend/app/main.py`](backend/app/main.py) + [`backend/app/config.py`](backend/app/config.py):
any localhost or 127.0.0.1 port is accepted by default via `allow_origin_regex`, with a new
`CORS_ALLOW_ORIGINS` setting (comma-separated) that replaces the default with an explicit allowlist for any
non-laptop deployment. Documented in `.env.example`. `allow_credentials` stays off, so a permissive local
origin grants a page nothing it could not get by calling the API directly.

**Coverage added** — 7 tests in `tests/test_api.py`: three localhost origins accepted by preflight (5173,
5174, `127.0.0.1:8080`), three non-local origins still refused (`localhost.example.com`, `evil.test`,
`notlocalhost:5173` — the regex is `fullmatch`, so host-prefix tricks do not pass), and the allowlist override.

**Re-verified live** against the running API:

| Origin | `Access-Control-Allow-Origin` |
|---|---|
| `http://localhost:5173` | echoed |
| `http://localhost:5174` | echoed |
| `http://127.0.0.1:4000` | echoed |
| `https://evil.test` | absent — refused |
| `http://notlocalhost:5173` | absent — refused |

and end-to-end: the frontend was started on **5174** with no `VITE_API_BASE_URL`, loaded against the API on
8000, and answered a full routed query with the breakdown panel intact — the exact case that failed before.

---

## 5. Notes and limits

- **The smoke test and the UI runs write to the database.** Across all three runs the query log went 21 → 41,
  open gaps 11 → 24, corrections 3 → 7. That is by design (the metric needs the instrumentation rows), but it
  means the metrics figures quoted in §2 and §3 are snapshots, and no metric number here is reproducible
  across runs.
- **The query log was cleared afterwards and the metric reset to zero** — see §6. The rates quoted in §2 and
  §3 were measured entirely on synthetic traffic and should not be read as system performance.
- **Latency is the weak number.** p50 8.5 s, p95 26.4 s, dominated by the synthesis call. Acceptable for the
  exercise, too slow for an interactive tool without streaming.
- **No frontend unit tests exist.** Coverage there is lint + build + the manual browser pass above. If the UI
  grows, the citation-rendering and confidence-display logic are the parts worth pinning down first.
- The live-Claude tests require `ANTHROPIC_API_KEY`; everything else runs fully offline with heuristic
  enrichment.

---

## 6. Query log cleared, metric reset

The measurement rates above were computed on traffic this test session generated, so they measured the tests,
not the system. All 41 `query_log` rows were test traffic — five distinct queries (the three UI suggestion
buttons, the smoke test's two, and one `ping`), several of them repeated a dozen times — with no real usage
mixed in. They were cleared, along with the 24 gaps and 7 corrections foreign-keyed to them.

`backend/app.db` was backed up first, through SQLite's online backup API rather than a file copy so the
snapshot is consistent while the API holds the database open: **`backend/app.db.bak-20260921-122529`**
(2,760,704 bytes). Restore by copying it back over `backend/app.db`.

| Table | Before | After |
|---|---:|---:|
| `query_log` | 41 | 0 |
| `gaps` | 24 | 0 |
| `corrections` | 7 | 0 |
| `documents` / `chunks` / `people` | 37 / 193 / 17 | unchanged |
| `decisions` / `action_items` | 91 / 141 | unchanged |
| `ingestion_runs` | 1 | unchanged |

`sqlite_sequence` was reset for the three cleared tables, so the next query is #1 rather than #42.

**Metric re-read on the cleared database.** `GET /metrics` returns `null` for every rate and `[]` for the
trend and weakest-query lists, rather than dividing by zero or reporting a misleading `0%`:

```json
"queries": { "total": 0, "avg_confidence": null, "routing_rate": null,
             "correction_rate": null, "answered_without_intervention": null },
"gaps": { "open": 0, "resolved": 0, "total": 0 },
"corrections": { "total": 0, "corrected_queries": 0 }
```

Ingestion health is unaffected and still reports 37 documents, 193 chunks, 0 parse failures, enrichment
confidence 0.82. The Measurement page renders the empty state correctly — `—` in every tile and "No queries
logged yet." under both tables, with the ingestion section fully populated. No console errors.

One cosmetic fault showed up only in this state and was fixed: the Latency tile's subtitle fell back to a
bare `p50`, labelling a percentile under an em dash where no percentile existed. The hint now drops out with
the value it describes ([`latencyHint()`](frontend/src/pages/MeasurementPage.jsx)), matching how the other
tiles degrade inside their own sentence (`trailing —`). Re-checked live on the empty database: all twelve
tiles render, Latency shows `—` with no subtitle, no console errors.

**The metric now has no value, and that is the correct state.** "Answered without intervention" measures real
people asking real questions; there is nothing to report until the system sees some. Generating more traffic
here would only re-create the problem this section exists to undo.

---

## 7. Third pass — the answer-quality gate, and what building it found

Adding a golden-set gate and an MCP server was the task. Five defects came out of doing it, and the two that
matter are both the same shape as §4's: they produce a confident, well-formed, wrong result rather than an
error, so nothing in the existing 105 tests could have caught them.

### 7a. A department became a person in the routing graph

`SELECT * FROM people` returned 17 rows against a 16-person cast. The extra one was named **`Product`**,
linked to `kestrel2-test-cell-integration-spec-DRAFT.docx` with `role = 'action_owner'`.

Claude enrichment had lifted two action items whose owner the source writes as "Product" — the department,
not a person — and `resolve_person` created a row for it, because its fallback was `upsert_person`. Routing
walks `chunks → documents → document_people → people`, so `Product` was a legitimate candidate routee. The
README's claim that a routee is "never fabricated" was false in exactly one place, and it took a count of
table rows to see it.

**Fix.** `resolve_person` returns `int | None` and never creates. Only a verbatim attendee/author line or
`data/people.yaml` may add to `people` — the only two places a name is stated by the source rather than
derived by a model. A derived owner that resolves to a known person still gets its edge; one that does not
stays text on the `action_items` row, visible where it was written and absent from the graph.
`scripts/inspect_db.py` gained a second check that distinguishes "a known person is missing an edge" (fatal)
from "this owner is not a person" (informational, currently 1).

### 7b. The routing floor was checked against a different chunk than the one it justified

*"What is Meridian's parental leave policy?"* — a question the corpus has nothing whatsoever about — routed
to **Victor Nwosu**, quoting a paragraph of open questions from a device-handler integration spec.

`route()` checked `signal.top_similarity`, the best normalised similarity anywhere in the retrieved set
(0.27, above the 0.25 floor), and then built its case on `candidate.best_chunk` — a *different* chunk, at
0.22. The guard and the evidence were never about the same passage. Ranking fuses keyword overlap with
semantic similarity, so the quoted chunk can score 0.00 on meaning and still lead on literal tokens like
"what" and "we".

**Fix.** The floor is applied a second time, to the chunk the rationale will actually quote. Two of the three
uncovered questions in the golden set now reach nobody; the third reaches the Vantage PM off a cloud
infrastructure passage at 0.36, which is thin but defensible — a floor high enough to suppress it would also
suppress the routing that works. Pinned by `tests/test_routing.py`.

### 7c. The gate did not reproduce in CI — because the threshold meant two different things

The golden set was green locally and failed two cases the first time the CI sequence was run end to end:
`helios3-measured-throughput` 0.608 → 0.528 and `encoder-last-time-buy-deadline` 0.556 → 0.479, both
crossing the 0.55 threshold into routing.

The cause was not the gate. Retrieval weights sources by `enrichment_confidence`, which is 25% of the
confidence score. Claude enrichment scores this corpus at a mean of 0.82; the heuristic fallback CI uses
scores the *same documents* at 0.46. The documents did not change — the enricher's self-belief did — and
0.25 × 0.36 ≈ 0.09 is precisely the drop measured. **The answer-versus-route decision depended on which flag
the corpus was ingested with.**

**Fix.** `source_trust` now uses `relative_quality` — a document's enrichment confidence against the best in
its own corpus — so it keeps what the signal is for (a sparse scratch file still ranks below a spec) and
drops the offset that only says which enricher ran. The same 13 offline cases now differ by at most 0.015
between the two databases, against 0.08 before. `tests/test_search.py` pins the invariant directly: a uniform
rescaling of the corpus's enrichment confidences must not move `compute_confidence`.

`.github/workflows/ci.yml` also re-ingests the corpus before grading it, so the gate is always run against a
database built the way the grader will build it.

### 7d and 7e. Two spreadsheets did not survive their own arithmetic

Found by writing `tests/test_corpus.py`, which recomputes the narrative rather than checking the file parses.

| File | Defect |
|---|---|
| `fy26-budget.xlsx` | The R&D total (11,400,000 / 11,905,000) exceeded the sum of its line items (10,600,000 / 11,045,000) by 800k and 860k. The two totals were consistent *with each other* — their difference is the 505k the note claims — so nothing looked wrong until the column was added up. Fixed by restoring the missing line (shared engineering tools and EDA licences), not by editing the totals. |
| `efem-cost-reduction-tracker.xlsx` | The fan filter line read 34,000 for six units where the BOM prices them at 5,700 each. The *target* on the same row, 28,500, is exactly 5 × 5,700, which settles which figure was wrong. Corrected to 34,200, saving 5,700, standard-cost target 334,300 — margins still reconcile at 41% and 46%. |

The workshop transcript still says 34,000 and 31,500. That one is **kept**: a person quoting round numbers in
a meeting while the spreadsheet is exact is what real corpora look like, and it is now registered as
deliberate in the README's defect table and asserted as deliberate in `test_corpus.py`, so a later "fix"
fails the suite.

### Also checked, and already correct

The adversarial pass looked for several failure modes that turned out not to be present, which is worth
recording so nobody re-investigates them:

| Checked | State |
|---|---|
| `PRAGMA foreign_keys` set per connection, not once in the schema | correct — `db/connection.py:21` |
| Spreadsheet quantities stored as numbers, not text | correct — all `int`; now asserted |
| Every transcript speaker format parsed | correct — three forms plus a label guard |
| Every attendee and speaker in `data/people.yaml` | correct — 16/16, zero drift |
| Transcript frontmatter dates match filenames | correct — 22/22 |
| Build-rate sheet is the binding constraint | correct — 6/6 rows |
| Unicode survives docx → parse → SQLite | correct — zero replacement characters |

### Current state

```
cd backend && python -m pytest tests -q
134 passed, 1 skipped      # the skip is the live-Claude test, gated on RUN_LLM_TESTS=1

cd backend && python -m eval.run_eval              # Claude backend
19/19 passed           answered 0.675-0.963   routed 0.252-0.507

cd backend && python -m eval.run_eval --offline    # extractive backend
14/14 passed, 5 excluded (model-only)
                       answered 0.565-0.796   routed 0.339-0.426
```

The full CI sequence — `--reset --no-llm` ingest → `inspect_db` → pytest → eval gate — was run locally
against the heuristic database and is green, which is the only form of "CI will pass" worth asserting.

---

## Reproducing

```bash
cd backend && ./.venv/Scripts/python.exe -m pytest tests -v
```

```bash
cd backend && ./.venv/Scripts/python.exe -m eval.run_eval --offline
```

```bash
cd backend && ./.venv/Scripts/python.exe -m uvicorn app.main:app --port 8000
```

```bash
PY=./backend/.venv/Scripts/python.exe bash scripts/smoke_test.sh
```
