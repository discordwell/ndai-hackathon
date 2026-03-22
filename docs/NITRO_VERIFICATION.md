# How Nitro Enclave Verification Works

This document explains exactly what happens when you submit an exploit to NDAI, and how to test the full pipeline locally before paying for AWS.

## The Problem

A seller says "I have an ACE exploit for Apache 2.4.52." How do you prove that to a buyer without revealing the exploit?

## The Solution: Capability Oracles

The enclave doesn't trust the seller's success criteria. Instead, it generates its own challenges:

```
┌─────────────────────────────────────────────────────────┐
│                    NITRO ENCLAVE                        │
│                                                         │
│  1. Build target container (Apache 2.4.52 + configs)    │
│  2. Start Apache service                                │
│  3. Plant random canary:                                │
│     /var/lib/ndai-oracle/ace_canary = "a7f3b2c1d9..."  │
│  4. Run seller's PoC script                             │
│  5. Check: did "a7f3b2c1d9..." appear in stdout?        │
│  6. Repeat N times with fresh canaries + ASLR           │
│  7. Sign result with hardware attestation               │
│                                                         │
│  Output: "ACE verified, 3/3 reliability, PCR0=abc..."   │
└─────────────────────────────────────────────────────────┘
```

The canary is a 64-character random hex string (256 bits of entropy). It's different every run. You can't fake it — your exploit must actually execute code to read the file.

## Oracle Types

| Oracle | What It Proves | How |
|---|---|---|
| **ACE** | Code execution as service user | Canary at `/var/lib/ndai-oracle/ace_canary` (0644). PoC must `cat` or read this file. |
| **LPE** | Privilege escalation to root | Canary at `/var/lib/ndai-oracle/lpe_canary` (0600, root-only). Service user can't read it — must escalate first. |
| **Info Leak** | Memory read from target process | Canary written to `/var/lib/ndai-oracle/info_canary` (0600, root-only) and loaded into target's env (`$NDAI_INFO_CANARY`). Must read from process memory, not disk. |
| **Callback** | Blind RCE (outbound connection) | TCP listener on random port. `/var/lib/ndai-oracle/callback_token` contains `host:port:token`. PoC must make the target connect back with the token. |
| **Crash** | Process termination | PoC causes target process to die with a signal (SIGSEGV, etc.) |
| **DoS** | Service disruption | Target stops responding to health checks after PoC runs |

## Verification Protocol (Step by Step)

```
Phase 1: ENVIRONMENT SETUP
├── Generate Dockerfile from target spec (base image, packages, configs)
├── docker build → per-target image
├── nitro-cli build-enclave → EIF (Enclave Image File)
├── nitro-cli run-enclave → launch isolated enclave
└── Record PCR0/1/2 (hardware measurements of exactly what's running)

Phase 2: SERVICE STARTUP
├── Start target services inside enclave
├── Health check each service (e.g., curl localhost:80)
└── Log service status

Phase 3: ORACLE VERIFICATION (repeated N times)
├── Plant fresh canary files (new random value each run)
├── Execute PoC script with resource limits:
│   ├── CPU: 60s max
│   ├── Memory: 512MB max
│   ├── Processes: 64 max
│   ├── Wall clock: 120s max
│   └── Output: 64KB capture cap
├── Check canary in PoC stdout/stderr
├── Restart services between runs (randomize ASLR)
└── Tally: successes / total = reliability score

Phase 4: ATTESTATION
├── Build verification chain hash (SHA-256 of all events)
├── Sign with Nitro NSM (hardware attestation document)
│   ├── PCR0 = hash of enclave image (proves exactly what code ran)
│   ├── PCR1 = hash of kernel
│   └── PCR2 = hash of application
├── COSE Sign1 envelope
└── Return: result + chain_hash + pcr0
```

## What PCR Values Mean

PCR (Platform Configuration Register) values are SHA-384 hashes measured by AWS Nitro hardware. They're unforgeable:

- **PCR0** — Hash of the entire Enclave Image File. If anyone modifies the verification code, PCR0 changes. This is the "code integrity" proof.
- **PCR1** — Hash of the Linux kernel inside the enclave.
- **PCR2** — Hash of the application (NDAI Python code).

A buyer can verify: "The result was produced by *this specific code* running on *real Nitro hardware*, not someone's laptop."

## The Verification Chain

Every event during verification is recorded in a hash chain:

```
session_start → services_started → poc_unpatched (run 1) →
poc_unpatched (run 2) → poc_unpatched (run 3) → result_produced
```

Each event includes a timestamp and the SHA-256 hash of the previous event. The final hash is the `verification_chain_hash` — a tamper-evident log of everything that happened.

## Buyer Overlay (Advanced)

A buyer (e.g., an intelligence agency) can provide encrypted file replacements:

1. Buyer uploads patched binaries encrypted to the enclave's public key
2. Enclave runs the PoC on the **unpatched** target first
3. Enclave applies the buyer's patches, restarts services
4. Enclave runs the PoC again on the **patched** target
5. If the exploit still works → the 0day is genuinely new to the buyer
6. If the exploit fails → the buyer already owns a fix for this vulnerability

The seller never sees the buyer's patches. The enclave never leaks either party's secrets.

---

## Testing Locally

You don't need AWS to test your exploit. The verification pipeline runs in three modes:

| Mode | Where | Isolation | Attestation | Cost |
|---|---|---|---|---|
| `simulated` | Your laptop | None (runs in-process) | Fake PCRs | Free |
| `docker` | Your laptop | Docker container | Fake PCRs | Free |
| `nitro` | EC2 c5.xlarge | AWS Nitro Enclave | Real hardware PCRs | ~$0.17/hr |

### Option 1: Simulated Mode (Fastest)

The verification protocol runs directly in your Python process. No Docker, no containers — it literally calls `subprocess.run()` with your PoC and checks the canary.

```bash
# Clone the repo
git clone https://github.com/discordwell/ndai-hackathon.git
cd ndai-hackathon

# Install
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e .

# Start PostgreSQL + Redis
docker compose up -d

# Create .env
cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://ndai:ndai@localhost:5432/ndai
REDIS_URL=redis://localhost:6379/0
TEE_MODE=simulated
SECRET_KEY=$(openssl rand -hex 32)
EOF

# Run migrations
alembic upgrade head

# Start server
uvicorn ndai.api.main:app --host 0.0.0.0 --port 8000
```

Then submit:
```bash
python scripts/ndai_submit.py --server http://localhost:8000
```

**What happens in simulated mode:**
- Target services start on your host (yes, Apache will actually run on port 80)
- Canary is planted in `/var/lib/ndai-oracle/` on your filesystem
- PoC runs as a subprocess with `ulimit` constraints
- Oracle checks stdout for the canary value
- PCR0 = `"simulated"` (no real attestation)

**Caveats:** Since everything runs on your host, your PoC has access to things it wouldn't have in a real enclave. A passing test here doesn't guarantee it passes in Nitro mode — but a failing test means it definitely won't.

### Option 2: Docker Mode (Recommended for Testing)

Closer to production. The target runs in a real Docker container with its own filesystem and network namespace.

```bash
# Same setup as above, but:
export TEE_MODE=simulated  # Still "simulated" — Docker isolation comes from the EIF builder

# The EIF builder generates a Dockerfile from the target spec and builds it:
docker build -t ndai-vuln-test -f /tmp/ndai-eif-builds/<hash>/Dockerfile .

# You can also build a target manually to test your PoC:
docker run -d --name test-target ubuntu:22.04
docker exec test-target apt-get update && apt-get install -y apache2
docker exec test-target service apache2 start

# Plant a canary manually
docker exec test-target mkdir -p /var/lib/ndai-oracle
docker exec test-target sh -c 'echo "test_canary_value" > /var/lib/ndai-oracle/ace_canary'

# Run your PoC
docker exec test-target bash -c '#!/bin/bash
cat /var/lib/ndai-oracle/ace_canary'
# Should output: test_canary_value
```

### Option 3: Full Nitro (Production)

For the real deal with hardware attestation:

```bash
# 1. Launch a Nitro-capable EC2 instance
./deploy/launch.sh us-east-1

# 2. Set up the instance (installs everything, builds EIF)
./deploy/setup.sh <PUBLIC_IP> ndai-key

# 3. Submit against the live instance
python scripts/ndai_submit.py --server http://<PUBLIC_IP>:8000
```

**Costs:**
- c5.xlarge: ~$0.17/hr (minimum Nitro-capable instance)
- Storage: 30GB gp3 (~$2.40/mo)
- A single verification takes 30-120 seconds
- Budget about $1-2 for an afternoon of testing

### Testing a Specific Target Locally

Here's a concrete example testing an Apache ACE exploit:

```bash
# 1. Start the verification server in simulated mode
TEE_MODE=simulated uvicorn ndai.api.main:app --port 8000 &

# 2. Write your exploit
cat > /tmp/my_exploit.sh << 'EOF'
#!/bin/bash
# My Apache 2.4.52 ACE exploit
# Step 1: trigger the vulnerability (your actual exploit code here)
# Step 2: read the canary to prove code execution
cat /var/lib/ndai-oracle/ace_canary
EOF

# 3. Submit
python scripts/ndai_submit.py \
    --server http://localhost:8000 \
    --target apache-httpd \
    --poc-file /tmp/my_exploit.sh \
    --capability ace \
    --runs 1 \
    --price 0.01

# 4. Check the result
# The CLI polls automatically and shows PASSED or FAILED
```

If it passes locally, it should pass on Nitro (assuming your exploit doesn't depend on host-specific conditions that differ inside an enclave).

## Architecture Diagram

```
┌──────────────┐     ┌────────────────┐     ┌─────────────────────────┐
│   CLI /      │     │   API Server   │     │   Nitro Enclave         │
│   Browser    │────>│   (FastAPI)    │────>│                         │
│              │     │                │     │  ┌───────────────────┐  │
│  Ed25519     │     │  Proposal DB   │     │  │ Target Container  │  │
│  Auth        │     │  SSE Stream    │     │  │ (Apache 2.4.52)   │  │
│              │     │                │     │  │                   │  │
│  PoC Script  │     │  Dispatcher    │     │  │ /var/lib/ndai-    │  │
│  Upload      │     │  ├─ Nitro      │     │  │ oracle/ace_canary │  │
│              │     │  ├─ Windows    │     │  │ = "a7f3b2c1d9.."  │  │
│              │     │  └─ iOS        │     │  └───────────────────┘  │
│              │     │                │     │                         │
│              │<────│  Result +      │<────│  PoC Executor           │
│              │     │  Chain Hash +  │     │  Oracle Manager          │
│              │     │  PCR0          │     │  Verification Chain     │
└──────────────┘     └────────────────┘     └─────────────────────────┘
                                                     │
                                              AF_VSOCK (port 5000)
                                                     │
                                            ┌────────────────┐
                                            │  EC2 Parent    │
                                            │  (c5.xlarge)   │
                                            │                │
                                            │  nitro-cli     │
                                            │  EIF Builder   │
                                            │  Docker        │
                                            └────────────────┘
```

## Security Model

The enclave provides three guarantees:

1. **Code Integrity** — PCR0 proves exactly what code ran. If the verification logic is modified, PCR0 changes and the attestation is invalid.

2. **Isolation** — The enclave has no network access, no persistent storage, and no shell. Communication is only via vsock. The PoC cannot exfiltrate data.

3. **Confidentiality** — PoC stdout/stderr never leave the enclave. Only the capability assessment (pass/fail, which oracle was triggered, reliability score) and the chain hash are returned.

The seller's exploit code is never visible to the buyer. The buyer's patches (overlay) are never visible to the seller. The enclave sees both, verifies, and reports only the capability assessment.
