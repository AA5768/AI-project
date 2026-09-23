# Function Reference

Module-by-module map of the code behind [API_REFERENCE.md](API_REFERENCE.md).
Private helpers (`_name`) are listed only where they carry a design decision a
reader needs.

## Contents

- [Data flow](#data-flow)
- [Configuration — `app/config.py`](#configuration--appconfigpy)
- [Ingestion](#ingestion)
- [Enrichment](#enrichment)
- [Retrieval](#retrieval)
- [Query pipeline](#query-pipeline)
- [Persistence — `app/db/`](#persistence--appdb)
- [API layer — `app/api/`](#api-layer--appapi)
- [MCP server — `app/mcp_server.py`](#mcp-server--appmcp_serverpy)
- [Answer-quality gate — `eval/`](#answer-quality-gate--eval)
- [Frontend](#frontend)
- [Scripts and tests](#scripts-and-tests)

---

## Data flow

**Ingest (batch):**

```
data/*.md|docx|pptx|xlsx
  → parse_*          → Document(sections=[Section, ...])   # format-specific
  → chunk_sections   → [Chunk]                             # format-blind from here on
  → enrich_document  → EnrichmentResult
  → embed            → [vector]
  → persist_document → SQLite
```

**Query (per request):**

```
POST /query
  → search            → [RetrievedChunk]      (vec0 KNN ∪ FTS5, fused)
  → compute_confidence→ ConfidenceSignal       gate 1
  → synthesize        → AnswerDraft            gate 2 (grounded fraction)
  → answer  … or …  route → RoutingDecision
  → log_query (+ record_gap) → QueryOutcome
```

---

## Configuration — `app/config.py`

| Symbol | Signature | Notes |
| --- | --- | --- |
| `Settings` | `pydantic_settings.BaseSettings` | Loaded from `.env` at project root; unknown keys ignored. |
| `Settings.has_api_key` | `→ bool` | Property. Drives every LLM-vs-fallback branch in the codebase. |
| `Settings.cors_origins` | `→ list[str]` | Property. Splits `cors_allow_origins` on commas; empty list means "any localhost port". |
| `settings` | module-level singleton | Imported everywhere. |

Key fields: `anthropic_api_key`, `db_path`, `data_dir`, `embedding_model`
(`all-MiniLM-L6-v2`), `embedding_dim` (384), `chunk_target_chars` (900),
`chunk_max_chars` (1600), `enrichment_model` (Haiku), `synthesis_model`
(Sonnet), `confidence_threshold` (0.55), `cors_allow_origins`.

On import the module calls `truststore.inject_into_ssl()` inside a
`try/except`, so HuggingFace downloads work behind a TLS-intercepting corporate
proxy and are unaffected elsewhere.

---

## Ingestion

### `app/ingestion/common.py` — the shared representation

Everything downstream of a parser sees only these three dataclasses, which is
what lets one set of rules apply to transcripts and spreadsheets alike.

| Symbol | Fields / signature | Notes |
| --- | --- | --- |
| `Section` | `text`, `kind`, `locator_start`, `locator_end`, `scope`, `speaker` | `kind` ∈ `line \| paragraph \| slide \| notes \| table \| cells`. |
| `Section.anchor` | `→ str` | Property. Renders the citable locator: `"lines 12-18"`, `"slide 3"`, `"Budget cells A4:D9"` (colon for cell ranges, dash otherwise; `scope` prefixed when set). |
| `Section.mergeable_with` | `(other) → bool` | Same `kind` and `scope` — the chunker's "structural context unchanged" test. |
| `Document` | `source_path`, `source_type`, `raw_text`, `sections`, `title`, `attendees_or_author`, `date` | `attendees_or_author` is verbatim from the file and is never re-derived by a model. |
| `Chunk` | `index`, `text`, `source_anchor` | |
| `Chunk.char_count` | `→ int` | Property. |

### `app/ingestion/parsers/` — format-specific, all with the same signature

Every parser is `parse_x(path: Path, source_path: str | None = None) → Document`.

| Function | Produces | Design note |
| --- | --- | --- |
| `parse_transcript` (`.md`) | One `Section` per **speaker turn**, `kind="line"`, `speaker` set | A turn is the smallest unit that still makes sense quoted back. Attendees and date come verbatim from YAML frontmatter. Handles `Name:`, `**Name:**` and `**Name**:`. |
| `parse_docx` | `kind="paragraph"` sections scoped to the nearest heading; tables emitted separately as `kind="table"` | A budget table inside a design doc needs its own anchor — it is exactly the content that later contradicts a spreadsheet. Author/date lifted from `Author:` / `Date:`-style lines. |
| `parse_pptx` | One `kind="slide"` section per slide body, plus a separate `kind="notes"` section | Speaker notes are where the caveat lives ("numbers are pre-audit"); separating them keeps the caveat citable on its own. |
| `parse_xlsx` | Rows banded into groups of `ROWS_PER_BAND` (12) with the header row repeated on each band, `kind="cells"` | A lone row is unretrievable noise; the same row under its header is answerable. The anchor is a real cell range a reader can select in Excel. |

### `app/ingestion/chunking.py`

| Function | Signature | Notes |
| --- | --- | --- |
| `chunk_sections` | `(sections, target_chars=None, max_chars=None) → list[Chunk]` | Groups adjacent sections up to `target_chars`, flushing early whenever `mergeable_with` fails (new slide/sheet/heading). Defaults come from `settings`. |
| `_split_oversized` | `(section, max_chars) → list[Section]` | Breaks one over-long section on paragraph → sentence → hard-character boundaries. Locators stay put: every shard cites the same place. |
| `_merge_anchor` | `(group) → str` | One span when the group is homogeneous; otherwise the distinct anchors joined by `; `. |
| `_render` | `(group) → str` | Prefixes transcript lines with `Speaker: `. |

Deliberately **not** fixed-width token slicing — splitting mid-turn produces
citations that are technically correct and practically useless.

### `app/ingestion/pipeline.py` — entrypoint

```bash
python -m app.ingestion.pipeline --reset
python -m app.ingestion.pipeline --no-llm     # force the heuristic path
```

| Function | Signature | Notes |
| --- | --- | --- |
| `run` | `(data_dir=None, db_path=None, use_llm=None, reset=False, limit=None, allow_downgrade=False) → dict` | The whole pipeline. Returns a summary: `run_id`, counts, `confidence_{avg,min,max}`, `duration_ms`. |
| `EnrichmentDowngrade` | `RuntimeError` | Raised before anything is written when a heuristic run would overwrite Claude-enriched documents. `persist_document` replaces in place, so `--no-llm` over an LLM-enriched database rewrites every summary and action item at roughly half the confidence and exits 0 — indistinguishable from a successful re-index. Cleared by `--reset` or `--allow-downgrade`. |
| `discover_files` | `(data_dir) → list[Path]` | Recursive, extension-filtered, skips Office lock files (`~$…`) and dotfiles. |
| `parse_file` | `(path, project_root) → Document` | Dispatches on suffix via `PARSERS`. |
| `load_people_directory` | `(data_dir) → dict[str, dict]` | Optional `data/people.yaml`. Accepts a mapping or a list of `{name, …}`. A missing or malformed file is a warning, not a failure — people are still created from attendee lines. |
| `_relative` | `(path, root) → str` | Repo-relative POSIX paths, so citations are identical on every machine. |
| `main` | `() → None` | argparse CLI: `--data-dir`, `--db`, `--reset`, `--limit`, `--llm/--no-llm`, `--allow-downgrade`, `-v`. |

**Failure policy.** Each document is wrapped independently. A parse, enrich or
persist failure increments a counter, writes an `ingestion_errors` row, rolls
back that document, and the run continues — one bad file never kills the batch.
FTS is rebuilt once at the end.

---

## Enrichment

### `app/enrichment/taxonomy.py`

Controlled vocabularies, declared once: `TOPIC_DOMAINS` (11 values),
`PRIORITIES` (4), `QUALITY_FLAGS` (`stale`, `contradictory`, `sparse`,
`unattributed`, `draft`). `DOMAIN_CUES`, `HIGH_PRIORITY_CUES` and
`LOW_PRIORITY_CUES` are substring cues used **only** by the heuristic fallback.

Fixed enums rather than free text: the UI renders these as badges, so a corpus
where one document says `eng` and the next says `Engineering` breaks filtering.

### `app/enrichment/schema.py`

The contract in both directions — the LLM is constrained to emit it, and the
heuristic fallback constructs the same object, so persistence never needs to
know which path ran.

| Model | Fields |
| --- | --- |
| `DerivedDecision` | `text`, `decided_by`, `evidence` (required of the model but nullable — grounding clears unlocatable quotes). |
| `DerivedActionItem` | `text`, `owner`, `due_date`, `evidence`. |
| `DocumentEnrichment` | `topic_domain`, `priority`, `summary`, `decisions`, `action_items`, `quality_flags`, `source_quality` (0–1). |
| `EnrichmentResult` | `enrichment`, `method` (`llm \| heuristic`), `model`, `confidence`, `fell_back`, `error`. |

`TopicDomain` / `Priority` / `QualityFlag` are `Literal`s built from the
taxonomy, so they become `enum` in the JSON schema sent to the model — the
constraint is the model's problem rather than something cleaned up afterwards.

### `app/enrichment/enrich.py`

| Function | Signature | Notes |
| --- | --- | --- |
| `enrich_document` | `(document, use_llm=None) → EnrichmentResult` | **The entry point.** `use_llm=None` means "LLM if a key is configured". On any LLM failure it falls back to heuristics and records `fell_back=True` + `error` rather than swallowing it. |
| `score_confidence` | `(document, enrichment, method) → float` | `0.45·base + 0.35·source_quality + 0.20·completeness`, where `base` is `0.80` for LLM and `0.40` for heuristics. Then subtracts flag penalties (`sparse` 0.20, `stale` 0.12, `contradictory` 0.10, `draft` 0.08, `unattributed` 0.05) and `0.25 × ungrounded-evidence fraction`. Clamped to `[0.05, 1.0]`. |
| `_enrich_with_llm` | `(document) → DocumentEnrichment` | `messages.parse(..., output_format=DocumentEnrichment)` against `settings.enrichment_model`. |
| `_coerce` | `(enrichment) → DocumentEnrichment` | Clamps to the controlled vocabularies — defence in depth for the heuristic path and schema drift. |
| `_apply_mechanical_flags` | `(document, enrichment) → DocumentEnrichment` | Owns `unattributed`, which is a **fact about the file**, not a judgement. Set from the parse for both paths and never inherited from the model, which got it wrong (Haiku flagged a transcript with three named attendees). |
| `_ground_evidence` | `(document, enrichment) → int` | Runs `ground_items` over decisions and action items; returns how many quotes were dropped. |
| `_postprocess` | `(document, enrichment)` | Grounding + mechanical flags: everything that must hold regardless of path. |

Attendees, authors and dates are passed to the model **as context only**, never
as fields to produce — that is what keeps the stored values verbatim.

### `app/enrichment/heuristics.py`

| Function | Signature | Notes |
| --- | --- | --- |
| `enrich_heuristically` | `(document) → DocumentEnrichment` | Regex-cue extraction: up to 8 decisions and 10 action items from candidate sentences, owner via `OWNER_RE` (filtered against `NOT_OWNERS`), due date via `DUE_RE`, flags from text length and `DRAFT_RE`/`STALE_RE`/`CONTRADICTION_RE`. `source_quality` is pinned at **0.35** — cue matching cannot tell a decision from someone describing one. |
| `_classify_domain` | `(text) → str` | Ranks by the number of **distinct** cues matched, with total occurrences only breaking ties. Counting occurrences let boilerplate win: a repeated "Quarter" column header beat genuine finance cues. |
| `_classify_priority` | `(text) → str` | `high`/`low` on cue match; otherwise `medium` when the document is over 1500 chars, else `unspecified`. |
| `_cue_pattern` | `(cue) → re.Pattern` | Word-boundary-aware with a suffix allowance, so `p0` does not match inside a part number. |
| `_candidate_sentences` / `_summarise` | | Sentences of 20–400 chars, speaker-prefixed; summary is the first few substantial ones, tagged `[Heuristic summary]`. |

### `app/enrichment/grounding.py`

The model's quote is treated as a **pointer**, never as the citation itself.
Across a 37-document run Claude paraphrased ~4% of quotes — stitching
non-adjacent spans, merging two speakers, trimming a clause. Those read as
citations and are not.

| Function | Signature | Notes |
| --- | --- | --- |
| `ground_evidence` | `(raw_text, evidence, min_ratio=0.70) → tuple[str \| None, bool]` | Returns `(span, exact)`. `span` is copied out of `raw_text`, so it is always findable in the file. Exact match first on collapsed text; otherwise anchors on the longest shared run and fuzzy-scores a same-length window. `(None, False)` means "must not be presented as a citation". |
| `ground_items` | `(raw_text, items) → tuple[list, int]` | Rewrites each item's `evidence` in place; returns the items and the dropped count. An item whose quote cannot be located **keeps its text** (the extracted decision may still be correct) but loses its evidence. |
| `_collapse` | `(text) → tuple[str, list[int]]` | Whitespace-collapsed, punctuation-folded, casefolded text plus a per-character index map back into the original — the fold table is 1:1 so offsets survive. |

---

## Retrieval

### `app/retrieval/embeddings.py`

Local `sentence-transformers`, offline, no API key.

| Function | Signature | Notes |
| --- | --- | --- |
| `get_model` | `() → SentenceTransformer` | `lru_cache(1)`. Imported lazily — loading torch costs ~3 s and the API process should not pay it unless something embeds. |
| `embed` | `(texts, batch_size=32) → list[list[float]]` | `normalize_embeddings=True`, so cosine is a plain dot product and sqlite-vec's L2 distance is monotone in it. |
| `embed_one` | `(text) → list[float]` | |
| `serialize` / `deserialize` | `(vector) → bytes` / `(blob) → list[float]` | float32 little-endian — the layout a vec0 `FLOAT[N]` column expects. |

### `app/retrieval/search.py`

| Symbol | Signature | Notes |
| --- | --- | --- |
| `RetrievedChunk` | dataclass | Chunk fields **plus** the document context a citation needs (`source_path`, `title`, `attendees_or_author`, `quality_flags`, `enrichment_confidence`, …), so the traceability chain lives in one object. Carries `semantic`, `keyword` and fused `score`. |
| `RetrievedChunk.cosine` | `→ float` | Property. Un-normalises `semantic` back to raw cosine, for debugging and metrics. |
| `RetrievedChunk.relative_quality` | `float` | `enrichment_confidence` divided by the best in this corpus. What `source_trust` is computed from — see `quality_reference`. |
| `quality_reference` | `(conn) → float` | `MAX(enrichment_confidence)` over `documents`, or `1.0` for an empty corpus. Enrichment confidence is not comparable across backends: Claude scores this corpus at a mean of 0.82, the heuristic fallback scores the *same* documents at 0.46. Feeding the raw value into a score a fixed threshold gates made the answer-versus-route decision depend on the ingest flag — measured over the golden set, every confidence fell ~0.08 on the heuristic path and two answerable questions crossed into routing. Dividing by the corpus maximum keeps the ordering (a sparse scratch file still ranks below a spec) and drops the offset that only says which enricher ran. |
| `ConfidenceSignal` | dataclass | `value` plus the parts it came from: `top_similarity`, `support`, `corroboration`, `source_trust`, `matched_documents`, `reasons`. |
| `ConfidenceSignal.as_dict` | `→ dict` | What the API ships inside `confidence_breakdown`. |
| `search` | `(conn, query_text, top_k=8, candidate_k=30) → list[RetrievedChunk]` | Hybrid: vec0 KNN ∪ FTS5, fused as `0.70·semantic + 0.30·keyword`. Empty query returns `[]`. Source type never enters the ranking. |
| `compute_confidence` | `(chunks) → ConfidenceSignal` | `0.40·top_similarity + 0.20·support + 0.15·corroboration + 0.25·source_trust`. Also fills `reasons` in plain language. |
| `is_confident` | `(value) → bool` | `value >= settings.confidence_threshold`. |
| `_fts_match_expression` | `(query_text) → str` | Every token double-quoted and `OR`-joined: escapes FTS5 operators (a bare `Helios-3` parses as `NOT`) and keeps user punctuation from becoming a syntax error. |
| `_keyword_candidates` | `(conn, query_text, limit) → dict[int, float]` | Rank-derived score `1/(1+0.25·rank)`, not raw bm25 — bm25 is unbounded and corpus-dependent, so it cannot be blended with a similarity. A malformed expression degrades to semantic-only rather than 500. |
| `_vector_candidates` | `(conn, vector, limit) → dict[int, float]` | vec0 `MATCH … k = ?`; converts distance with `cos = 1 − d²/2` (valid because vectors are L2-normalised). |
| `_normalise_similarity` | `(cosine) → float` | Maps the band that actually discriminates (`SIM_FLOOR 0.20` → `SIM_CEIL 0.70`) onto 0–1. Measured on this corpus, off-topic questions top out at 0.24–0.28 while answerable ones peak at 0.61–0.66, so raw cosine is useless as a confidence. |
| `_cosine_from_blob` | `(blob, vector) → float` | Similarity for a keyword-only hit the KNN arm did not return. |

**Why both arms.** The vector arm answers paraphrases; it degrades on rare
literal tokens (part numbers, "SEMI S2"), which is exactly where keyword is
strong. Confidence is computed from the *fused* result and never hardcoded,
because it is what gates routing to a human.

---

## Query pipeline

### `app/query/claude.py`

`get_client()` — `lru_cache(1)` Anthropic client for the query path. Cached
because each construction rebuilds an httpx client and, behind the corporate
proxy, a fresh TLS context. Kept separate from enrichment, which is a batch job
in its own process.

### `app/query/synthesis.py`

The model is asked for a **list of claims each carrying its source numbers**,
not for prose with markers to parse out. Two things fall out of that: every
sentence is individually traceable, and a claim citing a number outside the
retrieved set is detectably ungrounded.

| Symbol | Signature | Notes |
| --- | --- | --- |
| `SynthesizedClaim` / `SynthesizedAnswer` | pydantic | The `output_format` the model must fill: `answerable`, `claims[]`, `caveat`. |
| `Claim` | dataclass | `text`, `chunk_ids` — after mapping back to real rows. |
| `AnswerDraft` | dataclass | `answerable`, `answer`, `claims`, `caveat`, `support` (grounded fraction), `method`, `model`, `dropped_citations`, `error`. |
| `synthesize` | `(query_text, chunks) → AnswerDraft` | **Entry point.** No chunks → unanswerable. No API key → extractive. Any model failure → extractive with `error` set; one bad call degrades the answer, it never 500s the query. |
| `_synthesize_with_llm` | `(query_text, chunks) → AnswerDraft` | `messages.parse` with `SYSTEM_PROMPT`; `answerable` requires the model's flag **and** at least one grounded claim. |
| `_ground` | `(parsed, chunks) → tuple[list[Claim], int]` | Maps 1-based source numbers to chunk ids, counting anything out of range as dropped. The model never sees real ids, so a hallucinated citation is almost always an out-of-range number. |
| `_grounded_fraction` | `(claims) → float` | Fraction of claims with at least one valid chunk id — this becomes `answer_support`. |
| `_extractive` | `(query_text, chunks) → AnswerDraft` | Offline path: quotes the first two sentences of the best chunk verbatim. Real source text, so fully grounded, but a quoted passage rather than an answer — hence `EXTRACTIVE_SUPPORT = 0.75`. |
| `_format_sources` / `_build_user_prompt` | | Numbered blocks carrying path, anchor, date, people, quality flags and source confidence, truncated at 1800 chars each. |

`SYSTEM_PROMPT` is the behavioural contract: only the supplied sources, every
claim cited, `answerable=false` when the sources discuss the topic without
answering the question, and source conflicts recorded in `caveat` rather than
silently averaged.

### `app/query/routing.py`

The routee is **never** chosen by asking a model "who would know this?". It is
chosen by walking the same FK chain the citations use, so the suggested person
is always someone the corpus demonstrably records against the matched content,
and the rationale can quote the passage that put them there. The model only
phrases the draft question — the one part a human edits anyway.

| Symbol | Signature | Notes |
| --- | --- | --- |
| `RoutingDecision` | dataclass + `as_dict()` | The `routing` block of the query response. |
| `route` | `(conn, query_text, chunks, signal, reason) → RoutingDecision \| None` | **Entry point.** Returns `None` when nothing in the corpus is about the question, so naming whoever sits nearest an unrelated paragraph would be the same fabrication as inventing an answer. The caller still logs the gap. **Two** checks against `MIN_ATTRIBUTION_SIMILARITY` (0.25), because they are different chunks: the corpus-wide `signal.top_similarity` first, then `candidate.best_chunk.semantic` — the passage the rationale will actually quote. Only the first existed at one point, and *"what is Meridian's parental leave policy?"* cleared it at 0.27 and was then justified by a 0.22 paragraph about test-cell integration. Ranking fuses keyword overlap with semantics, so the quoted chunk can score 0.00 on meaning alone. |
| `choose_routee` | `(conn, chunks) → _Candidate \| None` | Scores people over the top `ATTRIBUTION_DEPTH` (5) chunks, **per document using that document's strongest chunk**, so a long file cannot out-vote a precise one just by having more pieces. |
| `_people_for_documents` | `(conn, document_ids) → dict[int, list[Row]]` | One batched join across `document_people`/`people`. |
| `_build_rationale` | `(candidate, signal) → str` | Names the source and anchor, quotes the evidence, adds multi-document support and the retrieval weakness that forced routing. |
| `_evidence_excerpt` | `(candidate) → str` | When the person is named in the matched text, quotes **the line that names them** — that is the evidence, not the paragraph around it. |
| `_draft_question` | `(query_text, candidate) → str` | LLM-phrased via `settings.synthesis_model`; falls back to `_fallback_draft` with no key or on any error. |

Scoring constants: `ROLE_WEIGHTS` `author 1.0 / action_owner 0.85 /
attendee 0.45`, `MENTION_BONUS` `+0.8` when the person's **full** name appears
in the matched passage (a bare first name is ambiguous across the directory),
`UNDIRECTORIED_FACTOR` `×0.5` for people with no department — those rows came
out of action-item text ("Dana will produce the RCA") and may be fragments or
not people at all, so they are pickable but never preferred.

### `app/query/service.py`

One function owns the order of operations, so every query — answered or routed
— leaves the same trail.

| Symbol | Signature | Notes |
| --- | --- | --- |
| `QueryOutcome` | dataclass | Exactly what `POST /query` serialises. |
| `answer_query` | `(conn, query_text, top_k=8) → QueryOutcome` | **The pipeline.** Retrieve → confidence → *(gate 1)* synthesise → *(gate 2)* discount → answer or route → `log_query` (+ `record_gap`) → commit. |
| `_grounding_multiplier` | `(support) → float` | `0.35 + 0.65 × support`. A fully grounded draft keeps its retrieval score; a wholly ungrounded one keeps `UNGROUNDED_FLOOR` of it. |
| `_confidence_breakdown` | `(signal, confidence, draft) → dict` | Spells out `value = retrieval_confidence × grounding_multiplier`. `answer_support` and `grounding_multiplier` are `None` — not `0.0` — when gate 1 stopped the query, because reporting zero would read as "checked, found nothing". |
| `_routing_reason` | `(signal, confidence, draft) → str` | Three distinct phrasings so gate-2 failures do not read as retrieval failures. |
| `_build_citations` | `(chunks, draft) → tuple[list[dict], list[dict]]` | Citations ordered by score; claims rewritten to carry **positions** in that list so the UI can render `[1]` without a second lookup. Falls back to the top 3 chunks when there is no draft. |
| `_citation` | `(chunk) → dict` | Every field read off a real row. |
| `_derived_metadata` | `(chunks, citations, draft) → dict` | Document-level badges, read off `documents` rather than re-derived. `topic_domain` is **score-weighted**, not counted — three weak sources should not outvote the one the answer came from. |

**The two gates, in order.**

1. `is_confident(signal.value)` — below threshold, route **without** a model
   call. There is then no weak answer for anyone to be tempted by.
2. `confidence = signal.value × _grounding_multiplier(draft.support)` — the
   draft's own grounding discounts the retrieval score. This is what stops a
   fluent answer about the right *topic* from passing as an answer to the
   question actually asked ("what is the nine pass number" retrieves every
   Helios-3 chunk and scores well on all four retrieval signals).

---

## Persistence — `app/db/`

### `app/db/connection.py`

| Function | Signature | Notes |
| --- | --- | --- |
| `get_connection` | `(db_path=None) → sqlite3.Connection` | `row_factory = Row`, loads the `sqlite_vec` extension, `PRAGMA foreign_keys = ON`. |
| `init_db` | `(db_path=None) → None` | Executes `schema.sql` with `{embedding_dim}` substituted — vec0 needs a literal dimension. Idempotent. |

`python -m app.db.connection` initialises the schema in place.

### `app/db/repository.py`

All SQL lives here, so the FK chain `chunks → documents → document_people →
people` is established once and cannot drift between the pipeline and the API.

**Ingestion-time writes**

| Function | Signature | Notes |
| --- | --- | --- |
| `utcnow` | `() → str` | ISO-8601 UTC, second precision. Every timestamp in the system. |
| `upsert_person` | `(conn, name, title=None, department=None, email=None) → int` | `ON CONFLICT(name)` with `COALESCE`, so a later sparse mention never blanks directory data. |
| `resolve_person` | `(conn, name) → int \| None` | Merges a partial name ("Dana") onto an **existing** person, only when exactly one matches. Never creates: `None` means no edge. Only a verbatim attendee/author line or `data/people.yaml` may add to `people`, because they are the only places a name is stated by the source rather than derived by a model. Enrichment also yields owners that are departments (`Product`, from the Kestrel-2 draft spec) or placeholders (`TBD`); those stay text on the `action_items` row and never become a node the routing walk can reach. |
| `link_person` | `(conn, document_id, person_id, role) → None` | `INSERT OR IGNORE` into `document_people`. |
| `persist_document` | `(conn, document, result, chunks, embeddings) → int` | One fully-processed document. Deletes any prior row for the same `source_path` first, so re-ingestion is idempotent. Raises when chunk and embedding counts disagree. Writes both the `chunks.embedding` blob and the `chunk_vectors` KNN row, sets `evidence_verified` from whether grounding kept the quote, and links people (`attendee` for transcripts, `author` otherwise, plus `action_owner`). |
| `delete_document` | `(conn, source_path) → None` | Cascades cover `chunks`/`decisions`/…, but **not** `chunk_vectors` — vec0 is a virtual table, so its rows are deleted explicitly. |
| `rebuild_fts` | `(conn) → None` | `INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')`. Cheap at this corpus size and immune to the trigger drift a partial re-ingest causes. |

**Instrumentation**

`start_ingestion_run(conn, data_dir, method) → int`,
`log_ingestion_error(conn, run_id, source_path, stage, error)`,
`log_enrichment(conn, run_id, source_path, result)`,
`finish_ingestion_run(conn, run_id, doc_count, chunk_count, parse_failures,
enrichment_failures, confidences, duration_ms)`.

**Query-time writes and reads**

| Function | Signature | Notes |
| --- | --- | --- |
| `log_query` | `(conn, query_text, answer, confidence, matched_chunk_ids, latency_ms, routed, source_types) → int` | Written for **every** query, answered or routed — `/metrics` reads the routing rate off this table. |
| `get_query` | `(conn, query_id) → Row \| None` | |
| `record_gap` | `(conn, query_id, reason, suggested_routing_person, suggested_person_id, routing_rationale, matched_content, draft_question) → int` | Status starts `open`. |
| `list_gaps` | `(conn, status=None, since=None, limit=100) → list[Row]` | Joined to `query_log` (required) and `people` (optional). A gap with no query text is untriageable, so the read path never returns a bare reason. |
| `set_gap_status` | `(conn, gap_id, status) → Row \| None` | Stamps `resolved_at` on `resolved`, clears it otherwise. |
| `record_correction` | `(conn, query_id, original_answer, corrected_answer, corrected_by) → int` | |
| `list_corrections` | `(conn, query_id=None, corrected_by=None, since=None, limit=100) → list[Row]` | Joined to `query_log`. |
| `get_document` / `get_document_chunks` / `get_document_people` / `get_document_decisions` / `get_document_action_items` | `(conn, document_id)` | The provenance reads behind `GET /documents/{id}`. |
| `find_person` | `(conn, name) → Row \| None` | Case-insensitive exact match; the guard behind `POST /routing/send`. |
| `metrics_snapshot` | `(conn, window=50) → dict` | Everything `/metrics` serves, in one pass. All-time **and** trailing-window figures; `answered_without_intervention` counted per query, not by adding two rates. |
| `_percentile` | `(values, fraction) → float \| None` | Nearest-rank, used for the latency p50/p95. |

### `app/db/schema.sql`

Tables: `documents`, `chunks`, `chunk_vectors` (vec0 virtual), `chunks_fts`
(FTS5 external-content over `chunks`, porter/unicode61), `people`,
`document_people`, `decisions`, `action_items`, `query_log`, `corrections`,
`gaps`, `ingestion_runs`, `ingestion_errors`, `enrichment_log`.

`{embedding_dim}` is the only placeholder, substituted by `init_db()`.

---

## API layer — `app/api/`

### `app/api/deps.py`

`db() → Iterator[sqlite3.Connection]` — one connection per request, closed in a
`finally`. Deliberately **not** a module-level singleton: FastAPI runs sync
endpoints in a thread pool and a sqlite3 connection belongs to its creating
thread. Connections are cheap here (a local file plus the extension load) and
this keeps each request's transaction isolated.

### Route modules

Each module owns one resource and validates its own input with pydantic; the
shapes are documented in [API_REFERENCE.md](API_REFERENCE.md).

| Module | Handlers | Response models |
| --- | --- | --- |
| `routes/query.py` | `query` | `QueryRequest`, `QueryResponse`, `Citation`, `Claim`, `Routing` |
| `routes/documents.py` | `get_document` | plain dict; parses the JSON columns and **nulls unverified evidence** |
| `routes/corrections.py` | `create_correction`, `list_corrections` | `CorrectionRequest` |
| `routes/gaps.py` | `list_gaps`, `update_gap` | `GapStatusUpdate`; `STATUSES = {"open","resolved"}` |
| `routes/metrics.py` | `get_metrics` | plain dict + `confidence_threshold` |
| `routes/routing.py` | `send_routing` | `RoutingSendRequest`; 404s on a person the corpus does not record |

### `app/main.py`

Builds the `FastAPI` app, mounts the six routers, and exposes `GET /health`.

CORS: an explicit allowlist when `settings.cors_origins` is non-empty,
otherwise the regex `http://(localhost|127\.0\.0\.1)(:\d+)?`. The dev server
does not own a fixed port — Vite silently moves to 5174 when 5173 is taken, and
pinning one origin makes that look like the API is down. `allow_credentials`
stays off, so a permissive local origin grants a page nothing it could not get
by calling the API directly.

---

## MCP server — `app/mcp_server.py`

A second transport over the same service layer, not a second implementation.
Every tool calls `app.query.service` and `app.db.repository` directly: the same
two confidence gates, the same routing walk, the same citation shape, the same
`query_log` and `gaps` rows. MCP traffic therefore reaches `/metrics` like any
other caller.

```bash
python -m app.mcp_server                          # stdio
claude mcp add meridian-kb -- python -m app.mcp_server
```

| Tool | Signature | Notes |
| --- | --- | --- |
| `ask` | `(question, top_k=8) → str` | Rendered prose with inline `[n]` markers, then `---`, then the same JSON payload `POST /query` returns. Excerpts truncated to `MAX_EXCERPT` (400). |
| `read_document` | `(document_id, include_raw_text=False) → str` | JSON. Same withholding rule as `GET /documents/{id}`: evidence that could not be located verbatim in the source is nulled rather than shown. `raw_text` off by default. |
| `open_gaps` | `(limit=20) → str` | Open gaps newest first, joined to the query that caused each. |
| `health` | `(window=50) → str` | The `/metrics` snapshot plus `confidence_threshold`. |
| `_db` | contextmanager | One connection per tool call, for the reason `api/deps.py` gives. |
| `_render` | `(outcome) → str` | Claims with their markers, then sources, then the confidence and `query_id`. A model that has to rebuild the claim→citation mapping from an array of indices will sometimes get it wrong, and a wrong citation is worse here than a verbose one. |
| `main` | `() → None` | Fails fast with an actionable message when the database is missing or unreadable, then `mcp.run()` on stdio. Logging goes to `WARNING` because stdout is the transport. |

**Read-only on purpose.** Corrections and gap triage stay on the HTTP API
behind the review queue: both are human judgements about a specific answer, and
an assistant resolving its own gaps is a loop with nobody in it.

`MCPServer` is the SDK's high-level server class; it was called `FastMCP`
before `mcp` 2.0, which is what most examples still show.

---

## Answer-quality gate — `eval/`

The unit tests pin the mechanics — a citation resolves, a threshold is applied,
a correction is stored. None of them can fail when the system starts answering
questions it should route, which is the failure users experience.

### `eval/golden.yaml`

19 cases. Each states the outcome the corpus justifies and a `why` that argues
it from the source files rather than from what the system currently returns.

| Field | Meaning |
| --- | --- |
| `expect` | `answered` or `routed`. Checked on both backends. |
| `must_cite` | Substrings of `source_path` the citations must **all** include. |
| `must_cite_any` | At least one must match — for facts several documents state properly. |
| `must_mention` / `must_not_mention` | Strings in the answer. **Synthesised prose only**: the extractive backend returns a passage verbatim, so checking it offline would measure chunk boundaries rather than the system. |
| `route_to` / `routes_to_nobody` | The routee, or the assertion that no one should be named. Backend-independent — no model touches the routing walk. |
| `requires: llm` | Only the model can make this call; offline runs report it as excluded, not as a pass. |

### `eval/run_eval.py`

| Symbol | Signature | Notes |
| --- | --- | --- |
| `run` | `(cases, db_path=None) → list[CaseResult]` | Runs each case through `answer_query`, skipping `requires: llm` when no key is configured. |
| `_check` | `(case, outcome, backend) → list[str]` | One failure string per broken assertion, so a case reports everything wrong with it at once. |
| `_bands` | `(results) → dict` | Min/max confidence per outcome, whether the threshold separates them, and `narrowest_margin` — the answered case sitting closest to the threshold, named. A gate that only counts passes hides the margin: if the answered floor drifts toward the threshold, the next corpus change flips a query with no test failing first. |
| `_markdown` | `(results, bands, backend) → str` | The GitHub step summary. Written on failure too, so a red run explains itself on the run page instead of in a log that needs a token to read. |
| `validate` | `(cases) → None` | Refuses a golden file where a `requires: llm` case does not declare a `blind_spot`. An unexplained exclusion is indistinguishable from one added because the case was failing. |
| `_blind_spots` | `(results) → dict` | Exclusions grouped by what they leave untested, for the report and the step summary. |
| `main` | `() → int` | `--golden`, `--db`, `--offline`, `--json`, `--markdown`, `--require-llm`. Non-zero exit on any regression. |

```bash
python -m eval.run_eval              # whichever backend is configured
python -m eval.run_eval --offline    # extractive, what CI runs
```

**Run it against a database ingested the way the gate will ingest it.** This is
the whole reason `.github/workflows/ci.yml` re-ingests before grading: see
`quality_reference` above for the 0.08 systematic disagreement that cost two
golden cases before `source_trust` was made relative.

---

## Frontend

### `src/api/client.js`

See [API_REFERENCE.md § Frontend client](API_REFERENCE.md#frontend-client) for
the method table.

| Symbol | Notes |
| --- | --- |
| `BASE_URL` | `VITE_API_BASE_URL` or `http://localhost:8000`. |
| `api` | The nine call wrappers. |
| `request(path, options)` | Retries **reads only**, twice, on a `NetworkError`. A retried POST could double-write, and a correction stored twice is worse than an error message. |
| `send(path, options)` | Sets `Content-Type` only when there is a body, keeping GETs free of a CORS preflight. Throws a renderable error. |
| `detailOf(body)` | FastAPI `detail` is a string for `HTTPException` and a list for validation errors; both are flattened to one message. |
| `queryString(params)` | Drops `undefined` / `null` / `""`. |

### `src/lib/format.js`

| Function | Notes |
| --- | --- |
| `fileName(path)` | Basename, splitting on either slash. |
| `formatTimestamp(value)` | Stored timestamps are UTC; appends `Z` when absent and renders local. Returns the raw value if unparseable. |
| `percent(value)` | `0.734 → "73%"`; `null`/`undefined` → `—`. |

### Components and pages

| File | Export | Role |
| --- | --- | --- |
| `App.jsx` | `App` | Shell and tab routing; `ApiStatus` polls `/health`. |
| `pages/AskPage.jsx` | `AskPage` | The query screen: submit, answer or routing, source drawer. |
| `pages/ReviewQueuePage.jsx` | `ReviewQueuePage` | Gaps and corrections; `GapRow` resolves/reopens, `CorrectionRow` renders the pair. |
| `pages/MeasurementPage.jsx` | `MeasurementPage` | `/metrics` dashboard. `MetricsBody`, `Tile`, `latencyHint`, `toneFor` (colours a recent figure against its all-time baseline). |
| `components/AnswerCard.jsx` | `AnswerCard` | Claims with `[n]` markers (`CitationMarker`) and the confidence derivation (`Breakdown`). |
| `components/RoutingCard.jsx` | `RoutingCard`, `NoRouteeCard` | The routee, rationale and editable draft question; `NoRouteeCard` covers `routing_unavailable`. |
| `components/SourceDrawer.jsx` | `SourceDrawer` | `GET /documents/{id}` provenance view; `DocumentBody` highlights the cited chunk. `Evidence` renders the quote only when `evidence_verified`, and otherwise says the quote was withheld — more useful than showing nothing. |
| `components/CorrectionForm.jsx` | `CorrectionForm` | Posts to `/corrections`. |
| `components/ui.jsx` | `Badge`, `ErrorNote`, `Empty`, `Spinner`, `ConfidenceMeter` | Shared primitives; `ConfidenceMeter` draws the value against the threshold. |

---

## Scripts and tests

| Path | Purpose |
| --- | --- |
| `backend/scripts/generate_office_corpus.py` | Authors `data/office/*.docx\|pptx\|xlsx` from source text held in the script — the binaries' reviewable form. Idempotent: every file is rewritten from scratch. |
| `backend/scripts/inspect_db.py` | Proves the populated DB has correct traceability chains without the API — checks, not just counts, so an orphaned chunk or a citation resolving to nothing is caught. Run `python -m scripts.inspect_db` from `backend/`. |
| `scripts/smoke_test.sh` | End-to-end API smoke test against a running server. |
| `.github/workflows/ci.yml` | Ingest (heuristic, no key) → `inspect_db` → pytest → eval gate, plus a frontend lint and build. Runs on every push and PR. |
| `.github/workflows/eval-llm.yml` | Weekly and on demand: ingest with Claude → `inspect_db` → all 19 golden cases against the real model. Covers the blind spots the keyless gate declares. `--require-llm` makes a missing secret fail loudly rather than silently grading the extractive backend. Not triggered by `pull_request`, because secrets do not reach forked PRs. |

Test modules mirror the packages: `test_parsers.py`, `test_pipeline.py`,
`test_enrichment.py`, `test_grounding.py`, `test_search.py`,
`test_synthesis.py`, `test_routing.py`, `test_api.py`, `test_mcp.py`, with
shared fixtures in `conftest.py`. Two do not mirror a package:

| Module | What it is for |
| --- | --- |
| `test_corpus.py` | Reads `data/` directly — no database, no model, no key. Recomputes the spreadsheets against the narrative they support (the four approved COGS-down actions must equal the standard-cost delta; gross margins must fall out of list price minus standard cost; the fan filter line must equal the BOM unit cost × 6; the build-rate column must be the binding constraint; every total must equal its line items) and checks the cast against `data/people.yaml`. Also asserts the *deliberate* defects are still defective, so an edit that "fixes" the stale budget deck fails instead of quietly deleting a test case Part 2 needs. |
| `test_mcp.py` | Asserts the MCP and HTTP surfaces return the same decision, confidence and citation ids for the same question. A second surface that drifts from the first is worse than no second surface. |

```bash
cd backend && pytest
```
