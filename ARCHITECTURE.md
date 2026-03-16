# NDAI Architecture

Implementation of [arxiv:2502.07924](https://arxiv.org/abs/2502.07924) — "NDAI Agreements" by Stephenson, Miller, Sun, Annem, Parikh.

## Problem

Arrow's disclosure paradox: inventors must reveal innovations to secure funding, but disclosure risks expropriation. NDAI solves this using TEEs + AI agents as an "ironclad NDA."

## System Overview

```
Frontend (React) → FastAPI Backend → Parent EC2 Instance → Nitro Enclave
                                                            ├── Seller Agent (Claude)
                                                            ├── Buyer Agent (Claude)
                                                            ├── Nash Bargaining Engine
                                                            └── Crypto (Shamir SSS)
```

### Trust Boundary

**Inside enclave** (secure): AI agents, negotiation engine, invention plaintext, Shamir reconstruction.
**Outside enclave** (untrusted): API, database, frontend, enclave orchestrator.

The parent instance proxies Claude API calls via vsock. The API key stays on the parent side and never enters the enclave. Note: the parent currently sees plaintext API traffic; enclave-side TLS termination is planned for a future phase.

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
| Session Orchestrator | `ndai/enclave/session.py` | Wires agents + engine into complete negotiation lifecycle |
| Shamir SSS | `ndai/crypto/shamir.py` | (k,n)-threshold secret sharing over GF(p), 256-bit prime |
| TEE Provider | `ndai/tee/provider.py` | Abstract TEE interface (Nitro + Simulated backends) |
| FastAPI Backend | `ndai/api/` | REST API for inventions, agreements, negotiations |
| Frontend | `frontend/` | React 19 + TypeScript + Tailwind, esbuild-bundled SPA |
| ORM Models | `ndai/models/` | SQLAlchemy models for users, inventions, agreements, payments |

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
    → No deal: all data destroyed, enclave terminated
```

## Security Model

- **Shamir SSS**: Invention encryption key split into n shares (k-of-n threshold)
- **Attestation**: PCR values verify enclave code identity before disclosure
- **vsock proxy**: Claude API calls routed through parent (parent sees plaintext; enclave-side TLS is future work)
- **Enclave-per-negotiation**: Strong isolation, memory wiped on termination

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
│  EnclaveOrchestrator │              │  ndai.enclave.app            │
│  (ndai/tee/          │   vsock      │  ├── NegotiationSession      │
│   orchestrator.py)   │◄────────────►│  ├── SellerAgent (Claude)    │
│                      │  port 5000   │  ├── BuyerAgent (Claude)     │
│  LLM Proxy           │              │  └── NegotiationEngine       │
│  (forwards Claude    │   vsock      │                              │
│   API calls)         │◄────────────►│  VsockLLMClient              │
│                      │  port 5001   │  (proxied API calls)         │
└──────────────────────┘              └──────────────────────────────┘
```

Messages are length-prefixed (4-byte big-endian header + JSON payload). The parent proxies Claude API calls: the enclave sends serialized requests over vsock, the parent forwards them to the Anthropic API over HTTPS. Note: the parent can observe API request/response content. The API key is kept parent-side and never enters the enclave. Future work: implement TLS termination inside the enclave for full confidentiality of LLM interactions.

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
