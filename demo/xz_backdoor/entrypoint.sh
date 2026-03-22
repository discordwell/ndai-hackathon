#!/bin/bash
# CVE-2024-3094 Target Container Entrypoint
#
# Starts:
#   1. sshd with LD_PRELOAD=liblzma_backdoor.so (the backdoor hook)
#   2. trigger_service (feeds payloads through RSA_public_decrypt)
#
# The backdoor hook intercepts RSA_public_decrypt in sshd, checking
# for Ed448-signed command payloads — exactly as CVE-2024-3094 did.

set -e

echo "[*] CVE-2024-3094 Target Environment Starting..."
echo "[*] Backdoor hook: /usr/lib/liblzma_backdoor.so"

# Start sshd with the backdoor loaded
echo "[*] Starting sshd with backdoored liblzma..."
LD_PRELOAD=/usr/lib/liblzma_backdoor.so /usr/sbin/sshd -D -e &
SSHD_PID=$!
echo "[+] sshd started (PID: $SSHD_PID)"

# Start the trigger service (backdoor payload delivery mechanism)
echo "[*] Starting trigger service on port 4444..."
LD_PRELOAD=/usr/lib/liblzma_backdoor.so /usr/local/bin/trigger_service &
TRIGGER_PID=$!
echo "[+] Trigger service started (PID: $TRIGGER_PID)"

echo "[+] Target environment ready."
echo "    SSH:     port 22"
echo "    Trigger: port 4444"

# Wait for either process to exit
wait -n $SSHD_PID $TRIGGER_PID
echo "[!] A service exited, shutting down..."
kill $SSHD_PID $TRIGGER_PID 2>/dev/null
wait
