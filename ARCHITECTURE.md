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

The parent instance proxies Claude API calls via vsock. TLS terminates inside the enclave, so the parent sees only encrypted bytes.

## Core Mechanism

1. **Security capacity**: `Φ(k,p,C) = k·(1-(1-p)^k)·C/(1-p)^k` — max securable value given TEE parameters
2. **Disclosure**: `ω̂ = min(ω, Φ)` — seller reveals up to security capacity
3. **Nash bargaining**: `θ = (1+α₀)/2`, equilibrium price `P* = θ·ω̂`
4. **Acceptance**: Seller accepts if `P ≥ α₀·ω̂` (payoff beats outside option)
5. **Budget cap**: Buyer's `P̄` prevents overpayment

### Hybrid Constraint Enforcement

**Hard constraints** (code-enforced): disclosure ceiling, budget cap, acceptance threshold, session deletion.
**Soft decisions** (LLM-delegated): disclosure framing, value assessment, negotiation reasoning.

Final price is ALWAYS `P* = θ·ω̂`. LLMs evaluate; the math decides.

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
        → Seller agent decides ω̂ via Claude
        → Buyer agent evaluates via Claude
        → Multi-round negotiation
        → Deterministic Nash resolution
    → Agreement: invention key + payment released
    → No deal: all data destroyed, enclave terminated
```

## Security Model

- **Shamir SSS**: Invention encryption key split into n shares (k-of-n threshold)
- **Attestation**: PCR values verify enclave code identity before disclosure
- **vsock proxy**: Claude API calls routed through parent; TLS inside enclave
- **Enclave-per-negotiation**: Strong isolation, memory wiped on termination

## Tech Stack

- Python 3.11+, FastAPI, SQLAlchemy (async), PostgreSQL, Redis
- AWS Nitro Enclaves (SimulatedTEEProvider for dev)
- Claude API (Anthropic) for LLM agents
- React frontend (planned)
