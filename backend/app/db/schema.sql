-- Meridian Robotics knowledge base schema (see PROJECT_INSTRUCTIONS.md Part 1 §4)

CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL,
    source_type TEXT NOT NULL,          -- transcript | docx | pptx | xlsx
    attendees_or_author TEXT,           -- JSON array, verbatim from source
    date TEXT,
    topic_domain TEXT,
    priority TEXT,
    summary TEXT,
    raw_text TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    text TEXT NOT NULL,
    source_anchor TEXT,                 -- e.g. line range, slide #, cell ref
    embedding BLOB                      -- populated via sqlite-vec
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, content='chunks', content_rowid='id'
);

CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS action_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    text TEXT NOT NULL,
    owner TEXT,
    due_date TEXT
);

CREATE TABLE IF NOT EXISTS query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_text TEXT NOT NULL,
    answer TEXT,
    confidence REAL,
    timestamp TEXT NOT NULL,
    matched_chunk_ids TEXT              -- JSON array
);

CREATE TABLE IF NOT EXISTS corrections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL REFERENCES query_log(id),
    original_answer TEXT,
    corrected_answer TEXT NOT NULL,
    corrected_by TEXT,
    timestamp TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id INTEGER NOT NULL REFERENCES query_log(id),
    reason TEXT,
    suggested_routing_person TEXT,
    routing_rationale TEXT,
    draft_question TEXT,
    status TEXT NOT NULL DEFAULT 'open' -- open | resolved
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    doc_count INTEGER,
    parse_failures INTEGER,
    enrichment_confidence_avg REAL
);
