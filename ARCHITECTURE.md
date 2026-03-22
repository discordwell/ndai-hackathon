# NDAI Architecture

Implementation of [arxiv:2502.07924](https://arxiv.org/abs/2502.07924) — "NDAI Agreements" by Stephenson, Miller, Sun, Annem, Parikh.

## Problem

Arrow's disclosure paradox: inventors must reveal innovations to secure funding, but disclosure risks expropriation. NDAI solves this using TEEs + AI agents as an "ironclad NDA."

## System Overview

```
Frontend (React) → FastAPI Backend → Parent EC2 Instance → Nitro Enclave
                                     ├── Base Sepolia (NdaiEscrow)
                                     ├── neko-chrome (CDP)
                                     └── Nitro Enclave
                                         ├── Seller Agent (Claude)
                                         ├── Buyer Agent (Claude)
                                         ├── Nash Bargaining Engine
                                         └── Crypto (Shamir SSS)
```

### Trust Boundary

**Inside enclave** (secure): AI agents, negotiation engine, invention plaintext, Shamir reconstruction.
**Outside enclave** (untrusted): API, database, frontend, enclave orchestrator.

### TEE Backend Portability

TrustKit is TEE-agnostic via a provider abstraction (`ndai/tee/provider.py`). All application logic — poker engine, negotiation agents, credential proxy — runs unchanged on any backend:

| Backend | Hardware | Attestation | Config |
|---------|----------|-------------|--------|
| **Nitro** | AWS Nitro Enclaves | COSE Sign1 via `/dev/nsm` | `TEE_MODE=nitro` |
| **dstack** | Intel TDX (Confidential VMs) | TDX quotes via dstack SDK | `TEE_MODE=dstack` |
| **Simulated** | None (dev mode) | Self-signed stubs | `TEE_MODE=simulated` |

In Nitro mode, the enclave performs TLS directly through a TCP tunnel — the parent only sees encrypted ciphertext. The API key is delivered via ECIES encryption to the enclave's attestation-bound ephemeral public key. In dstack mode, the entire container runs inside hardware-encrypted memory (Intel TDX), with keys derived from the dstack KMS. In simulated mode, the parent proxies Claude API calls via vsock (parent sees plaintext; no security guarantees).

## Core Mechanism

1. **Security capacity**: `Φ(k,p,C) = k·(1-(1-p)^k)·C/(1-p)^k` — max securable value given TEE parameters
2. **Disclosure**: `ω̂ = min(ω, Φ)` — seller reveals up to security capacity
3. **Bilateral Nash bargaining**: `P* = (v_b + α₀·ω̂) / 2` where `v_b` = buyer's independent assessment
4. **Deal viability**: `v_b ≥ α₀·ω̂` (non-negative surplus required)
5. **Budget cap**: Buyer's `P̄` prevents overpayment

When `v_b = ω̂`, this reduces to the paper's original formula `P* = θ·ω̂` where `θ = (1+α₀)/2` (backward compatible). The unilateral formula is still computed as an audit baseline.

### Hybrid Constraint Enforcement

**Hard constraints** (code-enforced): disclosure ceiling, budget cap, deal viability, assessed_value clamp [0,1], session deletion.
**Soft decisions** (LLM-delegated): disclosure framing, buyer value assessment.

Both agents' decisions affect the final price. The seller controls `ω̂` (disclosure), the buyer controls `v_b` (assessment). The math combines them deterministically.

## Key Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Negotiation Engine | `ndai/enclave/negotiation/engine.py` | Nash bargaining math, Φ, θ, P*, constraint checks |
| Seller Agent | `ndai/enclave/agents/seller_agent.py` | Claude tool-use for disclosure and offer evaluation |
| Buyer Agent | `ndai/enclave/agents/buyer_agent.py` | Claude tool-use for invention evaluation and pricing |
| Prompt Sanitizer | `ndai/enclave/agents/sanitize.py` | Injection-safe escaping + XML boundary wrapping for user data in prompts |
| Session Orchestrator | `ndai/enclave/session.py` | Wires agents + engine into complete negotiation lifecycle |
| Shamir SSS | `ndai/crypto/shamir.py` | (k,n)-threshold secret sharing over GF(p), 256-bit prime |
| TEE Provider | `ndai/tee/provider.py` | Abstract TEE interface (Nitro + Simulated backends) |
| NSM Interface | `ndai/enclave/nsm.py` | Real `/dev/nsm` ioctl for attestation documents |
| NSM Stub | `ndai/enclave/nsm_stub.py` | Self-signed COSE Sign1 for local development |
| Ephemeral Keys | `ndai/enclave/ephemeral_keys.py` | P-384 keypair + ECIES encryption for key delivery |
| Attestation | `ndai/tee/attestation.py` | COSE Sign1 verification, cert chain, PCR + nonce checks |
| TCP Tunnel | `ndai/enclave/vsock_tunnel.py` | Parent-side raw byte forwarder (enclave does TLS) |
| Tunnel LLM Client | `ndai/enclave/tunnel_llm_client.py` | Enclave-side httpx transport through tunnel |
| Nitro Root Cert | `ndai/tee/nitro_root_cert.py` | Bundled AWS Nitro Attestation PKI root CA |
| FastAPI Backend | `ndai/api/` | REST API for inventions, agreements, negotiations |
| Frontend | `frontend/` | React 19 + TypeScript + Tailwind, esbuild-bundled SPA |
| ORM Models | `ndai/models/` | SQLAlchemy models for users, inventions, agreements, payments, audit |
| Repository Layer | `ndai/db/repositories.py` | Async CRUD functions for all models |
| Alembic Migrations | `alembic/` | Database schema versioning (async PostgreSQL) |
| Transcript Chain | `ndai/enclave/transcript.py` | SHA-256 hash chain for tamper-evident transcripts |
| Audit Service | `ndai/services/audit.py` | Event logging for agreement lifecycle |
| Transparency API | `ndai/api/schemas/transparency.py` | Verifiable transparency report schema |
| Deploy Scripts | `deploy/` | Systemd, nginx, Docker Compose, smoke test |
| Wet Test Harness | `scripts/wet_test.py` | Automated real-LLM negotiation testing |
| Escrow Contract | `contracts/src/NdaiEscrow.sol` | On-chain escrow with price constraints, attestation verification, expiry |
| Escrow Factory | `contracts/src/NdaiEscrowFactory.sol` | Deploys per-deal escrow contracts, maintains registry |
| Escrow Client | `ndai/blockchain/escrow_client.py` | Python web3.py wrapper for escrow contract interaction |
| CDP Tunnel | `ndai/enclave/cdp_tunnel.py` | Parent-side vsock↔WebSocket bridge to Chrome |
| CDP Client | `ndai/enclave/tunnel_cdp_client.py` | Enclave-side lightweight CDP client over websockets |
| Browser Tools | `ndai/enclave/agents/browser_tools.py` | Agent tool definitions for browser automation |

## Data Flow

```
Seller submits invention (encrypted client-side)
    → Buyer expresses interest, sets budget cap
    → Both confirm delegation to TEE
    → Enclave launches, attestation verified
    → Inputs encrypted to enclave's ephemeral key
    → [Inside enclave]:
        → Decrypt inputs, compute Φ
        → Seller agent decides ω̂ via Claude (1 API call)
        → Buyer agent evaluates v_b via Claude (1 API call)
        → Bilateral Nash resolution: P* = (v_b + α₀·ω̂) / 2
    → Agreement: invention key + payment released
        → Orchestrator submits outcome on-chain via Base Sepolia (NdaiEscrow)
    → No deal: all data destroyed, enclave terminated
```

## Security Model

- **Shamir SSS**: Invention encryption key split into n shares (k-of-n threshold)
- **NSM Attestation**: Real `/dev/nsm` ioctl produces COSE Sign1 attestation documents, verified against AWS Nitro root CA with full certificate chain validation, nonce freshness, and PCR matching
- **Encrypted API Key Delivery**: Enclave generates ephemeral P-384 keypair on startup; public key embedded in attestation document; parent encrypts API key via ECIES (ECDH + HKDF-SHA384 + AES-256-GCM) to enclave's public key; enclave decrypts with private key — parent never has the key in enclave-readable form
- **Enclave TLS (TCP Tunnel)**: In Nitro mode, LLM API traffic is routed through a raw byte TCP tunnel (vsock port 5002); the enclave performs TLS handshake directly with api.openai.com / api.anthropic.com; parent sees only encrypted ciphertext. Whitelist enforced: only `api.openai.com:443` and `api.anthropic.com:443`
- **Enclave-per-negotiation**: Strong isolation, memory wiped on termination

> **Browser-evaluated artifacts:** When browser tools are used, Chrome runs on the parent EC2 instance (outside the TEE). The parent could serve fake pages or intercept CDP traffic. Browser evaluation provides convenience for interactive artifact inspection but has weaker trust guarantees than directly-uploaded artifacts encrypted to the enclave's ephemeral key. Mitigations include TLS certificate verification via CDP's Security.enable domain and content hashing into the transcript chain.

### Security Vectors Closed

| Vector | Before (Phase 5) | After (Phase 6/6b) |
|--------|-------------------|---------------------|
| Parent reads LLM traffic | All plaintext via JSON proxy | TLS ciphertext only (TCP tunnel) |
| Parent steals API key | Key in parent memory | ECIES-encrypted to enclave pubkey |
| Forged attestation | No signature check | COSE Sign1 verified to AWS root CA |
| Replay attestation | No freshness | Nonce + timestamp check |
| Modified enclave code | PCR check but no crypto sig | PCRs inside cryptographically signed attestation |
| Prompt injection via invention fields | 7-pattern uppercase blocklist | 15 case-insensitive regex patterns + XML boundary wrapping + angle bracket escaping |
| Result leakage to parent | omega_hat, payoffs, buyer_valuation sent in plaintext | Whitelist: only outcome/final_price/reason leave enclave |
| Silent proxy fallback | Attestation without pubkey silently fell back to plaintext proxy | Fail-closed: raises OrchestrationError, proxy blocked in Nitro mode |

## Tech Stack

- Python 3.11+, FastAPI, SQLAlchemy (async), PostgreSQL, Redis
- AWS Nitro Enclaves (SimulatedTEEProvider for dev)
- Claude API (Anthropic) for LLM agents
- React 19 + TypeScript + Tailwind CSS frontend (esbuild, served by FastAPI)

## TEE Deployment (AWS Nitro)

### Building the Enclave Image

The enclave image is built in two steps: Dockerfile to Docker image, then Docker image to EIF (Enclave Image Format) via `nitro-cli`.

```
enclave-build/Dockerfile  →  docker build  →  ndai-enclave:latest
                                                     ↓
                                              nitro-cli build-enclave
                                                     ↓
                                              ndai_enclave.eif + PCR values
```

Build command: `make enclave-build`

The Dockerfile uses a multi-stage build (python:3.11-slim) to minimize image size. Only the ndai package and its runtime dependencies are included — no dev tools, no shell in production.

### Instance Requirements

| Requirement | Value |
|-------------|-------|
| Instance type | c5.xlarge or larger (must be Nitro-capable) |
| nitro-cli | `sudo amazon-linux-extras install aws-nitro-enclaves-cli` |
| Allocator config | `/etc/nitro_enclaves/allocator.yaml`: set `memory_mib: 1600`, `cpu_count: 2` |
| Allocator service | `sudo systemctl enable --now nitro-enclaves-allocator` |
| Docker | Required for building EIF |

After configuring the allocator, restart it: `sudo systemctl restart nitro-enclaves-allocator`.

### vsock Communication Architecture

Nitro Enclaves have no network interface. All communication between the parent EC2 instance and the enclave uses AF_VSOCK (virtio socket), a kernel-level IPC mechanism addressed by CID (Context ID) and port.

```
Parent EC2 Instance                    Nitro Enclave (CID assigned at launch)
┌──────────────────────┐              ┌──────────────────────────────┐
│  EnclaveOrchestrator │   vsock      │  ndai.enclave.app            │
│  (ndai/tee/          │◄────────────►│  ├── NegotiationSession      │
│   orchestrator.py)   │  port 5000   │  ├── SellerAgent             │
│                      │  (commands)  │  ├── BuyerAgent              │
│  TCP Tunnel          │   vsock      │  └── NegotiationEngine       │
│  (raw byte forwarder │◄────────────►│                              │
│   to LLM APIs)       │  port 5002   │  TunnelLLMClient             │
│                      │  (TLS only)  │  (TLS inside enclave)        │
│  [LLM Proxy]         │   vsock      │  [VsockLLMClient]            │
│  (fallback mode)     │◄────────────►│  (fallback mode)             │
│                      │  port 5001   │                              │
│  CDP Tunnel          │   vsock      │  TunnelCDPClient             │
│  (vsock↔WebSocket    │◄────────────►│  (browser automation         │
│   bridge to Chrome)  │  port 5003   │   inside enclave)            │
└──────────────────────┘              └──────────────────────────────┘
```

**Nitro mode (secure)**: The TCP tunnel on port 5002 forwards raw bytes between the enclave and LLM APIs. The enclave performs TLS handshakes itself — the parent sees only encrypted ciphertext. The API key is delivered via ECIES encryption (P-384 ECDH + HKDF-SHA384 + AES-256-GCM) to the enclave's ephemeral public key, which is embedded in the NSM attestation document.

**Simulated mode (dev)**: The LLM proxy on port 5001 forwards JSON-serialized API calls. The parent sees plaintext. No security guarantees.

Messages on port 5000 use length-prefixed framing (4-byte big-endian header + JSON payload).

### PCR Values and Attestation

When `nitro-cli build-enclave` produces an EIF, it outputs PCR (Platform Configuration Register) values:

| PCR | Contents |
|-----|----------|
| PCR0 | Hash of the enclave image (EIF) |
| PCR1 | Hash of the Linux kernel and boot ramdisk |
| PCR2 | Hash of the application code |

These values are deterministic: the same Dockerfile and source code always produce the same PCRs. Before disclosing any invention data, the orchestrator requests an attestation document from the enclave (signed by the Nitro hypervisor's hardware root of trust) and verifies that PCR0/1/2 match the expected values. This proves the enclave is running the exact code that was audited.

Attestation documents are CBOR-encoded, signed by AWS Nitro, and parsed with `cbor2`. The `ndai/tee/attestation.py` module handles verification.

For development, `SimulatedTEEProvider` generates deterministic test PCRs (SHA-384 of the EIF path). These provide no security guarantees but enable local testing without Nitro hardware.

### Running in Production

1. Build the EIF: `make enclave-build` (on a Nitro-capable instance)
2. Record the PCR values from the build output
3. Configure environment:
   ```
   TEE_MODE=nitro
   ENCLAVE_EIF_PATH=ndai_enclave.eif
   ENCLAVE_CPU_COUNT=2
   ENCLAVE_MEMORY_MIB=1600
   ENCLAVE_VSOCK_PORT=5000
   ```
4. The orchestrator handles launch, attestation verification, negotiation, and teardown automatically

### Development Mode

Set `TEE_MODE=simulated` (the default) to use `SimulatedTEEProvider`. This runs negotiations in-process with no isolation, no vsock, and self-signed attestation documents. All integration tests use this mode.

## Frontend Architecture

Hash-based SPA router, no external routing library. FastAPI serves `frontend/dist/` as static files with catch-all for SPA routes.

| Layer | Files | Purpose |
|-------|-------|---------|
| API Client | `frontend/src/api/` | Typed fetch wrapper with JWT injection |
| Auth | `frontend/src/contexts/AuthContext.tsx` | JWT + role in localStorage, ProtectedRoute |
| Router | `frontend/src/routes/index.tsx` | Hash-based routing, role-based redirects |
| Layouts | `frontend/src/layouts/` | Seller/Buyer shells with sidebar nav |
| Pages | `frontend/src/pages/` | Dashboard, inventions, marketplace, agreements |
| Components | `frontend/src/components/` | Shared (Card, StatusBadge), seller (InventionForm), buyer (ListingCard), negotiation (OutcomeDisplay) |

## Poker (Texas Hold'em via TEE)

Provably fair poker where the Nitro Enclave acts as a trusted dealer. Deck, shuffle seed, and other players' hole cards never leave the enclave.

```
Browser ↔ SSE (per-player filtered) + REST → FastAPI → Enclave (poker engine)
                                                     → Base Sepolia (PokerTable.sol)
```

### Enclave Poker Engine (`ndai/enclave/poker/`)

| Module | Purpose |
|--------|---------|
| `state.py` | Dataclasses: Card, PlayerSeat, HandState, TableState, Pot |
| `deck.py` | CSPRNG shuffle (Fisher-Yates + SHA-256 PRNG from os.urandom seed) |
| `evaluator.py` | 7-card hand evaluator (best 5 of C(7,5)=21 combos) |
| `engine.py` | Game state machine: blinds, betting, side pots, showdown |
| `views.py` | Per-player view filtering (strips other players' hole cards) |
| `actions.py` | Enclave action handlers for 7 poker_* vsock actions |

### On-Chain Escrow (`contracts/src/PokerTable.sol`)

- Players deposit ETH directly via MetaMask
- Operator (TEE) settles each hand (zero-sum enforced on-chain)
- Players withdraw between hands
- Hand result hashes stored for auditability

### API (`ndai/api/routers/poker.py`)

9 endpoints at `/api/v1/poker`. SSE streaming broadcasts game events with per-player card filtering (each subscriber only sees their own hole cards). PokerOrchestrator manages long-lived tables and action timeouts.

### Security

- **Deck/cards**: Only exist in enclave memory. Attestation proves the code.
- **Shuffle fairness**: CSPRNG seed → deterministic shuffle. `sha256(seed)` published post-hand for verification.
- **Settlement**: On-chain zero-sum enforcement. Sequential hand numbering prevents replay.
- **Card filtering**: Parent receives `player_hands` dict from enclave, distributes each player's cards only to their SSE stream.

## Sealed Verification Pipeline

End-to-end 0day verification where the platform operator never sees the exploit.

### Trust Flow

```
Seller                         Platform (untrusted)              Nitro Enclave (trusted)
  │                                  │                                  │
  │ 1. Submit target spec + stake    │                                  │
  │ ─────────────────────────────>   │                                  │
  │                                  │  2. Build target, launch enclave │
  │                                  │  ─────────────────────────────>  │
  │ 3. GET /enclave/attestation      │                                  │
  │ ─────────────────────────────>   │      get_attestation(nonce)      │
  │                                  │  ─────────────────────────────>  │
  │ <── COSE Sign1 (AWS-signed) ──── │  <── attestation doc ──────────  │
  │                                  │                                  │
  │ 4. Verify:                       │                                  │
  │    - Cert chain → AWS Root CA    │                                  │
  │    - PCR0 matches on-chain value │                                  │
  │    - PCR0 matches local build    │                                  │
  │    - Nonce is fresh              │                                  │
  │    - Extract enclave P-384 key   │                                  │
  │                                  │                                  │
  │ 5. Inspect target (optional)     │                                  │
  │    - Check installed packages    │                                  │
  │    - Verify service configs      │                                  │
  │    - Confirm build spec matches  │                                  │
  │                                  │                                  │
  │ 6. Encrypt PoC to enclave key   │                                  │
  │    ECIES(enclave_pubkey, poc)    │                                  │
  │                                  │                                  │
  │ 7. SEAL & SUBMIT (go code)      │                                  │
  │    sealed_poc + SHA-256 hash     │                                  │
  │ ─────────────────────────────>   │  [store ciphertext, NOT plaintext]
  │                                  │                                  │
  │    Write access revoked ──────── │                                  │
  │                                  │  8. deliver_sealed_poc(bytes)    │
  │                                  │  ─────────────────────────────>  │
  │                                  │     [ECIES decrypt inside TEE]   │
  │                                  │     [plant oracle canaries]      │
  │                                  │     [run exploit N times]        │
  │                                  │     [check canary results]       │
  │                                  │  <── pass/fail + capability ──── │
  │                                  │                                  │
  │ 9. Result published              │                                  │
  │    (on-chain commitment hash)    │                                  │
  │                                  │                                  │
  │ BUYER FLOW:                      │                                  │
  │ 10. Buyer deposits to escrow     │                                  │
  │                                  │  11. Re-encrypt to buyer key     │
  │                                  │  ─────────────────────────────>  │
  │                                  │     seal(exploit, buyer_pubkey)  │
  │                                  │  <── delivery_ciphertext ──────  │
  │ 12. Buyer decrypts with own key  │                                  │
  │     Escrow releases to seller    │                                  │
```

### On-Chain Attestation

PCR0 (SHA-384 of enclave image) is published to `PCR0Registry.sol` on Ethereum Sepolia:
- Contract: `0x6A2Af53235dAe573c8F2AfbBa58C666fB4868222`
- Anyone can call `getPCR0()` and compare against their own local build
- Event log is permanent — operator cannot retroactively change history

### Operator Attack Surface (closed)

| Attack | Defense |
|--------|---------|
| Read PoC from database | DB stores ECIES ciphertext only |
| Modify enclave to exfiltrate | PCR0 changes → seller detects before sending |
| Read enclave memory from host | Nitro hardware physically prevents it |
| Intercept vsock traffic | PoC is ECIES-encrypted, only enclave has the key |
| Replay old attestation | Nonce + timestamp prevent replay |
| Fake the attestation | Cert chain roots to AWS hardware — can't forge |
| Swap enclave after attestation | New enclave = new key = seller must re-encrypt |
| Claim different exploit submitted | Sealed PoC hash committed on-chain at trigger time |

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Attestation API | `ndai/api/routers/enclave.py` | Exposes enclave attestation to sellers |
| ECIES Encryption | `ndai/enclave/ephemeral_keys.py` | P-384 ECDH + HKDF-SHA384 + AES-256-GCM |
| Sealed PoC Handler | `ndai/enclave/app.py` (`deliver_sealed_poc`) | Decrypts PoC inside enclave |
| Browser ECIES | `frontend-zk/src/crypto/ecies.ts` | Client-side encryption via @noble/curves |
| Sealed Delivery | `ndai/enclave/vuln_verify/sealed_delivery.py` | Re-encrypts exploit for buyer |
| PCR0 Registry | `contracts/src/PCR0Registry.sol` | On-chain enclave code attestation |
| Oracle System | `ndai/enclave/vuln_verify/oracles.py` | Capability proof via canary files |
| PoC Executor | `ndai/enclave/vuln_verify/poc_executor.py` | Sandboxed script execution with RLIMIT |

## Known Targets + Verification Proposals + Anti-Spam Escrow

Platform-maintained catalog of verification targets with anti-spam deposit escrow and reputation badges.

### Architecture

```
Seller browses Known Targets -> picks target -> writes PoC
    |
Has ⚡ badge? --yes--> Queue verification immediately
    |no
    v
Deposit ETH to escrow -> confirm tx -> Queue verification
    |
Sealed submission (see above):
  Fetch attestation -> verify PCR0 -> ECIES encrypt PoC -> submit sealed_poc
    |
Dispatcher routes by platform:
  |-- Linux (Chrome/Firefox/Ubuntu/Apache/OpenSSH) -> Nitro Enclave
  |-- XZ Backdoor (CVE-2024-3094) -> Nitro Enclave (custom EIF)
  |-- Windows -> Fresh EC2 Windows VM via SSM
  '-- iOS -> Manual review (Corellium added when demand exists)
    |
Capability oracle runs -> CapabilityResult
    |
Pass? -> Refund deposit + Award ⚡ badge + Auto-create marketplace listing
Fail? -> Forfeit deposit to platform
```

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Known Targets | `ndai/models/known_target.py` | Platform-maintained target catalog (Chrome, Firefox, Ubuntu, Windows, iOS) |
| Verification Proposals | `ndai/models/verification_proposal.py` | Seller PoC submissions against known targets |
| Target Catalog API | `ndai/api/routers/targets.py` | Browse available targets |
| Proposal API | `ndai/api/routers/proposals.py` | Submit, deposit, trigger, and stream verification |
| Badge API | `ndai/api/routers/badges.py` | Purchase or check ⚡ badge status |
| Verification Dispatcher | `ndai/services/verification_dispatcher.py` | Routes proposals to correct backend (Nitro/EC2/Corellium) |
| Nitro Verifier | `ndai/services/nitro_verifier.py` | Linux verification via pre-built EIF + capability oracles |
| Browser Executor | `ndai/enclave/vuln_verify/browser_executor.py` | Headless Chrome/Firefox PoC executor |
| Windows Verifier | `ndai/services/windows_verifier.py` | EC2 Windows VM verification via SSM |
| iOS Verifier | `ndai/services/ios_verifier.py` | Corellium stub (manual review) |
| Target Auto-Updater | `ndai/services/target_updater.py` | Cron-based version feed checker |
| VerificationDeposit.sol | `contracts/src/VerificationDeposit.sol` | On-chain escrow ($100 deposit, badge purchase) |
| Frontend | `zdayzk-frontend/src/pages/targets/`, `proposals/` | Target browsing, PoC submission, verification progress |

### Anti-Spam: VerificationDeposit.sol

Single contract (not factory) managing deposits for all proposals. Badge holders skip deposits.

- `deposit(proposalId)` -- $100 ETH escrow per verification run
- `refund(proposalId)` -- Operator refunds if PoC passes capability oracle
- `forfeit(proposalId)` -- Operator forfeits if PoC fails (funds go to platform)
- `purchaseBadge()` -- One-time $100 for permanent ⚡ badge
- `grantBadge(seller)` -- Operator awards badge after first successful verification

### Known Target Catalog

8 known targets with platform-specific verification methods:

| Target | Platform | Method | Escrow | PoC Type |
|--------|----------|--------|--------|----------|
| Apache HTTP Server | linux | Nitro Enclave | $100 | Bash |
| Chrome (Linux) | linux | Nitro Enclave | $100 | HTML |
| Firefox (Linux) | linux | Nitro Enclave | $100 | HTML |
| XZ Utils / CVE-2024-3094 | linux | Nitro Enclave | $500 | Python3 |
| OpenSSH Server | linux | Nitro Enclave | $200 | Bash |
| Ubuntu LTS | linux | Nitro Enclave | $100 | Bash |
| Windows Server 2022 | windows | EC2 VM + SSM | $100 | PowerShell |
| iOS (Latest) | ios | Manual/Corellium | $500 | Manual |

### Auto-Update

Feed checkers poll upstream release APIs every 6 hours:
- Chrome: Chromium Dashboard API
- Firefox: Mozilla product-details
- Ubuntu: Launchpad API
- Windows/iOS: Manual updates

## CVE-2024-3094 Demo (Hackathon PoC)

End-to-end demonstration of the 0day marketplace using the XZ Utils backdoor as showcase.

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Backdoor reproduction | `demo/xz_backdoor/` | Simplified faithful reproduction of CVE-2024-3094 attack pattern |
| Target spec | `demo/target_spec.py` | TargetSpec definition for enclave verification |
| Seed data | `demo/seed_data.py` | Seeds marketplace with CVE-2024-3094 metadata |
| Demo session | `ndai/enclave/vuln_demo_session.py` | Combined verify → negotiate → seal pipeline |
| Demo API | `ndai/api/routers/vuln_demo.py` | SSE-streaming demo endpoints |
| Demo frontend | `frontend/src/pages/vuln/VulnDemoPage.tsx` | Full pipeline visualization |
| Demo script | `scripts/demo_xz_backdoor.py` | Terminal-based presenter script |
| Health check | `demo/health_check.py` | Pre-demo dependency checker |

### Demo Flow

1. Seller submits CVE-2024-3094 vulnerability (CVSS 10.0, pre-auth RCE)
2. Buyer browses anonymized marketplace listing
3. Buyer proposes deal with budget cap
4. TEE builds target (debian:12 + backdoored liblzma + sshd)
5. Capability oracles verify ACE via Ed448-signed SSH payload
6. AI agents negotiate price via bilateral Nash bargaining
7. VulnEscrow deployed on Base Sepolia (90/10 split)
8. Sealed delivery: ECIES re-encryption, zero-knowledge transfer
9. Buyer downloads and decrypts exploit locally
