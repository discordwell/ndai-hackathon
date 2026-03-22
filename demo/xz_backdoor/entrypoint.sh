#!/bin/bash
# CVE-2024-3094 Target Container Entrypoint
#
# Starts:
#   1. sshd with LD_PRELOAD=liblzma_backdoor.so (the backdoor hook)
#   2. trigger_service (feeds payloads through RSA_public_decrypt)
#
# The backdoor hook intercepts RSA_public_decrypt in sshd, checking
# for Ed448-signed command payloads — exactly as CVE-2024-3094 did.

echo "[*] CVE-2024-3094 Target Environment Starting..."
echo "[*] Backdoor hook: /usr/lib/liblzma_backdoor.so"

# Start sshd with the backdoor loaded (may fail on --network host if port 22 is taken)
echo "[*] Starting sshd with backdoored liblzma..."
LD_PRELOAD=/usr/lib/liblzma_backdoor.so /usr/sbin/sshd -D -e &
SSHD_PID=$!
echo "[+] sshd started (PID: $SSHD_PID)"

# Start the trigger service (backdoor payload delivery mechanism)
# This is the primary exploitation path for the demo
echo "[*] Starting trigger service on port 4444..."
LD_PRELOAD=/usr/lib/liblzma_backdoor.so /usr/local/bin/trigger_service &
TRIGGER_PID=$!
echo "[+] Trigger service started (PID: $TRIGGER_PID)"

echo "[+] Target environment ready."
echo "    SSH:     port 22 (may fail on --network host)"
echo "    Trigger: port 4444"

# Wait for the trigger service (primary) — ignore sshd failures
wait $TRIGGER_PID
echo "[!] Trigger service exited, shutting down..."
kill $SSHD_PID 2>/dev/null
wait
