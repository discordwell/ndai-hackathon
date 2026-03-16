#!/bin/bash
# NDAI end-to-end smoke test
# Usage: ./deploy/smoke-test.sh <host> [port]
set -euo pipefail

HOST="${1:?Usage: ./deploy/smoke-test.sh <host> [port]}"
PORT="${2:-80}"
BASE="http://$HOST:$PORT"
PASS=0
FAIL=0

check() {
  local name="$1"
  shift
  if "$@"; then
    echo "  PASS: $name"
    ((PASS++))
  else
    echo "  FAIL: $name"
    ((FAIL++))
  fi
}

echo "=== NDAI Smoke Test: $BASE ==="

# 1. Health check
echo ""
echo "[1/6] Health check"
HEALTH=$(curl -sf "$BASE/health" 2>/dev/null || echo '{}')
check "GET /health returns ok" [ "$(echo "$HEALTH" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)" = "ok" ]

# 2. Register seller
echo ""
echo "[2/6] Register seller"
SELLER=$(curl -sf -X POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke-seller@test.com","password":"smoke123","role":"seller","display_name":"Smoke Seller"}' 2>/dev/null || echo '{}')
SELLER_TOKEN=$(echo "$SELLER" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
check "Seller registration returns token" [ -n "$SELLER_TOKEN" ]

# 3. Register buyer
echo ""
echo "[3/6] Register buyer"
BUYER=$(curl -sf -X POST "$BASE/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"smoke-buyer@test.com","password":"smoke123","role":"buyer","display_name":"Smoke Buyer"}' 2>/dev/null || echo '{}')
BUYER_TOKEN=$(echo "$BUYER" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("access_token",""))' 2>/dev/null)
check "Buyer registration returns token" [ -n "$BUYER_TOKEN" ]

# 4. Create invention
echo ""
echo "[4/6] Create invention"
INVENTION=$(curl -sf -X POST "$BASE/api/v1/inventions/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $SELLER_TOKEN" \
  -d '{
    "title":"Smoke Test Invention",
    "full_description":"A test invention for smoke testing the deployment.",
    "technical_domain":"testing",
    "novelty_claims":["Automated smoke test validation"],
    "development_stage":"concept",
    "self_assessed_value":0.6,
    "outside_option_value":0.3,
    "anonymized_summary":"A novel testing method",
    "category":"Software"
  }' 2>/dev/null || echo '{}')
INVENTION_ID=$(echo "$INVENTION" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))' 2>/dev/null)
check "Invention created with ID" [ -n "$INVENTION_ID" ]

# 5. Create agreement
echo ""
echo "[5/6] Create agreement + set params + confirm"
AGREEMENT=$(curl -sf -X POST "$BASE/api/v1/agreements/" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -d "{\"invention_id\":\"$INVENTION_ID\",\"budget_cap\":0.8}" 2>/dev/null || echo '{}')
AGREEMENT_ID=$(echo "$AGREEMENT" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("id",""))' 2>/dev/null)
check "Agreement created" [ -n "$AGREEMENT_ID" ]

# Set params
PARAMS=$(curl -sf -X POST "$BASE/api/v1/agreements/$AGREEMENT_ID/params" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BUYER_TOKEN" \
  -d '{"alpha_0":0.3}' 2>/dev/null || echo '{}')
THETA=$(echo "$PARAMS" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("theta",""))' 2>/dev/null)
check "Params set, theta computed" [ -n "$THETA" ] && [ "$THETA" != "null" ]

# Confirm
CONFIRMED=$(curl -sf -X POST "$BASE/api/v1/agreements/$AGREEMENT_ID/confirm" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $BUYER_TOKEN" 2>/dev/null || echo '{}')
STATUS=$(echo "$CONFIRMED" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)
check "Agreement confirmed" [ "$STATUS" = "confirmed" ]

# 6. Start negotiation (simulated mode — will likely fail without API key but should return status)
echo ""
echo "[6/6] Start negotiation"
NEG_START=$(curl -sf -X POST "$BASE/api/v1/negotiations/$AGREEMENT_ID/start" \
  -H "Authorization: Bearer $BUYER_TOKEN" 2>/dev/null || echo '{}')
NEG_STATUS=$(echo "$NEG_START" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)
check "Negotiation started (status=$NEG_STATUS)" [ -n "$NEG_STATUS" ]

# If running, poll a few times
if [ "$NEG_STATUS" = "pending" ] || [ "$NEG_STATUS" = "running" ]; then
  echo "  Polling for completion..."
  for i in $(seq 1 15); do
    sleep 4
    POLL=$(curl -sf "$BASE/api/v1/negotiations/$AGREEMENT_ID/status" \
      -H "Authorization: Bearer $BUYER_TOKEN" 2>/dev/null || echo '{}')
    POLL_STATUS=$(echo "$POLL" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("status",""))' 2>/dev/null)
    echo "  Poll $i: status=$POLL_STATUS"
    if [ "$POLL_STATUS" = "completed" ] || [ "$POLL_STATUS" = "error" ]; then
      break
    fi
  done
  check "Negotiation finished (status=$POLL_STATUS)" [ "$POLL_STATUS" = "completed" ] || [ "$POLL_STATUS" = "error" ]
fi

# 7. Check frontend loads
echo ""
echo "[7/7] Frontend"
FRONTEND=$(curl -sf "$BASE/" 2>/dev/null || echo "")
check "Frontend HTML loads" echo "$FRONTEND" | grep -q "NDAI" 2>/dev/null

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[ "$FAIL" -eq 0 ] && echo "All checks passed!" || echo "Some checks failed."
exit $FAIL
