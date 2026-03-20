"""Comprehensive live test of Recall and Props features against paper concepts.

Tests the deployed site at shape.discordwell.com against the NDAI paper's
core security properties:

1. DISCLOSURE PARADOX (Recall): Credentials never leave the TEE boundary.
   Consumer gets only the action result, never the secret itself.
2. BOUNDED DISCLOSURE (Props): Raw transcripts are destroyed after processing.
   Only structured intelligence (summaries, action items) is returned.
3. POLICY ENFORCEMENT: Actions outside the allowed set are denied.
4. AUDIT TRAIL: All access attempts are logged.
5. OWNERSHIP ISOLATION: Users can only see their own data.
6. USE DEPLETION: Secrets have bounded use counts.
"""

import json
import sys
import time

import requests

BASE = "https://shape.discordwell.com/api/v1"


def register(email, role="seller"):
    r = requests.post(f"{BASE}/auth/register", json={
        "email": email, "password": "testpass123", "role": role,
        "display_name": f"Test {role}",
    })
    if r.status_code == 400 and "already registered" in r.text:
        r = requests.post(f"{BASE}/auth/login", json={
            "email": email, "password": "testpass123",
        })
    assert r.status_code == 200, f"Auth failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def test(name, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {name}" + (f" — {detail}" if detail else ""))
    return condition


# ──────────────────────────────────────────────────────────────────────
# Setup: create two users (owner and consumer)
# ──────────────────────────────────────────────────────────────────────
ts = int(time.time())
owner_token = register(f"owner-{ts}@test.com", "seller")
consumer_token = register(f"consumer-{ts}@test.com", "buyer")
other_token = register(f"other-{ts}@test.com", "seller")

passed = 0
failed = 0
total = 0


def check(name, condition, detail=""):
    global passed, failed, total
    total += 1
    if test(name, condition, detail):
        passed += 1
    else:
        failed += 1


# ======================================================================
# PART 1: CONDITIONAL RECALL — Paper's "Disclosure Paradox"
# ======================================================================
print("\n" + "=" * 60)
print("PART 1: CONDITIONAL RECALL (Disclosure Paradox)")
print("=" * 60)

# 1.1 Create a secret with policy
print("\n--- 1.1 Secret Creation ---")
r = requests.post(f"{BASE}/secrets/", json={
    "name": "AWS Production Key",
    "description": "Production AWS access key for S3 operations",
    "secret_value": "AKIAIOSFODNN7EXAMPLE-supersecret",
    "policy": {
        "allowed_actions": ["list S3 buckets", "describe EC2 instances"],
        "max_uses": 3,
    },
}, headers=auth(owner_token))
assert r.status_code == 201, f"Create failed: {r.text}"
secret = r.json()
secret_id = secret["id"]

check("Secret created successfully", r.status_code == 201)
check("Secret value NOT in response", "AKIAIOSFODNN7EXAMPLE" not in json.dumps(secret),
      "Paper requires credentials never leave TEE boundary")
check("Policy preserved correctly", secret["policy"]["max_uses"] == 3)
check("Uses remaining matches max_uses", secret["uses_remaining"] == 3)
check("Status is active", secret["status"] == "active")

# 1.2 Secret value never exposed in ANY endpoint
print("\n--- 1.2 Secret Value Never Exposed (Core Security Property) ---")

r = requests.get(f"{BASE}/secrets/", headers=auth(owner_token))
check("List own secrets — value hidden",
      "AKIAIOSFODNN7EXAMPLE" not in r.text and "supersecret" not in r.text,
      "Even owner cannot retrieve the raw secret value")

r = requests.get(f"{BASE}/secrets/available", headers=auth(consumer_token))
check("Available secrets — value hidden",
      "AKIAIOSFODNN7EXAMPLE" not in r.text and "supersecret" not in r.text,
      "Consumer sees name + policy only")

r = requests.get(f"{BASE}/secrets/{secret_id}", headers=auth(consumer_token))
check("Secret detail — value hidden",
      "AKIAIOSFODNN7EXAMPLE" not in r.text and "supersecret" not in r.text)

# 1.3 Policy enforcement — allowed action
print("\n--- 1.3 Policy Enforcement ---")

r = requests.post(f"{BASE}/secrets/{secret_id}/use", json={
    "action": "list S3 buckets",
}, headers=auth(consumer_token))
check("Allowed action succeeds", r.status_code == 200 and r.json().get("success") is True,
      f"Action 'list S3 buckets' is in policy. Result: {r.json().get('result', '')[:80]}...")

# Verify the result doesn't contain the raw secret
if r.status_code == 200:
    use_result = r.json()
    check("Use result does NOT contain raw secret",
          "AKIAIOSFODNN7EXAMPLE" not in json.dumps(use_result) and "supersecret" not in json.dumps(use_result),
          "TEE returns only the action result, never the credential")
    check("Result has attestation_available flag", use_result.get("attestation_available") is True)

# 1.4 Policy enforcement — denied action
print("\n--- 1.4 Denied Action (Policy Violation) ---")

r = requests.post(f"{BASE}/secrets/{secret_id}/use", json={
    "action": "delete all S3 buckets and terminate all EC2 instances",
}, headers=auth(consumer_token))
check("Unauthorized action is denied", r.status_code == 200 and r.json().get("success") is False,
      "Paper requires strict policy boundary enforcement")
if r.status_code == 200:
    check("Denial explains policy",
          "not allowed" in r.json().get("result", "").lower() or "denied" in r.json().get("result", "").lower())

# 1.5 Use depletion
print("\n--- 1.5 Use Depletion (Bounded Disclosure) ---")

r = requests.get(f"{BASE}/secrets/{secret_id}", headers=auth(owner_token))
remaining = r.json()["uses_remaining"]
check("Uses decremented after valid use", remaining == 2,
      f"Expected 2, got {remaining} (denied actions should NOT consume uses)")

# Use again
r = requests.post(f"{BASE}/secrets/{secret_id}/use", json={
    "action": "describe EC2 instances",
}, headers=auth(consumer_token))
if r.status_code == 200 and r.json().get("success"):
    r2 = requests.get(f"{BASE}/secrets/{secret_id}", headers=auth(owner_token))
    remaining2 = r2.json()["uses_remaining"]
    check("Second valid use decrements", remaining2 == 1, f"Remaining: {remaining2}")

# 1.6 Owner cannot use own secret
print("\n--- 1.6 Owner Cannot Use Own Secret ---")
r = requests.post(f"{BASE}/secrets/{secret_id}/use", json={
    "action": "list S3 buckets",
}, headers=auth(owner_token))
check("Owner blocked from using own secret", r.status_code == 403,
      f"Got {r.status_code}: {r.text[:100]}")

# 1.7 Audit trail
print("\n--- 1.7 Audit Trail ---")

r = requests.get(f"{BASE}/secrets/{secret_id}/access-log", headers=auth(owner_token))
check("Owner can view access log", r.status_code == 200)
logs = r.json()
check("Access log records all attempts", len(logs) >= 2,
      f"Found {len(logs)} entries")
statuses = [l["status"] for l in logs]
check("Log contains approved entries", "approved" in statuses)
check("Log contains denied entries", "denied" in statuses)

# Consumer cannot view access log
r = requests.get(f"{BASE}/secrets/{secret_id}/access-log", headers=auth(consumer_token))
check("Consumer cannot view access log", r.status_code == 403,
      "Only owner has audit visibility")


# ======================================================================
# PART 2: PROPS — Paper's "Bounded Disclosure"
# ======================================================================
print("\n" + "=" * 60)
print("PART 2: PROPS (Bounded Disclosure)")
print("=" * 60)

TRANSCRIPT_1 = """
Alice: Let's discuss the Q2 roadmap. The auth service migration is blocking the mobile team.
Bob: Agreed. We need the new OAuth endpoints by March 15th. I'll handle the token refresh flow.
Charlie: The payment processor integration depends on the auth service too.
Alice: Great. Also, we decided to use PostgreSQL instead of MongoDB for the events store.
Bob: One blocker — we don't have staging environment access yet. DevOps ticket is open.
Alice: I'll follow up with the DevOps team today. Let's sync again Thursday.
Charlie: Can we get a cost estimate for the PostgreSQL migration by end of week?
"""

TRANSCRIPT_2 = """
Diana: Mobile team standup. We're blocked on the backend auth endpoints.
Eve: The API spec changed again — I need to re-do the token storage logic.
Diana: We decided to support offline mode. That means local credential caching.
Eve: Biggest blocker: no staging environment. We can't test the OAuth flow end-to-end.
Diana: Dependencies: backend auth service, push notification infrastructure.
Eve: I'll pair with Bob from backend on the token refresh implementation.
"""

# 2.1 Submit first transcript
print("\n--- 2.1 Transcript Submission ---")

r = requests.post(f"{BASE}/transcripts/", json={
    "title": "Q2 Backend Planning",
    "team_name": "Backend Team",
    "content": TRANSCRIPT_1,
}, headers=auth(owner_token))
check("Transcript submitted", r.status_code == 201)
t1 = r.json()
t1_id = t1["id"]

check("Status is completed (LLM processed)", t1["status"] == "completed",
      f"Got: {t1['status']}")
check("Raw content NOT in response",
      "OAuth endpoints" not in json.dumps(t1) and "Alice:" not in json.dumps(t1),
      "Paper: raw transcript destroyed, only metadata returned")
check("Content hash present", len(t1.get("content_hash", "")) == 64,
      "SHA-256 hash for verification")

# 2.2 Summary extraction quality
print("\n--- 2.2 Summary Quality (LLM Extraction) ---")

r = requests.get(f"{BASE}/transcripts/{t1_id}/summary", headers=auth(owner_token))
check("Summary retrieved", r.status_code == 200)
summary = r.json()

check("Has executive summary", len(summary.get("executive_summary", "")) > 20,
      f"Summary: {summary.get('executive_summary', '')[:100]}...")
check("Has action items", len(summary.get("action_items", [])) >= 1,
      f"Found: {summary.get('action_items', [])}")
check("Has key decisions", len(summary.get("key_decisions", [])) >= 1,
      f"Found: {summary.get('key_decisions', [])}")
check("Has dependencies", len(summary.get("dependencies", [])) >= 1,
      f"Found: {summary.get('dependencies', [])}")
check("Has blockers", len(summary.get("blockers", [])) >= 1,
      f"Found: {summary.get('blockers', [])}")
check("Has sentiment", summary.get("sentiment") in ("positive", "neutral", "negative"),
      f"Got: {summary.get('sentiment')}")
check("Has attestation flag", summary.get("attestation_available") is True)

# Verify raw transcript verbatim text is NOT in the summary
# Note: speaker names may appear in action items (e.g. "Bob: handle X") — that's correct extraction
check("Raw transcript verbatim NOT in summary",
      "Let's discuss the Q2 roadmap" not in json.dumps(summary)
      and "I'll handle the token refresh flow" not in json.dumps(summary),
      "Verbatim transcript sentences should not appear in summary")

# 2.3 Submit second transcript and test aggregation
print("\n--- 2.3 Cross-Team Aggregation ---")

r = requests.post(f"{BASE}/transcripts/", json={
    "title": "Mobile Team Standup",
    "team_name": "Mobile Team",
    "content": TRANSCRIPT_2,
}, headers=auth(owner_token))
check("Second transcript submitted", r.status_code == 201)
t2 = r.json()
t2_id = t2["id"]

# Aggregate
r = requests.post(f"{BASE}/transcripts/aggregate", json={
    "transcript_ids": [t1_id, t2_id],
}, headers=auth(owner_token))
check("Aggregation succeeds", r.status_code == 200)
agg = r.json()

check("Cross-team summary present", len(agg.get("cross_team_summary", "")) > 20,
      f"Summary: {agg.get('cross_team_summary', '')[:100]}...")
check("Shared dependencies identified", len(agg.get("shared_dependencies", [])) >= 1 or len(agg.get("shared_blockers", [])) >= 1,
      f"Deps: {agg.get('shared_dependencies', [])}, Blockers: {agg.get('shared_blockers', [])}")
check("Recommendations provided", isinstance(agg.get("recommendations", []), list))
check("Transcript count correct", agg.get("transcript_count") == 2)
check("Raw transcripts NOT in aggregation",
      "Alice:" not in json.dumps(agg) and "Diana:" not in json.dumps(agg),
      "Aggregation works on summaries, not raw content")

# 2.4 Ownership isolation
print("\n--- 2.4 Ownership Isolation ---")

r = requests.get(f"{BASE}/transcripts/{t1_id}", headers=auth(consumer_token))
check("Other user cannot view transcript", r.status_code == 403)

r = requests.get(f"{BASE}/transcripts/{t1_id}/summary", headers=auth(consumer_token))
check("Other user cannot view summary", r.status_code == 403)

# Other user cannot aggregate your transcripts
r = requests.post(f"{BASE}/transcripts/aggregate", json={
    "transcript_ids": [t1_id, t2_id],
}, headers=auth(consumer_token))
check("Other user cannot aggregate your transcripts", r.status_code == 403,
      "Ownership verified before aggregation")


# ======================================================================
# PART 3: EDGE CASES AND SECURITY BOUNDARIES
# ======================================================================
print("\n" + "=" * 60)
print("PART 3: EDGE CASES AND SECURITY")
print("=" * 60)

# 3.1 Unauthenticated access
print("\n--- 3.1 Authentication Required ---")

r = requests.get(f"{BASE}/secrets/")
check("Secrets list requires auth", r.status_code in (401, 403))

r = requests.get(f"{BASE}/transcripts/")
check("Transcripts list requires auth", r.status_code in (401, 403))

# 3.2 Invalid inputs
print("\n--- 3.2 Input Validation ---")

r = requests.post(f"{BASE}/secrets/", json={
    "name": "", "secret_value": "x", "policy": {"allowed_actions": [], "max_uses": 0},
}, headers=auth(owner_token))
check("Empty name rejected", r.status_code == 422)

r = requests.post(f"{BASE}/transcripts/", json={
    "title": "X", "content": "short",
}, headers=auth(owner_token))
check("Too-short transcript rejected", r.status_code == 422,
      "Content must be >= 10 chars")

# 3.3 Nonexistent resources
print("\n--- 3.3 Not Found Handling ---")

r = requests.get(f"{BASE}/secrets/00000000-0000-0000-0000-000000000000", headers=auth(owner_token))
check("Nonexistent secret returns 404", r.status_code == 404)

r = requests.get(f"{BASE}/transcripts/00000000-0000-0000-0000-000000000000", headers=auth(owner_token))
check("Nonexistent transcript returns 404", r.status_code == 404)

# 3.4 Aggregation minimum
r = requests.post(f"{BASE}/transcripts/aggregate", json={
    "transcript_ids": [t1_id],
}, headers=auth(owner_token))
check("Aggregation requires >= 2 transcripts", r.status_code == 422,
      f"Got {r.status_code}")


# ======================================================================
# RESULTS
# ======================================================================
print("\n" + "=" * 60)
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
print("=" * 60)

if failed > 0:
    print("\nFailed tests need investigation.")
    sys.exit(1)
else:
    print("\nAll tests passed! Features align with paper's security model.")
    sys.exit(0)
