# CVE-2024-3094 — XZ Utils Backdoor Reproduction

## Overview

This directory contains a **faithful reproduction** of the CVE-2024-3094 (XZ Utils backdoor) attack pattern for the NDAI 0day marketplace demo. It implements the same exploit mechanism as the original but uses a known test keypair instead of the unknown attacker key.

## What Was CVE-2024-3094?

In March 2024, Andres Freund (Microsoft) discovered a backdoor in xz-utils versions 5.6.0 and 5.6.1. The attacker ("Jia Tan") spent **two years** gaining co-maintainer trust before injecting malicious code into the source release tarballs.

**Attack chain:**
1. Modified build system (M4 macros) extracted obfuscated payload from test `.xz` files
2. Payload compiled into liblzma as a modified `crc64_resolve()` ifunc
3. When OpenSSH loaded liblzma (via systemd), the ifunc installed a hook on `RSA_public_decrypt`
4. The hook checked SSH key data for a specific **Ed448 signature**
5. If the signature verified, the embedded command was executed **before authentication**
6. Result: **Unauthenticated remote code execution** on any affected SSH server

**CVSS: 10.0** | Affected: Fedora 40/rawhide, Debian testing/unstable, Arch Linux, Kali Linux

## What We Reproduce

| Original | Our Reproduction |
|----------|-----------------|
| liblzma ifunc resolver hook | LD_PRELOAD shared library hook |
| RSA_public_decrypt interception | Same — identical hook point |
| Ed448 signature verification | Same — using test keypair |
| Pre-auth command execution via system() | Same |
| Build-time M4 macro obfuscation | **Omitted** (stealth, not exploitation) |
| Anti-analysis checks | **Omitted** (stealth, not exploitation) |
| Unknown attacker Ed448 key | **Known test key** (generate_keys.py) |

## Files

| File | Purpose |
|------|---------|
| `generate_keys.py` | Generate Ed448 test keypair |
| `backdoor_hook.c` | The backdoor: hooks RSA_public_decrypt, verifies Ed448 sig, executes command |
| `trigger_service.c` | Demo helper: feeds payloads through RSA_public_decrypt |
| `build_backdoor.sh` | Compile the shared library |
| `poc_trigger.py` | PoC script: builds Ed448-signed payload, triggers backdoor |
| `Dockerfile.target` | Target container: Debian 12 + OpenSSH + backdoor |
| `entrypoint.sh` | Container entrypoint |

## Quick Start

```bash
# 1. Generate test keys
python3 generate_keys.py

# 2. Build the target container
docker build -f Dockerfile.target -t ndai-xz-target .

# 3. Run the target
docker run -d -p 2222:22 -p 4444:4444 --name xz-target ndai-xz-target

# 4. Plant a test canary (simulating the oracle)
docker exec xz-target sh -c 'echo "test_canary_abc123" > /var/lib/ndai-oracle/ace_canary'

# 5. Run the PoC
python3 poc_trigger.py --target 127.0.0.1 --trigger-port 4444

# Expected output: "test_canary_abc123" (proves code execution)
```

## How It Works in the NDAI Marketplace

1. **Seller** submits this vulnerability with encrypted PoC and target spec
2. **NDAI enclave** builds the target environment from the spec
3. **OracleManager** plants a random ACE canary in `/var/lib/ndai-oracle/ace_canary`
4. **PoCExecutor** runs `poc_trigger.py` with RLIMIT isolation
5. **Backdoor** executes `cat /var/lib/ndai-oracle/ace_canary` via pre-auth RCE
6. **OracleManager** detects the canary in stdout → **ACE VERIFIED**
7. **Negotiation** proceeds with the verified capability assessment

## Security Notice

This reproduction is for **authorized security research** and NDAI marketplace demonstration only. CVE-2024-3094 has been patched since March 2024. The test Ed448 keypair has no real-world value — the original attacker's key is unknown.
