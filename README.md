# NDAI / TrustKit

An implementation of [NDAI Agreements](https://arxiv.org/abs/2502.07924) (Stephenson, Miller, Sun, Annem, Parikh): using Trusted Execution Environments and AI agents as an "ironclad NDA" to resolve Arrow's disclosure paradox — an inventor must reveal an innovation to sell it, but revealing it risks expropriation.

Two Claude agents (one acting for the seller, one for the buyer) negotiate over an invention **inside a hardware enclave**. The invention plaintext, the agents' reasoning, and the bargaining math never leave the TEE; the outside world sees only the attested outcome: deal or no deal, and the price.

TrustKit is the generalized platform that grew out of the paper implementation — a TEE-agnostic toolkit (AWS Nitro Enclaves, Intel TDX via dstack, or a simulated dev backend) plus a set of applications that all exploit the same primitive: *code you can prove ran, over data nobody could see*.

## What's in the box

| Application | What it does | Key code |
|---|---|---|
| **NDAI Negotiation** | Seller/buyer Claude agents + Nash bargaining engine inside the enclave; Shamir-split invention keys; on-chain escrow settlement | `ndai/enclave/agents/`, `ndai/enclave/negotiation/` |
| **Sealed 0day verification** | Researchers submit exploit PoCs ECIES-encrypted to the enclave's attested key. The platform operator never sees plaintext: the enclave builds the target, plants canary oracles, runs the PoC, and publishes only pass/fail + capability. Verified listings get on-chain commitment hashes and sealed re-encryption to the buyer's key on purchase | `ndai/enclave/vuln_verify/`, `ndai/api/routers/proposals.py`, `ndai-seal/` |
| **TEE Poker** | Texas Hold'em with the enclave as provably fair dealer — deck and hole cards exist only in enclave memory; per-player SSE view filtering; zero-sum settlement on-chain | `ndai/enclave/poker/`, `contracts/src/PokerTable.sol` |
| **Conditional Recall** | Secrets held by the enclave and released only through a credential proxy when disclosed conditions are met | `ndai/enclave/sessions/secret_proxy.py` |
| **Props** | Meeting transcripts summarized inside the TEE so the raw transcript never reaches the operator | `ndai/enclave/sessions/transcript_processor.py` |

Supporting cast: encrypted messaging (X3DH-style one-time prekeys), bounties/RFPs, ZK-auth marketplace identities, and a React 19 frontend served by FastAPI.

## Architecture (short version)

```
Frontend (React) → FastAPI → Parent EC2 instance → Nitro Enclave
                   │            │  vsock 5000: commands (length-prefixed JSON)
                   │            │  vsock 5002: raw TCP tunnel — enclave does TLS itself
                   │            │  vsock 5003: CDP bridge to Chrome (browser tools)
                   │            └─ Base/Ethereum Sepolia (escrow + registries)
                   └─ PostgreSQL / Redis (untrusted persistence)
```

**Trust boundary.** Inside the enclave: AI agents, negotiation engine, invention/PoC plaintext, Shamir reconstruction, deck shuffles. Outside (untrusted): API, database, frontend, the parent instance itself.

**Key security mechanisms** (details and threat table in [ARCHITECTURE.md](ARCHITECTURE.md)):

- COSE Sign1 attestation verified to the AWS Nitro root CA, with nonce freshness and PCR matching (`ndai/tee/attestation.py`)
- API keys delivered by ECIES (P-384 ECDH + HKDF-SHA384 + AES-256-GCM) to the enclave's attestation-bound ephemeral public key — the parent never holds usable credentials
- In Nitro mode the enclave performs TLS directly through a byte-forwarding tunnel; the parent sees ciphertext only, with an egress whitelist of the LLM API hosts
- Result stripping: only whitelisted fields (outcome, price, reason) leave the enclave
- Fail-closed orchestration: missing attestation pubkey aborts rather than falling back to plaintext proxying

**TEE backends** are pluggable via `TEE_MODE`:

| Mode | Hardware | Use |
|---|---|---|
| `nitro` | AWS Nitro Enclaves | Production; real `/dev/nsm` attestation |
| `dstack` | Intel TDX confidential VMs | Production alternative; dstack KMS keys |
| `simulated` | none | Local dev/tests; self-signed attestation stubs |

## Quickstart (local dev)

Requires Python 3.11+, Node 22+, and Docker.

```bash
# Infra: PostgreSQL 16 + Redis 7
make infra

# Python package + dev tools
make dev                      # pip install -e ".[dev]"

# Configuration
cp .env.example .env          # then set ANTHROPIC_API_KEY etc.

# Database schema
make migrate                  # alembic upgrade head

# Frontend (FastAPI serves frontend/dist/)
make frontend-install frontend-build

# API on :8000
make run
```

`TEE_MODE=simulated` is the default — negotiations run in-process with stub attestation, no enclave hardware needed.

## Tests

```bash
pytest tests/unit/ -q          # 798 tests
pytest tests/e2e/ -q           # needs DATABASE_URL pointing at a running Postgres
pytest tests/integration/ -q   # simulated-TEE orchestration flows
make lint                      # ruff + mypy
```

CI (`.github/workflows/deploy.yml`) runs unit + e2e against Postgres 16 on every push to `main`.

## ndai-seal CLI

A pip-installable tool for exploit sellers — verify you're talking to the real enclave before anything sensitive leaves your machine:

```bash
pip install -e ndai-seal/

ndai-seal attest https://api.example.com      # fetch + verify attestation, save enclave pubkey
ndai-seal verify-pcr0 --pcr0 <hex>            # check PCR0 against the on-chain registry
ndai-seal encrypt --poc exploit.sh            # ECIES-encrypt PoC to the enclave key
```

To submit the sealed ciphertext to the marketplace (auth, target selection, polling for the verification result), use `scripts/ndai_submit.py` — run it with no arguments for an interactive walkthrough, or see [docs/SUBMIT_GUIDE.md](docs/SUBMIT_GUIDE.md).

## Smart contracts

Foundry project in `contracts/` (Base Sepolia / Ethereum Sepolia):

- `NdaiEscrow` / `NdaiEscrowFactory` — per-deal escrow with price constraints and attestation checks
- `PCR0Registry` — on-chain registry of audited enclave image measurements + build specs
- `PokerTable` / `PokerTableFactory` — deposits, zero-sum hand settlement, withdrawal
- `VerificationDeposit` — anti-spam stake for verification proposals
- `VulnEscrow`, `VulnAuction`, `BundleRegistry`, `SeriousCustomer` — marketplace settlement primitives

## Repository layout

```
ndai/            Python package
  api/           FastAPI app, routers, schemas, auth
  enclave/       Code that runs INSIDE the TEE (agents, poker, vuln_verify, tunnels)
  tee/           Parent-side: providers, orchestrators, attestation verification
  crypto/        Shamir secret sharing (GF(p), 256-bit prime)
  blockchain/    web3.py clients for the contracts
  models/, db/   SQLAlchemy ORM + repositories (async PostgreSQL)
  services/      Audit log, verification dispatch, Windows EC2 verifier
frontend/        React 19 + TypeScript + Tailwind SPA (esbuild)
frontend-zk/     ZK marketplace frontend
contracts/       Solidity (Foundry)
ndai-seal/       Seller CLI (attest / encrypt / submit)
enclave-build/   Dockerfile → EIF build for Nitro
alembic/         DB migrations
deploy/          systemd, nginx, compose, smoke tests
demo/, scripts/  Seed data, wet tests, CVE-2024-3094 (xz) verification demo
tests/           unit / integration / e2e
```

## Status & caveats

This is hackathon/research code built to demonstrate the NDAI mechanism end to end — it has real attestation, real ECIES key delivery, and a real on-chain trail, but it has not been audited. The vulnerability-verification pipeline exists to demonstrate *sealed* verification on authorized targets (the bundled demo replays CVE-2024-3094, the xz backdoor, against a purpose-built container). Browser-tool evaluation runs Chrome on the parent instance and carries weaker guarantees than enclave-direct artifact upload — see the note in ARCHITECTURE.md.

## License

MIT
