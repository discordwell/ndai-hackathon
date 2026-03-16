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

## Key Findings

- Paper's acceptance threshold: seller accepts if P >= alpha_0 * omega_hat (derived from P + alpha_0*(omega-omega_hat) >= alpha_0*omega)
- Security capacity formula: Phi(k,p,C) = k * (1-(1-p)^k) * C / (1-p)^k
- With paper defaults (k=3, p=0.005, C=7.5B), Phi ≈ 340M — much larger than omega ∈ [0,1), so security capacity is never binding for normalized values
- Hybrid constraint enforcement is critical: hard constraints in code, soft decisions via LLM. Final price always Nash bargaining formula.
- SimulatedTEEProvider uses async queues; production NitroEnclaveProvider uses AF_VSOCK + nitro-cli
