# Claudepad - NDAI Session Memory

## Session Summaries

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

## Key Findings

- Paper's acceptance threshold: seller accepts if P >= alpha_0 * omega_hat (derived from P + alpha_0*(omega-omega_hat) >= alpha_0*omega)
- Security capacity formula: Phi(k,p,C) = k * (1-(1-p)^k) * C / (1-p)^k
- With paper defaults (k=3, p=0.005, C=7.5B), Phi ≈ 340M — much larger than omega ∈ [0,1), so security capacity is never binding for normalized values
- Hybrid constraint enforcement is critical: hard constraints in code, soft decisions via LLM. Final price always Nash bargaining formula.
- SimulatedTEEProvider uses async queues; production NitroEnclaveProvider uses AF_VSOCK + nitro-cli
