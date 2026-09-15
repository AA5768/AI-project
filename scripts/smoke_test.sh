#!/usr/bin/env bash
# Exercises the Part 2 API end-to-end against the Part 1 database:
# query -> citation -> low-confidence routing -> correction -> gap retrieval -> metrics.
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "== POST /query (expect high-confidence answer with citations) =="
QUERY_RESPONSE=$(curl -sf -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"text": "What did we decide about the warehouse robot arm program?"}')
echo "$QUERY_RESPONSE"

echo "== GET /documents/{id} (resolve first citation) =="
# TODO: extract a document id from $QUERY_RESPONSE citations once /query is implemented
# curl -sf "$BASE_URL/documents/1"

echo "== POST /query (expect low-confidence routing) =="
ROUTING_RESPONSE=$(curl -sf -X POST "$BASE_URL/query" \
  -H "Content-Type: application/json" \
  -d '{"text": "What is the exact budget line item for Q4 shipping costs?"}')
echo "$ROUTING_RESPONSE"

echo "== POST /corrections =="
curl -sf -X POST "$BASE_URL/corrections" \
  -H "Content-Type: application/json" \
  -d '{"query_id": 1, "corrected_answer": "Corrected answer text", "corrected_by": "test-user"}'
echo

echo "== GET /corrections =="
curl -sf "$BASE_URL/corrections"
echo

echo "== GET /gaps?status=open =="
curl -sf "$BASE_URL/gaps?status=open"
echo

echo "== GET /metrics =="
curl -sf "$BASE_URL/metrics"
echo

echo "== smoke test complete =="
