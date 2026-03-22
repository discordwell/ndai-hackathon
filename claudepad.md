# Claudepad - NDAI Session Memory

## Session Summaries

### 2026-03-23T07:00Z — zdayzk.com: Standalone Zero-Day Marketplace Frontend
- Built complete standalone frontend for zdayzk.com at `zdayzk-frontend/` — React 19 + TypeScript + Tailwind CSS, esbuild-bundled
- **Design**: Dark premium theme (surface-950 dark bg, gold accent-400, glass-morphism cards, system fonts for CSP/privacy safety)
- **Pages**: Landing (hero, how-it-works, trust signals, footer), Login/Register, Dashboard (unified dual-role), Marketplace (listings + filters + severity meter), Listing Detail + propose deal, Submit Vulnerability (3-step form), Deals List, Deal Page (status timeline + SSE live negotiation + outcome card + escrow panel + sealed delivery)
- **Architecture**: 44 source files — design system (Button, Card, Badge, Input, Select, Modal, Spinner), API client layer (typed fetch + JWT), AuthContext (zdayzk_token, no role concept), WalletContext placeholder (MetaMask optional), useNegotiationStream (SSE), useEscrow (ethers.js v6 VulnEscrow interaction), hash-based router, PublicLayout + AppLayout with sidebar
- **Backend changes**: Dual-role "user" registration (auth.py accepts role="user", default in schema), FRONTEND_DIR env var in app.py, Alembic migration for role server default
- **Deploy infra**: zdayzk.service (port 8101, workers 1 for SSE), Caddyfile.zdayzk (auto HTTPS), deploy-zdayzk.sh, setup-zdayzk.sh (shared DB, SSO via same SECRET_KEY). DNS: A records for zdayzk.com → 15.204.59.61
- **Code review fixes**: Removed Google Fonts CDN (CSP/privacy violation), fixed flex+block conflict, set workers=1 for SSE
- **Note**: Frontend currently wired to old `/vulns/` API — needs rewiring to `/zk-vulns/` if ZK auth is the intended auth model for zdayzk.com
- 4 new unit tests (dual-role schema), frontend builds clean (684K dist)

### 2026-03-22T23:00Z — CVE-2024-3094 Demo: Full Marketplace Lifecycle
- Built end-to-end hackathon PoC using XZ Utils backdoor (CVSS 10.0, March 2024) as showcase
- **Backdoor reproduction** (`demo/xz_backdoor/`): Faithful reproduction of attack pattern — liblzma LD_PRELOAD hook → RSA_public_decrypt interception → Ed448-signed command execution. Uses known test keypair, omits stealth obfuscation. Includes: backdoor_hook.c (~200 LOC), trigger_service.c, poc_trigger.py, Dockerfile.target, Ed448 key generation.
- **TargetSpec extension**: Added `build_steps` field to TargetSpec model for compile-from-source support. Security-validated (whitelisted commands, blocked network/shell injection). Renders as `RUN` commands in generated Dockerfile.
- **Combined demo session** (`ndai/enclave/vuln_demo_session.py`): Orchestrates verify → negotiate → seal pipeline with progress callbacks. Demo API router with SSE streaming at `/api/v1/vuln-demo/`.
- **Smart contract client alignment**: Fixed `vuln_escrow_client.py` to match actual `VulnEscrow.sol` interface (`submitVerification` not `submitOutcome`, `price` not `reservePrice`/`budgetCap`). Fixed `VulnEscrowState.Verified` (was `Evaluated`).
- **Demo frontend**: `VulnDemoPage.tsx` — dark-themed pipeline visualization with phase status indicators, real-time SSE event log, and result display.
- **Demo script**: `scripts/demo_xz_backdoor.py` — terminal presenter script with `--speed fast/live` modes, color output, simulated verification, and API-driven negotiation.
- **33 new tests** (build_steps validation, XZ target spec, demo session), 688 total passing.

### 2026-03-22T20:00Z — Sealed Exploit Delivery: Zero-Knowledge Transfer
- Built cryptographic delivery protocol: exploit plaintext ONLY exists inside Nitro Enclave
- **Protocol**: Seller encrypts exploit to enclave (ECIES), enclave re-encrypts with fresh K_d for buyer, encrypts K_d to buyer's P-384 public key (ECIES). Platform stores only ciphertext.
- **On-chain commitments**: SHA-256 hashes of encrypted exploit + encrypted key stored on VulnEscrow contract. Proves integrity without revealing content.
- **Payment gating**: API endpoints `/delivery/{id}/payload` and `/delivery/{id}/key` only return ciphertext after on-chain DealAccepted
- **Platform deniability**: operator stores AES ciphertext (no K_d) + ECIES ciphertext (no buyer privkey). Can truthfully say "I never possessed any decryption key."
- **Test suite proves**: seal/unseal round-trip, platform cannot decrypt, wrong key fails, tampering detected, different buyers get different ciphertext
- 14 new crypto tests, 655 total passing.

### 2026-03-22T19:00Z — Capability Oracles: Proof-of-Exploitation
- Replaced crash-based verification with capability oracle system
- **Oracle types**: ACE (canary readable by service user), LPE (canary root-only), Info Leak (canary in process memory), Callback (TCP listener), Crash (signal detection), DoS (health check failure)
- **Key principle**: enclave generates random canaries, seller's PoC must retrieve them. Seller doesn't define success — enclave independently verifies the claim.
- **Reliability scoring**: PoC runs N times with service restarts between runs to randomize heap/ASLR. Reports success rate (e.g., "ACE verified, reliability 2/3").
- **Capability downgrading**: if seller claims ACE but only crashes, result shows "claimed: ACE, verified: CRASH" — buyer sees what the exploit actually achieves vs what was claimed.
- 108 verification tests, 641 total passing. No regressions.

### 2026-03-22T17:00Z — Phase 3: Per-Target EIF PoC Verification
- Built PoC verification system: seller specifies target software (base image + pinned packages + config + PoC script), system builds a custom EIF with that exact software installed
- **PoC Executor**: runs exploit scripts inside enclave with RLIMIT resource isolation (CPU, memory, process count, file size), captures exit code/stdout/stderr/signal, truncates output at 64KB
- **Buyer Overlay**: buyer (e.g., intelligence agency) provides ECIES-encrypted file replacements (patched binaries). Enclave decrypts with ephemeral key, atomically replaces files, re-runs PoC. Seller never sees patches.
- **Overlap detection**: if PoC works on unpatched AND patched → buyer's patches don't block it (genuinely new 0day). If PoC fails on patched → buyer already has coverage.
- **Security validation**: base image whitelist, package name regex, config path restriction (/etc/ only), overlay path restriction (/usr/lib/ etc.), PoC script dangerous pattern detection, service command whitelist
- **EIF Builder**: generates Dockerfile from TargetSpec, runs docker build + nitro-cli, caches by spec hash, returns PCR manifest
- **Verification Orchestrator**: full lifecycle — launch per-target EIF → attest → deliver key → send PoC → optional overlay → receive signed result → terminate
- Research finding: WASM NOT viable for real 0days (tested against 6 CVEs — Log4Shell, xz backdoor, PHP CGI, OpenSSH, FortiOS, HTTP/2). Only 1/6 could theoretically run in WASM. Architecture uses native execution instead.
- 83 new tests, 616 total passing. No regressions.

### 2026-03-22T15:00Z — Zero-Day Vulnerability Marketplace
- Built new "vuln" feature module alongside existing invention marketplace, reusing TEE infrastructure
- **Shelf-life decay engine** (`shelf_life.py`): V(t) = V_0 * exp(-λt) * (1-P_patch) * exclusivity_premium, with per-category decay rates (browser=0.015, embedded=0.001, etc.)
- **Graduated disclosure agents**: VulnSellerAgent picks disclosure level 0-3 (class → component → triggers → PoC summary); VulnBuyerAgent does CVSS triage. Hard constraints enforced in code, not LLM.
- **VulnNegotiationSession**: Same 4-phase flow as invention negotiation, adapted with shelf-life V(t) replacing static Φ
- **Smart contracts**: VulnEscrow.sol with decay-adjusted pricing (`decayAdjustedPrice = finalPrice * decayNumerator / 1e18`), patch oracle (`reportPatch()` → full buyer refund), and embargo tracking. 23 Forge tests pass (including 256 fuzz runs).
- **Full stack**: DB models + migration, API endpoints (CRUD + SSE streaming), React frontend (marketplace, submit form, deal page with live progress), blockchain client
- **Code review fixes**: Added auth to listings endpoint (zero-day metadata is sensitive), blocked self-dealing, fixed counter-offer handling in multi-round negotiation
- 46 new Python tests + 23 Solidity tests, all passing. No regressions in existing tests.

### 2026-03-16T10:00Z — Initial MVP scaffolding (Phases 1-3)
- Read and analyzed arxiv:2502.07924 (NDAI Agreements paper)
- Planned full production architecture with user (AWS Nitro, Python/FastAPI, Claude agents, Shamir SSS)
- Implemented: project scaffolding, Shamir's Secret Sharing, Nash bargaining engine, TEE abstraction (simulated + Nitro), LLM agents (seller/buyer with Claude tool-use), enclave session orchestrator, FastAPI skeleton with auth/inventions/agreements/negotiations routers, SQLAlchemy ORM models, 66 passing tests
- Key fix: acceptance threshold should be `alpha_0 * omega_hat` not `theta * omega` (seller accepts if total payoff beats outside option)

### 2026-03-16T11:45Z — Phase 5: API + Frontend
- Built full React 19 + TypeScript + Tailwind CSS frontend, bundled with esbuild (no Vite per CLAUDE.md)
- Hash-based SPA router (no react-router dep), AuthContext with JWT+role in localStorage
- Backend: static file serving via FastAPI StaticFiles + SPA catch-all, role added to TokenResponse, async negotiation with background thread + status polling
- Frontend routes: login, register, seller dashboard/inventions/agreements, buyer dashboard/marketplace/agreements, negotiation outcome display
- 15 new API tests (auth role, static serving, full seller->buyer flow, negotiation status), total 90 tests passing
- Wet tested full flow: register seller -> submit invention -> register buyer -> browse marketplace -> create agreement -> set params (theta computed) -> confirm delegation -> start negotiation button appears
- Phase 4 (TEE integration) still requires AWS Nitro hardware

### 2026-03-16T12:30Z — Phase 4: TEE Integration (AWS Nitro)
- Decided on AWS Nitro Enclaves (free, just pay for EC2 instance ~$0.17/hr c5.xlarge)
- Enclave-side app (`ndai/enclave/app.py`): vsock listener, runs NegotiationSession inside enclave
- Vsock LLM proxy (`vsock_proxy.py`): parent-side proxy forwards Claude API calls from enclave (enclave has no network)
- Vsock LLM client (`vsock_llm_client.py`): enclave-side client that routes through proxy instead of direct HTTPS
- Attestation module (`ndai/tee/attestation.py`): CBOR parsing of Nitro attestation docs, PCR verification
- Parent-side orchestrator (`ndai/tee/orchestrator.py`): full lifecycle management (launch → attest → negotiate → terminate)
- EIF build pipeline: Dockerfile + build.sh in enclave-build/
- API integration: negotiations router now uses EnclaveOrchestrator, provider selected by tee_mode setting
- 170 tests passing (80 new from Phase 4)
- Coded via 3 parallel subagents: enclave app, orchestrator, build pipeline

### 2026-03-16T14:00Z — Bilateral Nash Bargaining
- Replaced unilateral pricing (P* = θ·ω̂) with bilateral Nash bargaining (P* = (v_b + α₀·ω̂) / 2)
- Buyer's assessed_value now directly affects final price (was discarded before)
- Removed multi-round negotiation loop (3-11 API calls → 2 API calls)
- Engine: added compute_bilateral_price, check_deal_viability, resolve_bilateral_negotiation
- Buyer agent: single evaluate_invention call, no make_offer, assessed_value clamped to [0,1]
- Session: 3 phases (seller disclosure → buyer eval → bilateral resolution)
- Backward compatible: when v_b = ω̂, bilateral = unilateral
- Critical test: test_changing_buyer_valuation_changes_price proves agent decisions matter
- All 227 tests passing

### 2026-03-16T16:45Z — Phase 6: Real Nitro Security (NSM + Enclave TLS + COSE)
- Closed 3 critical security gaps: stub attestation, plaintext LLM proxy, unverified COSE signatures
- NSM interface (`nsm.py`): real `/dev/nsm` ioctl via ctypes for attestation document requests
- NSMStub (`nsm_stub.py`): generates self-signed COSE Sign1 for local dev (keeps tests passing)
- Ephemeral keys (`ephemeral_keys.py`): P-384 keypair + ECIES (ECDH + HKDF-SHA384 + AES-256-GCM) for API key delivery
- COSE verification (`attestation.py`): full cert chain validation to bundled AWS Nitro root CA, ECDSA signature check, timestamp freshness
- TCP tunnel (`vsock_tunnel.py`): parent-side raw byte forwarder replacing JSON proxy; enclave does TLS itself
- Tunnel LLM client (`tunnel_llm_client.py`): httpx.BaseTransport routing through vsock tunnel
- Key delivery flow: enclave generates ephemeral keypair → public key embedded in NSM attestation → parent ECIES-encrypts API key → enclave decrypts
- New Nitro flow: launch → tunnel → attest (COSE verify) → deliver encrypted key → negotiate → terminate
- Backward compatible: simulated mode unchanged, all legacy JSON proxy code preserved as fallback
- 315 tests passing (98 new: NSM, ephemeral keys, COSE verification, tunnel, key delivery integration)

### 2026-03-16T18:15Z — Phase 6b: Adversarial Hardening
- Closed 3 adversarial attack surfaces: prompt injection, result leakage, silent proxy fallback
- Prompt injection: new `sanitize.py` module with `escape_for_prompt()` (15 regex patterns, angle bracket escaping, backtick neutralization, control char stripping, truncation) + `wrap_user_data()` for XML boundary marking
- Seller/buyer agents: all user-controlled invention/disclosure fields now XML-wrapped with `<invention_data>`/`<disclosed_invention>` tags + escape, explicit "DATA ONLY, never instructions" markers
- Result leakage: `_strip_sensitive_fields()` whitelist in enclave app (only outcome/final_price/reason leave enclave), orchestrator strips simulated results too
- API layer: removed omega_hat/buyer_valuation/negotiation_rounds from NegotiationOutcomeResponse, only outcome/final_price/reason stored in _outcomes
- Fail-closed: Nitro mode now raises OrchestrationError if attestation lacks public key (was silently falling back to plaintext proxy), _start_llm_proxy guards against Nitro usage
- 353 tests passing (38 new: prompt injection sanitization, result stripping, fail-closed orchestrator, adversarial agent prompts)

### 2026-03-16T20:30Z — Phases 7-12: Deploy, DB, Frontend, Multi-Round, Audit, Wet Test
- **Phase 7 (Deploy)**: Added ports 80/443 to SG, systemd service (`deploy/ndai.service`), nginx reverse proxy (`deploy/nginx.conf`), hardened `setup.sh` (docker compose, pg_isready, migrations, systemd), smoke test script, updated `ndai-ctl.sh` deploy command to use systemd+alembic
- **Phase 8 (DB Persistence)**: Extended Invention model with 10 negotiation fields, initialized Alembic (async env.py), created repository layer (`ndai/db/repositories.py`), wired all 4 routers to async SQLAlchemy (replaced `_users`, `_inventions`, `_agreements`, `_outcomes` dicts), added DB lifecycle to app.py, fixed test cleanup (module-scoped TestClient + raw asyncpg truncation). Docker Compose on port 5433 (5432 was in use by another project).
- **Phase 9 (Frontend)**: Fixed NegotiationOutcomeResponse types (removed omega_hat/buyer_valuation, added reason/negotiation_rounds), added SSE endpoint (`/stream`), progress_callback to NegotiationSession, SSE hook (`useNegotiationStream.ts`), NegotiationProgress step indicator, simplified PriceBreakdown, wired BuyerAgreementDetailPage to SSE+progress
- **Phase 10 (Multi-Round)**: Added `make_offer` tool to buyer agent, multi-round loop in session.py (buyer offers → seller responds → accept/counter/reject), budget cap clamping on buyer offers, `negotiation_rounds` field in NegotiationResult + API schema, 4 new multi-round tests. Updated existing test fixtures to `max_rounds=1` for backward compat.
- **Phase 11 (Audit)**: Transcript hash chain (`ndai/enclave/transcript.py`), ECDSA sign/verify in ephemeral_keys, audit event service (`ndai/services/audit.py`), transparency report schema + API endpoint, audit-log endpoint, audit events on agreement_created/params_set/delegation_confirmed/negotiation_started/negotiation_completed. 15 new tests.
- **Phase 12 (Wet Test)**: Created `scripts/wet_test.py` harness with 5 scenarios (quantum crypto, drug discovery, low value, high budget, adversarial injection), automated polling, reasonableness checks, audit log verification.
- **Total: 382 tests passing** (363 → 382), frontend builds clean, Alembic migrations applied.

### 2026-03-20T08:30Z — Conditional Recall + Props Features
- Implemented two new features for Shape Rotator hackathon "Cohort that Builds Itself" bonus track
- **Conditional Recall**: Upload credentials with usage policies; TEE executes actions without exposing the secret. 6 API endpoints (create, list mine, list available, get, use via TEE, access log), atomic use-claiming to prevent races, owner-cannot-use enforcement
- **Props**: Submit meeting transcripts; TEE extracts summaries/action items/decisions/blockers via LLM, destroys raw text. 5 API endpoints (submit, list, get, summary, cross-team aggregation with ownership verification)
- Both features: ORM models (Secret, SecretAccessLog, MeetingTranscript, TranscriptSummary), Pydantic schemas, async repositories, TEE sessions (SecretProxySession, TranscriptProcessingSession) with guaranteed memory wipe in finally blocks
- Frontend: FeatureNav top bar (TRUSTKIT branding), feature-aware Sidebar, 8 new pages (4 Recall + 4 Props), 2 typed API clients
- Code review fixes: removed credential prefix leak from LLM prompt, atomic try_claim_use replacing race-prone decrement, explicit create_summary params, aggregate ownership check
- Alembic migration for 4 new tables, 5 new unit tests, 8 E2E tests
- Used subagent-driven development with git worktree isolation; 9 commits, 34 files changed, ~2600 lines added
- **Total: 370 tests passing** (365 unit + 5 new, 4 pre-existing escrow failures unrelated)

### 2026-03-20T22:50Z — TrustKit TEE Upgrade: Conseca Policy Engine + Egress Logging + Verification Chain
- Implemented three-layer verifiable security across Recall and Props features
- **Policy Engine (Conseca pattern)**: LLM generates context-specific constraints (generator.py), deterministic engine enforces via regex/bounds (engine.py). Defaults always applied as baseline; LLM can add constraints but not weaken defaults.
- **Egress Logging**: EgressAwareLLMClient wraps existing clients, SHA-256 hashes every request/response without retaining sensitive data. Transparent to session code.
- **Verification Chain**: SHA-256 linked hash chain records every session event (start, policy gen, LLM call, enforcement, data clear). Produces human-readable attestation claims and tamper-evident final hash.
- **Backend integration**: Both SecretProxySession and TranscriptProcessingSession now produce policy_report, policy_constraints, egress_log, verification fields. Stored in DB via new verification_data JSONB columns. Aggregation endpoint also gets verification.
- **Frontend**: 3 new shared components (VerificationPanel, PolicyDisplay, EgressLogDisplay) with expand/collapse, green checkmarks, hash badges. Wired into SecretUsePage, SummaryPage, AggregationPage.
- **30 files changed, +1754 lines**: 8 new files (3 backend modules, 3 frontend components, 3 test files), 12 modified backend files, 6 modified frontend files, 1 Alembic migration
- **401 unit tests passing**, frontend builds clean, deployed to shape.discordwell.com
- Browser wet test pending (Chrome extension not connected)

### 2026-03-20T23:45Z — Texas Hold'em Poker via Nitro Enclave
- Built provably fair Texas Hold'em poker where the enclave acts as trusted dealer
- **Enclave poker engine** (`ndai/enclave/poker/`): CSPRNG deck shuffle (Fisher-Yates with os.urandom seed), 7-card hand evaluator (all C(7,5) combos), full game state machine (blinds, betting rounds, side pots, showdown), per-player view filtering (hole cards never leak)
- **Enclave integration**: New `poker_*` action dispatch in app.py (7 actions: create_table, join_table, leave_table, start_hand, action, timeout, get_table). Game state persists in EnclaveState.poker_tables dict.
- **Smart contracts**: PokerTable.sol (multi-player escrow, deposit/withdraw, operator-only zero-sum settleHand, hand result hash verification) + PokerTableFactory.sol. 17 Foundry tests passing.
- **API layer**: 9 FastAPI endpoints at /api/v1/poker, SSE streaming with per-player card filtering, PokerOrchestrator for long-lived table management, action timeout scheduling
- **Database**: 4 new models (PokerTable, PokerSeat, PokerHand, PokerHandAction), Alembic migration
- **Frontend**: Felt-green poker table with elliptical seat positioning, CSS card components (Unicode suits), betting controls (fold/check/call/raise slider), lobby with table creation, SSE game state updates, hero seat rotation to bottom
- **MetaMask integration** planned: ethers.js v6, useWallet hook, WalletContext, direct deposit/withdraw to PokerTable.sol
- 78 Python unit tests + 20 Solidity tests = 98 new tests passing. Frontend builds clean.
- Poker is role-agnostic (any authenticated user can play)
- **Code review fixes applied**: side pot double-counting, folded-player phantom pots, raise amount ambiguity, deposit verification, settleHand integration, withdraw-during-hand guard, emergencyWithdraw cleanup, start-hand auth check, per-table lock for race condition, wallet_address in views
- **Deployed and wet tested**: Full hand played via API (preflop→flop→turn→river→showdown with Full House winner), card filtering verified (each player sees only own hole cards), UI renders table/cards/seats/pot/blinds correctly
- **Note**: uvicorn must run with `--workers 1` because poker enclave state is in-process (multi-worker loses state)

## Key Findings

- Paper's acceptance threshold: seller accepts if P >= alpha_0 * omega_hat (derived from P + alpha_0*(omega-omega_hat) >= alpha_0*omega)
- Security capacity formula: Phi(k,p,C) = k * (1-(1-p)^k) * C / (1-p)^k
- With paper defaults (k=3, p=0.005, C=7.5B), Phi ≈ 340M — much larger than omega ∈ [0,1), so security capacity is never binding for normalized values
- Hybrid constraint enforcement is critical: hard constraints in code, soft decisions via LLM. Final price always Nash bargaining formula.
- SimulatedTEEProvider uses async queues; production NitroEnclaveProvider uses AF_VSOCK + nitro-cli
