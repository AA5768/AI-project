# Meridian Robotics Knowledge System — FDE Take-Home

Unifies three take-home exercises (transcripts → +Office docs/traceability/routing → user-facing app)
into one system. See [PROJECT_INSTRUCTIONS.md](PROJECT_INSTRUCTIONS.md) for the full spec.

**Primary AI tool used to build this project: Claude Code (CLI).**

## Stack

- **Storage**: SQLite (`sqlite-vec` for embeddings + FTS5 for keyword fallback)
- **Embeddings**: local `sentence-transformers` (`all-MiniLM-L6-v2`)
- **LLM**: Claude via the Anthropic API (Haiku for enrichment, Sonnet for query synthesis/routing)
- **API**: FastAPI
- **UI**: React + Vite

## Repo layout

```
data/transcripts/       # meeting transcripts (.md + YAML frontmatter)
data/office/             # decks, docs, spreadsheets (.docx/.pptx/.xlsx)
backend/                 # ingestion, db schema, FastAPI app
frontend/                # React app
scripts/smoke_test.sh    # end-to-end API smoke test
```

## Setup

### Backend

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp ../.env.example ../.env    # fill in ANTHROPIC_API_KEY
python -m app.db.connection   # initialize the SQLite schema
python -m app.ingestion.pipeline   # ingest data/ into the database
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Smoke test

With the API running:

```bash
bash scripts/smoke_test.sh
```

## Measurement approach (first 30 days)

*TODO — one paragraph, per PROJECT_INSTRUCTIONS.md Part 3 §4: pick a first-30-days metric
(e.g. % of queries answered without routing/correction) and describe how `query_log` +
`corrections`/`gaps` counts feed weekly aggregation via `/metrics`.*

## Status

Project structure initialized. Data corpus, ingestion/enrichment, retrieval, API logic, and UI
are not yet implemented — see stub files (`NotImplementedError`) and `TODO` markers throughout
`backend/app/`.
