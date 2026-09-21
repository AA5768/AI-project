-- Meridian Microsystems knowledge base schema (PROJECT_INSTRUCTIONS.md Part 1 section 4).
--
-- Traceability contract: every chunk resolves to exactly one document, and every
-- document carries the source_path plus the verbatim author/attendee list taken
-- from the file itself. Citations and routing in Part 2 are built by walking
-- chunks -> documents -> document_people, so nothing downstream has to invent a
-- filename or a person's name.
--
-- {embedding_dim} is substituted by init_db() -- vec0 needs a literal dimension.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS documents (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path           TEXT NOT NULL UNIQUE,   -- repo-relative, stable across machines
    source_type           TEXT NOT NULL,          -- transcript | docx | pptx | xlsx
    title                 TEXT,
    attendees_or_author   TEXT NOT NULL,          -- JSON array, verbatim from source
    date                  TEXT,                   -- ISO-8601 where the source gives one
    topic_domain          TEXT,                   -- LLM/heuristic derived
    priority              TEXT,                   -- high | medium | low | unspecified
    summary               TEXT,
    quality_flags         TEXT,                   -- JSON array: stale | contradictory | sparse | ...
    raw_text              TEXT NOT NULL,
    enrichment_method     TEXT NOT NULL,          -- llm | heuristic
    enrichment_model      TEXT,                   -- model id when method = llm
    enrichment_confidence REAL NOT NULL,          -- 0..1, how much to trust the derived metadata
    ingested_at           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_documents_source_type ON documents(source_type);
CREATE INDEX IF NOT EXISTS idx_documents_topic_domain ON documents(topic_domain);

CREATE TABLE IF NOT EXISTS chunks (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id    INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index    INTEGER NOT NULL,              -- ordinal within the document
    text           TEXT NOT NULL,
    source_anchor  TEXT NOT NULL,                 -- "lines 12-18" | "slide 3" | "Budget cells A4:D9"
    char_count     INTEGER NOT NULL,
    embedding      BLOB,                          -- float32 vector, source of truth
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);

-- KNN index over the same vectors held in chunks.embedding. Kept as a separate
-- vec0 table (rather than querying the BLOB column) so retrieval can use
-- `MATCH ... k = ?` instead of scanning every row in Python.
CREATE VIRTUAL TABLE IF NOT EXISTS chunk_vectors USING vec0(
    chunk_id  INTEGER PRIMARY KEY,
    embedding FLOAT[{embedding_dim}]
);

-- Keyword arm of hybrid retrieval. External-content table over chunks; the
-- pipeline issues a 'rebuild' after bulk insert rather than carrying triggers,
-- because ingestion always rewrites a document's chunks wholesale.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text,
    content='chunks',
    content_rowid='id',
    tokenize='porter unicode61'
);

-- People directory, populated from attendee/author lines actually present in the
-- corpus (optionally enriched by data/people.yaml). Part 2 routing picks a person
-- from here via document_people, so a suggested routee is always someone who
-- demonstrably touched the matched content.
CREATE TABLE IF NOT EXISTS people (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE,
    title      TEXT,
    department TEXT,
    email      TEXT
);

CREATE TABLE IF NOT EXISTS document_people (
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    person_id   INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,                    -- attendee | author | action_owner
    PRIMARY KEY (document_id, person_id, role)
);

-- `evidence` is copied out of documents.raw_text by enrichment/grounding.py, so
-- a non-null value is always findable in the source file. evidence_verified = 0
-- means the model's quote could not be located and was discarded; Part 2 must
-- not surface those as citations.
CREATE TABLE IF NOT EXISTS decisions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text              TEXT NOT NULL,
    decided_by        TEXT,
    evidence          TEXT,                       -- verbatim span of documents.raw_text
    evidence_verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS action_items (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id       INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text              TEXT NOT NULL,
    owner             TEXT,
    due_date          TEXT,
    evidence          TEXT,                       -- verbatim span of documents.raw_text
    evidence_verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS query_log (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text        TEXT NOT NULL,
    answer            TEXT,
    confidence        REAL,
    timestamp         TEXT NOT NULL,
    matched_chunk_ids TEXT,                       -- JSON array of chunks.id
    latency_ms        INTEGER,
    routed            INTEGER NOT NULL DEFAULT 0, -- 1 when confidence fell below threshold
    source_types      TEXT                        -- JSON array, which corpora the answer drew on
);

CREATE INDEX IF NOT EXISTS idx_query_log_timestamp ON query_log(timestamp);

CREATE TABLE IF NOT EXISTS corrections (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id         INTEGER NOT NULL REFERENCES query_log(id) ON DELETE CASCADE,
    original_answer  TEXT,
    corrected_answer TEXT NOT NULL,
    corrected_by     TEXT,
    timestamp        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gaps (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id                 INTEGER NOT NULL REFERENCES query_log(id) ON DELETE CASCADE,
    reason                   TEXT,
    suggested_routing_person TEXT,
    suggested_person_id      INTEGER REFERENCES people(id),
    routing_rationale        TEXT,
    matched_content          TEXT,                -- the excerpt that justified the routee
    draft_question           TEXT,
    status                   TEXT NOT NULL DEFAULT 'open',  -- open | resolved
    created_at               TEXT NOT NULL,
    resolved_at              TEXT
);

CREATE INDEX IF NOT EXISTS idx_gaps_status ON gaps(status);

-- Instrumentation (Part 1 section 5). Queryable rows, not log lines, so Part 2's
-- /metrics endpoint can aggregate ingestion health alongside query health.
CREATE TABLE IF NOT EXISTS ingestion_runs (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at                TEXT NOT NULL,
    finished_at               TEXT,
    data_dir                  TEXT NOT NULL,
    enrichment_method         TEXT NOT NULL,
    doc_count                 INTEGER NOT NULL DEFAULT 0,
    chunk_count               INTEGER NOT NULL DEFAULT 0,
    parse_failures            INTEGER NOT NULL DEFAULT 0,
    enrichment_failures       INTEGER NOT NULL DEFAULT 0,
    enrichment_confidence_avg REAL,
    enrichment_confidence_min REAL,
    enrichment_confidence_max REAL,
    duration_ms               INTEGER
);

CREATE TABLE IF NOT EXISTS ingestion_errors (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
    source_path TEXT,
    stage       TEXT NOT NULL,                    -- parse | enrich | embed | persist
    error       TEXT NOT NULL
);

-- Per-document enrichment outcome, kept even when the document itself is
-- re-ingested, so the confidence distribution has history to trend against.
CREATE TABLE IF NOT EXISTS enrichment_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES ingestion_runs(id) ON DELETE CASCADE,
    source_path TEXT NOT NULL,
    method      TEXT NOT NULL,
    confidence  REAL NOT NULL,
    fell_back   INTEGER NOT NULL DEFAULT 0,       -- 1 when the LLM path failed and heuristics ran
    timestamp   TEXT NOT NULL
);
