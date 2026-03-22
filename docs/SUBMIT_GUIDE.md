# Submitting an Exploit

This guide walks through submitting a proof-of-concept (PoC) exploit to the NDAI marketplace for cryptographic verification.

## Prerequisites

```bash
pip install cryptography httpx
```

That's it. The CLI handles key generation, authentication, and submission.

## Quick Start

```bash
# Interactive mode — prompts for everything
python scripts/ndai_submit.py

# One-shot mode
python scripts/ndai_submit.py \
    --target apache-httpd \
    --poc-file my_exploit.sh \
    --capability ace \
    --runs 5 \
    --price 0.5
```

## How It Works

### 1. Identity

You authenticate with an Ed25519 keypair. The CLI generates one automatically on first run and saves it to `~/.ndai/key.hex`. No email, no account — just a key.

```bash
# Use a specific key
python scripts/ndai_submit.py --key-file /path/to/key.hex

# Key format: 64 hex chars (32 bytes raw Ed25519 private key)
```

### 2. Pick a Target

The marketplace has known targets — real software with specific versions, pre-configured for verification. Run the CLI to see what's available:

```
  #    Target                              Type       Escrow     Verified
  ─── ─────────────────────────────────── ────────── ────────── ──────
  1    Apache HTTP Server 2.4.52           bash       $100       yes
  2    XZ Utils / liblzma 5.6.0-5.6.1     python3    $500       yes
  3    OpenSSH Server 9.6p1                bash       $200       yes
```

Each target specifies:
- **PoC type** — what language your exploit runs in (`bash`, `python3`, `html`, `powershell`)
- **Escrow** — deposit required (waived if you have a badge)
- **Verified** — whether the enclave image is pre-built

### 3. Write Your PoC

Your PoC runs inside a container with the vulnerable software already installed and running. You don't need to set up the target — just exploit it.

The **critical requirement**: the enclave plants a canary file that your exploit must read and output. The canary location depends on the capability you claim:

| Capability | Canary Location | Permissions | What You Prove |
|---|---|---|---|
| `ace` | `/var/lib/ndai-oracle/ace_canary` | 0644 (world-readable) | Code execution as service user |
| `lpe` | `/var/lib/ndai-oracle/lpe_canary` | 0600 (root-only) | Privilege escalation to root |
| `info_leak` | `/var/lib/ndai-oracle/info_canary` (0600, root-only) + `$NDAI_INFO_CANARY` env var | Root-only on disk, also in process env | Memory read from target process |
| `callback` | `/var/lib/ndai-oracle/callback_token` contains `host:port:token` | 0644 | Blind RCE — trigger outbound TCP |
| `crash` | N/A | N/A | Target process dies with signal |
| `dos` | N/A | N/A | Target stops responding to health checks |

**Example: ACE PoC for Apache** (bash)
```bash
#!/bin/bash
# Exploit CVE-XXXX-XXXX in Apache 2.4.52 to achieve code execution
# The canary is a random 32-char hex string planted by the enclave
cat /var/lib/ndai-oracle/ace_canary
```

**Example: RCE PoC for XZ/liblzma** (python3)
```python
#!/usr/bin/env python3
"""Trigger CVE-2024-3094 backdoor in liblzma to achieve pre-auth RCE."""
import subprocess
# ... trigger the backdoor via sshd ...
result = subprocess.run(["cat", "/var/lib/ndai-oracle/ace_canary"], capture_output=True)
print(result.stdout.decode())
```

The canary value is a **64-character random hex string** (256 bits of entropy), regenerated each run — you can't hardcode it. Your exploit must actually achieve the capability to read it.

### 4. Submit

```bash
python scripts/ndai_submit.py \
    --target apache-httpd \
    --poc-file exploit.sh \
    --capability ace \
    --runs 3 \
    --price 0.5
```

Arguments:
- `--target` — target slug (e.g. `apache-httpd`, `xz-utils`, `openssh-server`)
- `--poc-file` — path to your PoC script
- `--capability` — what you claim (`ace`, `lpe`, `info_leak`, `callback`, `crash`, `dos`)
- `--runs` — reliability runs, 1-20 (default 3). Higher = more convincing, takes longer
- `--price` — asking price in ETH (default 0.1)
- `--dry-run` — validate everything without submitting

### 5. Verification

After submission, the enclave:

1. **Builds** a fresh container from the target spec (base image + packages + configs)
2. **Starts** the target services (e.g. Apache httpd)
3. **Plants** capability oracles (random canary files)
4. **Runs** your PoC N times, restarting services between runs to randomize ASLR
5. **Checks** whether the canary appears in your PoC's stdout/stderr
6. **Reports** the result with a cryptographic chain hash

The CLI polls for the result automatically:

```
── Triggering verification ──

  ✓ Verification started — enclave is building target environment

  ⠹ building...
  ⠼ verifying...

── RESULT ──

  VERIFICATION PASSED
  > Claimed:    ace
  > Verified:   ace
  > Reliability: 100%
  > Chain hash: 326ff7b8a9...
  > PCR0:       a8f3c2d1e5...
```

## API Reference

If you prefer raw API calls:

```bash
# 1. Register
curl -X POST https://zdayzk.com/api/v1/zk-auth/register \
  -d '{"public_key": "<hex>", "signature": "<hex>"}'

# 2. Challenge
curl -X POST https://zdayzk.com/api/v1/zk-auth/challenge \
  -d '{"public_key": "<hex>"}'

# 3. Verify (get JWT)
curl -X POST https://zdayzk.com/api/v1/zk-auth/verify \
  -d '{"public_key": "<hex>", "nonce": "<nonce>", "signature": "<hex>"}'

# 4. List targets
curl https://zdayzk.com/api/v1/targets/ -H "Authorization: Bearer <token>"

# 5. Create proposal
curl -X POST https://zdayzk.com/api/v1/proposals/ \
  -H "Authorization: Bearer <token>" \
  -d '{
    "target_id": "<uuid>",
    "poc_script": "#!/bin/bash\ncat /var/lib/ndai-oracle/ace_canary",
    "poc_script_type": "bash",
    "claimed_capability": "ace",
    "reliability_runs": 3,
    "asking_price_eth": 0.1
  }'

# 6. Trigger verification (if badge holder or after deposit)
curl -X POST https://zdayzk.com/api/v1/proposals/<id>/verify \
  -H "Authorization: Bearer <token>"

# 7. Check result
curl https://zdayzk.com/api/v1/proposals/<id> \
  -H "Authorization: Bearer <token>"

# 8. Stream progress (SSE)
curl "https://zdayzk.com/api/v1/proposals/<id>/stream?token=<jwt>"
```

## Deposit Flow

If you don't have a badge, you'll need to deposit escrow before verification:

1. The API returns `deposit_amount_wei` and `deposit_proposal_id`
2. Send the deposit to the VerificationDeposit contract on Base Sepolia
3. Confirm with `POST /proposals/<id>/confirm-deposit` providing the `tx_hash`
4. Then trigger verification

Badge holders skip this entirely — proposals go straight to `queued` status.

## Tips

- **Test locally first.** See [NITRO_VERIFICATION.md](NITRO_VERIFICATION.md) for how to run the verification pipeline on your own machine.
- **Start with `crash` or `dos`** if you're not sure your exploit achieves full ACE. The system detects what your exploit actually achieves — if you claim `ace` but only get `crash`, it'll report `crash` as the verified level.
- **Use `--dry-run`** to validate your PoC format, capability choice, and target compatibility before spending escrow.
- **Higher reliability runs** make your exploit more valuable. A buyer wants to know it works 9/10 times, not just once.
