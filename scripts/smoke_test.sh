#!/usr/bin/env bash
# Part 2 exit criteria: exercises the API end-to-end against the Part 1 database.
#   query -> citation -> low-confidence routing -> correction -> gap retrieval -> metrics
#
# Queries below are chosen against the actual corpus in data/, not invented:
#   - the high-confidence one is covered by 5 documents across transcripts, a
#     docx and a pptx, all enriched at confidence >= 0.86;
#   - the low-confidence one asks for the "nine pass number", which appears in
#     exactly one place in the whole corpus -- an unmaintained, unattributed
#     scratch list (helios3-open-items.docx, confidence 0.29) whose own text is
#     "ask about the nine pass number". There is no answer to retrieve, so this
#     is the query that must route to a human instead of guessing.
#
# Requires the API to be running:  uvicorn app.main:app --port 8000
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"
PY="${PY:-python}"

# Pull a field out of a JSON response without depending on jq being installed.
json() { "$PY" -c 'import json,sys
data = json.load(sys.stdin)
for key in sys.argv[1].split("."):
    if data is None:
        break
    data = data[int(key)] if key.isdigit() else data.get(key)
print("" if data is None else data)' "$1"; }

fail() { echo "SMOKE TEST FAILED: $1" >&2; exit 1; }

echo "== GET /health =="
curl -sf "$BASE_URL/health" || fail "API is not reachable at $BASE_URL"
echo

echo "== POST /query (expect a confident answer with citations) =="
ANSWER=$(curl -sf -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"text": "What did we decide about the Northgate particle excursion?"}')
echo "$ANSWER"

CONFIDENCE=$(echo "$ANSWER" | json confidence)
DOC_ID=$(echo "$ANSWER" | json citations.0.document_id)
SOURCE=$(echo "$ANSWER" | json citations.0.source_path)
ANCHOR=$(echo "$ANSWER" | json citations.0.anchor)
QUERY_ID=$(echo "$ANSWER" | json query_id)

[ -n "$DOC_ID" ] || fail "no citation returned for a query the corpus can answer"
echo "  -> confidence=$CONFIDENCE  cited $SOURCE @ $ANCHOR (document $DOC_ID)"

echo "== GET /documents/{id} (the citation must resolve to a real row) =="
DOCUMENT=$(curl -sf "$BASE_URL/documents/$DOC_ID") || fail "citation pointed at document $DOC_ID, which does not exist"
echo "$DOCUMENT" | head -c 400
echo
RESOLVED=$(echo "$DOCUMENT" | json source_path)
[ "$RESOLVED" = "$SOURCE" ] || fail "citation said $SOURCE but document $DOC_ID is $RESOLVED"
echo "  -> citation resolves, author/attendees: $(echo "$DOCUMENT" | json attendees_or_author)"

echo "== POST /query (expect low confidence -> routing, not a guess) =="
ROUTED=$(curl -sf -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the nine pass number for Helios-3?"}')
echo "$ROUTED"

ROUTE_TO=$(echo "$ROUTED" | json routing.person)
[ -n "$ROUTE_TO" ] || fail "an unanswerable query returned no routing block"
echo "  -> routed to $ROUTE_TO"
echo "  -> rationale: $(echo "$ROUTED" | json routing.rationale)"
echo "  -> draft:     $(echo "$ROUTED" | json routing.draft_question)"

echo "== POST /routing/send (simulated) =="
curl -sf -X POST "$BASE_URL/routing/send" \
  -H "Content-Type: application/json" \
  -d "{\"query_id\": $(echo "$ROUTED" | json query_id), \"person\": \"$ROUTE_TO\", \"question\": \"Who owns the nine pass number?\"}"
echo

echo "== POST /corrections (tied to the real query_id from above) =="
[ -n "$QUERY_ID" ] || fail "/query did not return a query_id to correct against"
curl -sf -X POST "$BASE_URL/corrections" \
  -H "Content-Type: application/json" \
  -d "{\"query_id\": $QUERY_ID, \"corrected_answer\": \"The excursion was traced to the edge-grip end effector, not the FOUP loader.\", \"corrected_by\": \"smoke-test\"}"
echo

echo "== GET /corrections =="
curl -sf "$BASE_URL/corrections"
echo

echo "== GET /gaps?status=open =="
GAPS=$(curl -sf "$BASE_URL/gaps?status=open")
echo "$GAPS"
[ -n "$(echo "$GAPS" | json 0.id)" ] || fail "routing happened but no open gap was recorded"
echo

echo "== GET /metrics =="
curl -sf "$BASE_URL/metrics"
echo

echo "== smoke test complete =="
