#!/usr/bin/env python3
"""Generate Ed448 test keypair for the CVE-2024-3094 reproduction.

These keys have NO real-world value — they are used exclusively for the
NDAI marketplace demo to simulate the XZ Utils backdoor's authentication
mechanism. The original attacker's Ed448 private key is unknown.

Outputs:
  - test_ed448_private.pem  (PEM-encoded private key)
  - test_ed448_public.pem   (PEM-encoded public key)
  - test_ed448_public.h     (C header with raw public key bytes)
"""

import os
import sys

from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    # Generate keypair
    private_key = Ed448PrivateKey.generate()
    public_key = private_key.public_key()

    # Write PEM files
    priv_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    pub_pem = public_key.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)

    priv_path = os.path.join(HERE, "test_ed448_private.pem")
    pub_path = os.path.join(HERE, "test_ed448_public.pem")

    with open(priv_path, "wb") as f:
        f.write(priv_pem)
    with open(pub_path, "wb") as f:
        f.write(pub_pem)

    # Write C header with raw public key bytes for embedding in backdoor_hook.c
    raw_pub = public_key.public_bytes(Encoding.Raw, PublicFormat.Raw)
    hex_bytes = ", ".join(f"0x{b:02x}" for b in raw_pub)

    header_path = os.path.join(HERE, "test_ed448_public.h")
    with open(header_path, "w") as f:
        f.write("/* Auto-generated Ed448 test public key for CVE-2024-3094 reproduction */\n")
        f.write(f"/* Key length: {len(raw_pub)} bytes */\n")
        f.write("#ifndef TEST_ED448_PUBLIC_H\n")
        f.write("#define TEST_ED448_PUBLIC_H\n\n")
        f.write(f"static const unsigned char ED448_TEST_PUBKEY[{len(raw_pub)}] = {{\n")
        # Write in rows of 12
        for i in range(0, len(raw_pub), 12):
            chunk = raw_pub[i:i+12]
            line = ", ".join(f"0x{b:02x}" for b in chunk)
            if i + 12 < len(raw_pub):
                line += ","
            f.write(f"    {line}\n")
        f.write("};\n\n")
        f.write("#endif /* TEST_ED448_PUBLIC_H */\n")

    print(f"Generated keypair:")
    print(f"  Private key: {priv_path}")
    print(f"  Public key:  {pub_path}")
    print(f"  C header:    {header_path}")
    print(f"  Public key ({len(raw_pub)} bytes): {raw_pub.hex()}")


if __name__ == "__main__":
    main()
