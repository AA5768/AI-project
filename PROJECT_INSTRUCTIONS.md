# Project Instructions — FDE Take-Home

Unifies the three take-home exercises (transcripts → +Office docs/traceability/routing → user-facing app)
into one system, built in three layers. Each part below maps to specific exercise requirements so nothing
gets dropped, but the build order follows the architecture (data → API → UI), not the exercise numbering.

## Confirmed tech stack

- **Storage**: SQLite as the single source of truth, using the `sqlite-vec` extension for embedding
  vectors and FTS5 for keyword fallback (hybrid retrieval), all in one `.db` file.
- **Embeddings**: local `sentence-transformers` model (e.g. `all-MiniLM-L6-v2`) — offline, no API-key
  dependency.
- **LLM**: Claude via the Anthropic API — Haiku for batch metadata enrichment, Sonnet for query-time
  answer synthesis and routing rationale.
- **Orchestration**: hand-rolled retrieval (top-k chunk lookup → prompt template → Claude call) inside
  FastAPI — no LangChain/LlamaIndex — so confidence scoring and per-claim citation mapping (needed for
  Exercise 2) stay fully under our control.
- **API**: FastAPI. **UI**: React + Vite.

## Constraints carried through every part

- New/empty workspace, single public GitHub repo, data committed into the repo.
- Primary AI tool: Claude Code (CLI). Note this in the README.
- No real customer data, real names, or employer-proprietary content — invented org only.
- 24h budget — favor a working end-to-end slice over a polished partial system at every checkpoint.

## Invented organization context

**Meridian Microsystems** — ~120-person semiconductor equipment automation company. Three product lines:
**Helios-3**, a 300 mm atmospheric wafer-handling robot and EFEM; **Kestrel-2**, a tri-temperature device
test handler that docks to back-end ATE; and **Vantage**, an equipment-connectivity and OEE SaaS
(SECS/GEM, EDA/Interface A, SEMI E10). Departments: Engineering, Product, Sales/CS, Operations,
Finance, People. Use this org for both the transcripts and the Office documents so the two corpora
cross-reference the same people, projects, and decisions (e.g., a decision made in a meeting later shows up half-implemented in a slide deck, or a
spreadsheet contradicts something a transcript says — this is what makes traceability and correction-capture
meaningful in Part 1/2).

Invent ~10-15 recurring people across departments with realistic-but-fake names, titles, and email handles,
and 4-6 running projects/topics (e.g., the wafer-handler program, a connectivity software release, a
customer particle excursion, a second-source/allocation squeeze, a hiring push, a COGS-down initiative). Reuse these consistently across all
documents so cross-document search/traceability has real signal.

---

## Part 1 — Database & data interaction layer

Covers Exercise 1 (§1-3) and the storage/traceability/correction/gap-capture requirements of Exercise 2.

1. **Generate the corpus**
   - `data/transcripts/*.md` — 15-20 meeting transcripts. Each has YAML frontmatter (date, attendees,
     meeting title) + free-form dialogue with decisions and action items embedded naturally (not
     pre-labeled — enrichment has to derive them).
   - `data/office/*.docx / .pptx / .xlsx` — 10-15 files: status decks, design docs, budget/roadmap
     spreadsheets, meeting-minutes docx, etc., authored by the same invented people.
   - Vary quality and priority deliberately: some documents are stale, contradictory, sparse, or
     low-confidence sources — this is what Exercise 2's gap/correction/routing logic needs to exercise.

2. **Ingestion**
   - One ingestion pipeline that both file families flow through, converging on a common internal
     representation (`Document { id, source_path, source_type, raw_text, sections[] }`) before enrichment,
     so business rules apply consistently across sources.
   - Parsers: markdown+frontmatter for transcripts; `python-docx`, `python-pptx`, `openpyxl` (or
     equivalent) for Office formats. Preserve enough structural anchor (paragraph/slide/cell reference) per
     chunk to support citation later.

3. **Enrichment (LLM-derived structured metadata)**
   - Per document: topic domain, priority (where applicable), summary, decisions[], action_items[], and
     attendees/author preserved verbatim from the source (not re-derived/guessed).
   - Persist the enrichment as structured rows, not just an LLM response blob — this is what the query API
     and UI metadata badges read from.

4. **Storage schema** (SQLite is sufficient; add a vector column/table or FTS5 for semantic-ish search)
   - `documents` — id, source_path, source_type, author/attendees (JSON), date, topic_domain, priority,
     summary.
   - `chunks` — id, document_id, text, source_anchor (line/slide/cell), embedding.
   - `query_log` — id, query_text, answer, confidence, timestamp, matched_chunk_ids (JSON).
   - `corrections` — id, query_id (FK), original_answer, corrected_answer, corrected_by, timestamp.
   - `gaps` — id, query_id (FK), reason, suggested_routing_person, routing_rationale, draft_question,
     status (open/resolved).
   - Every row in `chunks`/`documents` must carry enough to answer "which file, which
     author/attendee" — that FK chain is what makes Part 2's citations and routing non-fabricated.

5. **Instrumentation hooks** (feeds Exercise 2's "catch quality degradation" requirement)
   - Log per-ingestion: doc count, parse failures, enrichment confidence distribution.
   - Log per-query: confidence score, whether it fell back to routing, latency.
   - Keep this as queryable rows (not just log lines) so Part 2 can expose a `/metrics` endpoint.

**Exit criteria for Part 1:** a script that ingests `data/` end-to-end and leaves a populated SQLite DB you
can inspect directly (`sqlite3` shell or a notebook) with correct traceability chains — no API needed yet.

---

## Part 2 — RESTful API layer

Covers Exercise 1 §4, and all of Exercise 2's traceability/routing/correction/instrumentation surface.

Framework suggestion: FastAPI (async, auto OpenAPI docs, easy to curl/test).

1. **Core query endpoint**
   - `POST /query {text}` → retrieves relevant chunks across both sources, synthesizes an answer, returns:
     `{answer, confidence, citations: [{source_path, author_or_attendees, anchor}], derived_metadata}`.
   - Confidence must be a real computed signal (retrieval score threshold, agreement across chunks, etc.),
     not hardcoded — it's what gates routing.

2. **Traceability**
   - Every citation object must resolve to an actual row in `documents`/`chunks`. Add a
     `GET /documents/{id}` to fetch full source context for a citation (for the UI to show provenance).

3. **Routing (low-confidence path)**
   - When confidence is below threshold, `POST /query` response includes
     `routing: {person, rationale, matched_content, draft_question}` instead of (or alongside) a weak
     answer. `rationale` must cite the actual matched content that led to picking that person.

4. **Correction capture**
   - `POST /corrections {query_id, corrected_answer, corrected_by}` — stores the correction tied to the
     original query/answer.
   - `GET /corrections` and `GET /gaps` — retrievable, filterable (e.g., by status/date) so gaps/corrections
     aren't a write-only sink.

5. **Instrumentation endpoint**
   - `GET /metrics` — recent query confidence trend, routing rate, correction rate, ingestion health. This
     is the thing that would let you notice degradation before users complain.

6. **Consistency**
   - Same business rules (confidence thresholding, routing logic, citation shape) apply regardless of
     whether the winning chunk came from a transcript or an Office doc — don't special-case by source type
     in the response shape.

**Exit criteria for Part 2:** a `curl`/`httpie` script (commit it, e.g. `scripts/smoke_test.sh`) exercising
query → citation → low-confidence routing → correction → gap retrieval → metrics, all through the running
API, against the Part 1 database.

---

## Part 3 — User interface layer

Covers Exercise 3.

Stack suggestion: React + Vite, plain fetch to the Part 2 API (no need for a framework-heavy state layer at
this scale).

1. **Ask screen**
   - Text input → answer rendered with inline/adjacent citations (source file + author, clickable to show
     the source excerpt) and the derived metadata badges (topic domain, priority) from the response.

2. **Routing screen (low-confidence path)**
   - When the API response includes `routing`, render a card: who, why (the matched content), and an
     editable draft question textarea, with a "send" action. Send can be simulated (e.g., POST to a stub
     `/routing/send` that just logs it) — the point is the review/edit/send affordance, not real email
     delivery.

3. **Review queue**
   - A simple list view (filter by open/resolved) pulling from `GET /gaps` and `GET /corrections`, framed as
     something a team lead would triage periodically — query text, what went wrong, current status, and an
     action to mark resolved.

4. **Measurement approach (deliverable, one paragraph, ship it in the README or on-screen)**
   - Pick one first-30-days metric (e.g., % of queries answered without routing/correction — a direct proxy
     for trustworthy coverage) and state how you'd instrument it (already covered by `query_log` +
     `corrections`/`gaps` counts from Part 1/2 — just aggregate weekly).

**Exit criteria for Part 3:** `npm run dev` serves a working app against the local API covering ask →
citation → routing → review queue, plus the measurement-approach paragraph committed somewhere visible.

---

## Suggested repo layout

```
/data/transcripts/*.md
/data/office/*.docx,*.pptx,*.xlsx
/backend/          # ingestion, db, api (Parts 1-2)
/frontend/          # React app (Part 3)
/scripts/smoke_test.sh
README.md           # setup, primary AI tool disclosure, measurement paragraph
PROJECT_INSTRUCTIONS.md
```

## Suggested time-boxing (24h budget)

- Part 1 (data + ingestion + schema): ~6-7h
- Part 2 (API + routing/correction/instrumentation): ~7-8h
- Part 3 (UI): ~6-7h
- Buffer for README, smoke tests, repo cleanup: ~2-3h
