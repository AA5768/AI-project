# Meridian Microsystems Knowledge System — FDE Take-Home

Unifies three take-home exercises (transcripts → +Office docs/traceability/routing → user-facing app)
into one system. See [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md) for the full spec.

**Primary AI tool used to build this project: Claude Code (CLI).**

## Stack

- **Storage**: SQLite (`sqlite-vec` for embeddings + FTS5 for keyword fallback)
- **Embeddings**: local `sentence-transformers` (`all-MiniLM-L6-v2`)
- **LLM**: Claude via the Anthropic API (Haiku for enrichment, Sonnet for query synthesis/routing)
- **API**: FastAPI, plus an MCP server over the same service layer
- **UI**: React + Vite
- **Gate**: golden answer-quality eval, run in GitHub Actions with no API key

## Repo layout

```
data/people.yaml         # the invented cast (name → title, department, email)
data/transcripts/        # 22 meeting transcripts (.md + YAML frontmatter)
data/office/             # 15 decks, docs, spreadsheets (.docx/.pptx/.xlsx)
backend/                 # ingestion, db schema, FastAPI app
backend/app/mcp_server.py  # the same service layer over MCP
backend/eval/            # golden set + the answer-quality gate
backend/scripts/         # corpus generator + db inspector
frontend/                # React app
docs/                    # API + function reference
scripts/smoke_test.sh    # end-to-end API smoke test
.github/workflows/ci.yml # ingest -> tests -> eval gate, no API key
```

## Documentation

- [docs/API_REFERENCE.md](docs/API_REFERENCE.md) — the HTTP contract: every
  endpoint, request/response shape, error and enum.
- [docs/FUNCTION_REFERENCE.md](docs/FUNCTION_REFERENCE.md) — module-by-module
  map of the code behind it, backend and frontend.
- [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md) — the spec.
- [TEST_REPORT.md](TEST_REPORT.md) — test coverage and results.

## The corpus

Invented org: **Meridian Microsystems**, a ~120-person semiconductor equipment
automation company. Three product lines run through every document — **Helios-3**
(300 mm wafer-handling robot and EFEM), **Kestrel-2** (tri-temperature device test
handler for back-end ATE), and **Vantage** (equipment connectivity and OEE SaaS:
SECS/GEM, EDA/Interface A, SEMI E10) — plus a customer particle excursion, a
supplier allocation squeeze, a hiring push, and a COGS-down initiative.
No real people, customers, or suppliers: everything is invented.

Transcripts are hand-authored markdown. The Office files are binaries, so they are
generated from reviewable source text in
[`backend/scripts/generate_office_corpus.py`](backend/scripts/generate_office_corpus.py):

```bash
cd backend && python -m scripts.generate_office_corpus
```

**Quality is varied on purpose** — this is what Part 2's gap, correction, and
routing logic has to exercise:

| Document | Defect | Contradicts |
|---|---|---|
| `helios3-program-status-2026-05.pptx` | stale | 450 wph (measured 412 on 2026-06-04), ship 30 Sep (moved to 14 Nov on 2026-08-13), and a Vantage acceptance criterion the kickoff explicitly excluded |
| `vantage-roadmap-fy26.pptx` | stale | on-premises shown at 4.0 GA; the 2026-02-05 scoping meeting moved it to 4.1 |
| `fy26-budget.xlsx` | stale | Helios-3 NRE at 3.6M; cut to 3.2M on 2026-05-21, then set to 3.4M on 2026-07-23 |
| `kestrel2-test-cell-integration-spec-DRAFT.docx` | draft | TBDs, a datasheet figure the author says is unsupportable |
| `helios3-open-items.docx` | sparse, unattributed | no author, four bullet fragments |
| `2026-05-07-eng-standup-partial-notes.md` | sparse, unattributed | no attendees, hearsay about an encoder EOL letter that is confirmed a month later |
| `2026-07-23-efem-cogs-down-workshop.md` | rounded in the room | Owen quotes the fan filter set at 34,000 and the four actions at 31,500; the tracker says 34,200 and 31,700. People round when they speak. Kept on purpose — the spreadsheet is the system of record and reconciles exactly |

The spreadsheets are held to arithmetic, not just to plausibility:
`backend/tests/test_corpus.py` recomputes them against the narrative they are
supposed to support — the four approved COGS-down actions must equal the
standard-cost delta, the gross margins must fall out of list price minus
standard cost, the fan filter line must equal the BOM unit cost times six, the
build-rate column must be the binding constraint, and every total must equal
its line items. Two of those did not hold when the tests were first written.
The same file asserts the deliberate defects above are still defective, so a
well-meaning edit that "fixes" the stale budget deck fails the suite instead of
quietly deleting the test case Part 2 exists for.

The same facts are reachable from more than one source with different reliability
(e.g. the Northgate root cause appears in a transcript, in bridge minutes, in an 8D
report, and in a status deck), which is what makes citation ranking and
correction capture testable rather than decorative.

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp ../.env.example ../.env    # fill in ANTHROPIC_API_KEY
python -m app.ingestion.pipeline --reset   # ingest data/ into the database
python -m scripts.inspect_db               # verify traceability chains
uvicorn app.main:app --reload --port 8000
```

`--reset` drops the database first. The pipeline creates the schema itself, so a
separate init step is not needed.

### Ingestion options

| Flag | Effect |
|---|---|
| *(none)* | Claude enrichment when `ANTHROPIC_API_KEY` is set, heuristics otherwise |
| `--llm` | Force Claude enrichment; fails loudly if no key is configured |
| `--no-llm` | Force the deterministic heuristic fallback (offline, no API cost) |
| `--reset` | Delete the database file before ingesting |
| `--limit N` | Ingest only the first N files (useful while iterating) |
| `--allow-downgrade` | Permit `--no-llm` to overwrite Claude-enriched documents |

Re-running without `--reset` is idempotent: a document is replaced in place, and
previous `ingestion_runs` rows are kept so confidence can be trended over time.

Replaced in place is also why `--no-llm` over a Claude-enriched database is
refused. It would rewrite every summary, decision and action item at roughly
half the confidence and exit 0, which is indistinguishable from a successful
re-index; the only trace is a column nobody re-reads after a clean run. Use
`--reset` to rebuild, or `--allow-downgrade` when it is what you meant.

### Tests

```bash
cd backend
python -m pytest tests -q
```

### The answer-quality gate

134 unit and API tests pin the mechanics — that a citation resolves, that a
threshold is applied, that a correction is stored. None of them can fail when
the system starts answering questions it should route, which is the failure
users actually experience, so there is a second gate:

```bash
cd backend
python -m eval.run_eval              # whichever backend is configured
python -m eval.run_eval --offline    # extractive backend, what CI runs
```

[`eval/golden.yaml`](backend/eval/golden.yaml) holds 19 questions with the
outcome the corpus justifies — answered or routed, which sources the citations
must include, which person a routed query must reach — each with a `why` that
argues it from the source files rather than from what the system currently
returns. `eval/run_eval.py` runs them, prints the confidence bands either side
of the routing threshold, and exits non-zero on any regression.

Five cases are marked `requires: llm` and skipped offline. That is not a
loophole; it is the measurement. They are mostly questions whose sources
discuss the subject at length without answering it, and the extractive fallback
returns the best passage and calls it an answer, so it cannot get them right.
Loosening the assertion would hide the one thing this comparison is for.

### CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs with no
`ANTHROPIC_API_KEY` on purpose: enrichment falls back to heuristics and
synthesis to the extractive path, so the whole pipeline is exercised for free
and without a secret.

It re-ingests the corpus before grading it, and that step is load-bearing
rather than tidy. Retrieval weights sources by their enrichment confidence, and
Claude enrichment scores this corpus at a mean of 0.82 where the heuristic
fallback scores the same documents at 0.46 — the documents are identical, the
enricher's self-belief is not. A gate tuned against a locally Claude-enriched
database therefore disagreed with CI by about 0.08 on every query, which was
enough to push two answerable questions across the routing threshold. The fix
was not to re-tune the gate: `source_trust` now measures a document against the
best in its own corpus rather than against an absolute scale, so the same
question gets the same verdict either way, and CI builds the database it is
about to grade so the two can be compared at all.

### Where it ends up

Both backends over the same corpus, same golden set:

Both backends over the same corpus and the same 19 cases. The extractive
column is measured over all 19, including the five the gate skips offline, so
the comparison is a comparison rather than a scoreboard:

| | Claude | Extractive |
|---|---|---|
| golden set as gated | **19/19** | 14/14 (5 excluded by name) |
| answer-vs-route decision, all 19 | **19/19** | 17/19 |
| routed to the person the record names | 2/2 | 1/2 |
| no routee invented for an uncovered question | 2/2 | 2/2 |

The two decisions the extractive backend gets wrong are the two pure
answerability cases: *what is on the roadmap for Helios-4* (there is no
Helios-4) and *what is the nine pass adder number* (every particle chunk in the
corpus matches; no document states the figure). Both retrieve strongly and
neither is answerable, which is precisely the judgement a rule engine cannot
make and the second gate exists to delegate. Its third loss is quieter: it
answers *when is first customer ship* correctly-shaped and wrongly-sourced,
citing the stale May status deck rather than the August ops review that moved
the date.

The no-routee rule and the routing walk itself are identical between backends —
no model touches them — so the difference isolates what the model actually
contributes.

Confidence separates cleanly across the routing threshold on both, with
nothing straddling it:

```
Claude       answered 0.675 - 0.963      Extractive   answered 0.565 - 0.796
             routed   0.252 - 0.507                   routed   0.339 - 0.426
                            ^ route below 0.55
```

The gap between the two answered bands is the extractive path's deliberate
support discount, not a disagreement about the corpus. The narrowest margin in
either column is the EU availability question at 0.565 offline, 0.015 above
the threshold; the golden file names it as the one that will move first.

### Notes on this environment

- **Corporate TLS interception**: `app/config.py` calls `truststore.inject_into_ssl()`
  at import so the OS certificate store is used. Without it the
  `sentence-transformers` model download fails with `CERTIFICATE_VERIFY_FAILED`
  behind an intercepting proxy. The model is cached after the first run, so
  subsequent runs work offline (`HF_HUB_OFFLINE=1`).
- **No API key required to get a working database.** Enrichment falls back to
  deterministic heuristics and scores itself low, which is visible in
  `documents.enrichment_method` and `enrichment_confidence`.

### Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173, against the API on :8000
```

Three screens, no state library — each one owns a single request:

| Screen | What it does |
|---|---|
| **Ask** | Renders the answer claim by claim, each sentence carrying the citation markers for *that* sentence. Markers and citation rows open a drawer on `GET /documents/{id}` scrolled to the cited chunk, with the document's people, decisions and action items. Metadata badges (topic, priority, source types, quality flags) come off the response, and a collapsible panel shows how the confidence was computed. An answered query offers a correction; a low-confidence one renders the routing card instead |
| **Routing card** | Who, why — the rationale plus the passage it was computed from, click-through to its source — and the draft question in an editable textarea before a simulated send. When the corpus connects no one to the question, it says so rather than naming someone |
| **Review queue** | Gaps and corrections filtered by status, each joined to the query that caused it, with resolve/reopen |
| **Measurement** | The first-30-days metric below, with its live value from `GET /metrics` |

### Smoke test

With the API running:

```bash
bash scripts/smoke_test.sh
```

## The API

All of it is in the OpenAPI docs at `http://localhost:8000/docs` once the server
is running.

| Method | Path | What it does |
|---|---|---|
| `POST` | `/query` | Retrieve, score, then answer with citations **or** route to a person |
| `GET` | `/documents/{id}` | The full source behind a citation: raw text, every chunk with its anchor, people, decisions, action items |
| `POST` | `/corrections` | Store a human correction against a `query_log` row (the original answer is copied in) |
| `GET` | `/corrections` | Filter by `query_id`, `corrected_by`, `since` |
| `GET` | `/gaps` | Filter by `status` (`open`/`resolved`) and `since`; joined to the query that caused each gap |
| `PATCH` | `/gaps/{id}` | Triage: mark resolved (or reopen) |
| `POST` | `/routing/send` | Simulated hand-off. Delivery is stubbed, addressing is not — an unknown recipient is a 404 |
| `GET` | `/metrics` | Query confidence trend, routing/correction rates, latency, ingestion health |

The response shape never depends on where the winning chunk came from: a
transcript line and a spreadsheet cell range compete on the same score and come
back as the same citation object.

## The MCP server

The same service layer, a different transport — so an assistant can use this
corpus without a second implementation of the rules.

```bash
cd backend && python -m app.mcp_server          # stdio
claude mcp add meridian-kb -- python -m app.mcp_server
```

| Tool | What it does |
|---|---|
| `ask` | Query the corpus. Rendered prose with inline citation markers, then the same structured payload `POST /query` returns |
| `read_document` | The full source behind a citation, same withholding rule for unverified evidence |
| `open_gaps` | The review queue: what the corpus could not answer |
| `health` | The `/metrics` snapshot |

Every tool calls `app/query/service.py` and `app/db/repository.py` directly:
the same two confidence gates, the same routing walk, the same `query_log` and
`gaps` rows — MCP traffic shows up in `/metrics` like any other caller.
[`tests/test_mcp.py`](backend/tests/test_mcp.py) asserts that, running the same
question through both surfaces and comparing the decision, the confidence and
the citation ids, because a second surface that drifts from the first is worse
than no second surface.

It is read-only. Corrections and gap triage stay on the HTTP API behind the
review queue: both are human judgements about a specific answer, and an
assistant resolving its own gaps is a loop with nobody in it.

### How confidence is computed

Confidence gates routing, so it is computed from the retrieval result rather
than asserted. Two gates, and a query has to clear both:

**Gate 1 — is there evidence?** ([`retrieval/search.py`](backend/app/retrieval/search.py))
Cosine similarity from `sqlite-vec` is fused with a bm25 rank from FTS5, then
scored on four signals: how well the best chunk matches, whether the next-best
chunks agree, how many *distinct documents* corroborate, and how confidently
Part 1 enriched those documents. Raw MiniLM cosine is useless as a 0..1 score —
measured over this corpus, an off-topic question still peaks at 0.24-0.28 while
an answerable one reaches 0.61-0.66 — so the band that actually discriminates is
calibrated onto the full range first. Below the threshold the query is routed
without a model call: there is no weak answer for anyone to be tempted by.

**Gate 2 — does it answer the question?** ([`query/synthesis.py`](backend/app/query/synthesis.py))
Gate 1 cannot tell an answer from a topic. *"What is the nine pass number for
Helios-3?"* pulls in every Helios-3 particle chunk in the corpus and scores 0.81.
So Claude is asked for a list of claims, each carrying the source numbers it came
from, and every citation is checked back against the retrieved set. The grounded
fraction discounts the retrieval score (`confidence = retrieval × (0.35 + 0.65 ×
grounded)`), and an answer the sources don't support drops that query to 0.28 and
routes it.

### How routing picks a person

Never by asking a model "who would know this?". The routee is found by walking
the same FK chain the citations use — `chunks → documents → document_people →
people` — weighting the recorded relationship (author > action owner > attendee)
and adding a bonus when the person's name appears *in the matched passage
itself*. That is why the nine-pass question routes to Ingrid Lund, Contamination
Control Engineer: the passage that matched is her explaining adders per pass.
The rationale quotes the line that chose her, and the draft question is written
from that same passage for a human to edit before sending.

When nothing in the corpus is actually about the question, no one is suggested.
A gap is still recorded, with `routing_unavailable` explaining why — naming
whoever happens to sit nearest an unrelated paragraph would be the same
fabrication as inventing an answer.

That check has to be applied to the passage the rationale quotes, not to the
best match in the corpus, and they are not the same chunk: `route()` cleared
the floor on the corpus-wide best similarity and then built its case on
whichever chunk the chosen person scored highest on. *What is Meridian's
parental leave policy?* passed at 0.27 and was justified by a 0.22 paragraph
about test-cell integration, naming its author — the exact fabrication the
floor was written to stop, arriving through the gap between the chunk that
passed it and the chunk that was used. Ranking fuses keyword overlap with
semantics, so the quoted chunk can have a semantic similarity of zero: literal
tokens like *what* and *we* are enough when nothing matches on meaning.

Two of the three uncovered questions in the golden set now reach nobody. The
third, *what do we spend on AWS every month*, reaches the Vantage product
manager off a cloud infrastructure scoping passage at 0.36 — thin, but the
corpus genuinely has no closer owner for a question about hosting cost, and a
floor high enough to suppress it would also suppress the routing that works.

Every non-person is kept out of the graph at the other end too. Enrichment
yields action-item owners as the source wrote them, which is sometimes a
department: `Product` arrived as an owner from the Kestrel-2 draft spec and
became a row in `people`, reachable by the same FK walk the rationale uses.
Only a verbatim attendee or author line — or `data/people.yaml` — may create a
person now. A derived owner is linked when it resolves to someone already
known and otherwise stays text on the action item: visible where it was
written, absent from the routing graph.

## Measurement approach (first 30 days)

The number to watch is **the share of queries answered without intervention** —
neither routed to a human nor subsequently corrected — because it is the only
one that moves for both failure modes that matter: the system not knowing, and
the system being wrong. It needs no new instrumentation. Every query already
writes a `query_log` row with its computed confidence, latency and a `routed`
flag; every escalation writes a `gaps` row and every human fix a `corrections`
row, both foreign-keyed back to that query. `GET /metrics` serves the metric
directly (`queries.answered_without_intervention`, counted per query so a routed
query that was also corrected isn't double-counted), alongside the same figure
over the trailing 50 queries and a per-day confidence and routing trend, so a
weekly read is a single request. The trailing window is the early-warning
signal: a routing rate of 5% all-time and 40% over the last 50 queries means the
corpus has gone stale against what people are now asking, and `/metrics` also
reports ingestion health — parse failures, enrichment method mix, the documents
enriched below 0.5 confidence — so the cause is visible in the same response.
Target for the first 30 days: get the answered-without-intervention rate above
70% while the corrections queue stays small enough for one lead to triage
weekly; if it climbs by *suppressing* routing instead, the gaps count would drop
while corrections rise, which is why both are read together rather than either
alone.

## Data model

```
documents ──┬── chunks ──┬── chunk_vectors   (sqlite-vec KNN index)
            │            └── chunks_fts      (FTS5 keyword index)
            ├── decisions
            ├── action_items
            └── document_people ── people

query_log ──┬── corrections
            └── gaps ── people

ingestion_runs ──┬── ingestion_errors
                 └── enrichment_log
```

Every chunk carries a `source_anchor` that names a real location in the file
(`lines 12-18`, `slide 3`, `Budget (header row 1) cells A2:D13`) and resolves
through `documents` to the verbatim author/attendee list. That chain is what
makes Part 2's citations and routing checkable rather than generated.

## Status

| Part | State |
|---|---|
| **Part 1 — data layer** | **Done.** Exit criteria met against the real corpus on both paths: Claude Haiku enrichment gives 37 documents → 193 chunks, 0 parse failures, avg confidence 0.82; the offline heuristic fallback ingests the same corpus at avg confidence 0.46. Both report traceability chains intact via `python -m scripts.inspect_db`. All 227 stored evidence quotes are byte-exact spans of their source file, and the 16 rows in `people` are exactly the cast in `data/people.yaml` — nothing model-derived creates a person. |
| **Data corpus** | Authored: 22 transcripts + 15 Office files, 16 recurring people across 6 departments, cross-referenced across sources. Six documents are deliberately degraded (sparse / draft / unattributed) to give Part 2's gap and routing logic something real to fire on. |
| **Part 2 — API** | **Done.** 134 tests pass (`python -m pytest tests -q`), offline — the model is stubbed, so grounding and the routing rules are pinned without an API key. Exit criteria met: `bash scripts/smoke_test.sh` runs query → citation → `/documents/{id}` → low-confidence routing → simulated send → correction → gap retrieval → metrics against the running API, and asserts each step rather than just printing it. |
| **Answer-quality gate** | 19 golden questions, 19/19 with Claude and 14/14 on the keyless extractive path (5 model-only cases excluded by name). Confidence bands separate cleanly across the routing threshold on both. Wired to GitHub Actions, which re-ingests the corpus heuristically before grading it so the gate reproduces. |
| **MCP server** | Four read-only tools over the same service layer as the HTTP API, with a test asserting both surfaces return the same decision, confidence and citations for the same question. |
| **Part 3 — UI** | **Done.** Exit criteria met: `npm run dev` serves ask → citation → source drawer → routing → simulated send → correction → review queue against the local API, verified end to end in the browser on all three query outcomes (answered, routed to a person, routed with no owner). The measurement paragraph is in this README and on the Measurement screen beside its live value. |
