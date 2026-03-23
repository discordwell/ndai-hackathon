# Apache HTTP Server — Verification Target

## Build Spec

| Field | Value |
|-------|-------|
| Base Image | `ubuntu:22.04` |
| Apache | `2.4.52-1ubuntu4.3` |
| Curl | `7.81.0-1ubuntu1.13` |
| Service | `apache2` on port 80 |
| PoC User | `poc` (unprivileged) |
| Oracle Dir | `/var/lib/ndai-oracle/` |

## Reproduce Locally

```bash
# Build the target image (from project root)
docker build -f targets/apache-httpd/Dockerfile -t ndai-apache-target .

# Convert to EIF (requires Nitro-capable EC2 instance)
nitro-cli build-enclave --docker-uri ndai-apache-target:latest --output-file apache-httpd.eif

# Compare PCR0 against on-chain registry
cast call 0x6A2Af53235dAe573c8F2AfbBa58C666fB4868222 "getPCR0()(bytes32,bytes16)" --rpc-url https://ethereum-sepolia-rpc.publicnode.com
```

If your PCR0 matches the on-chain value, the enclave is running this exact code.
