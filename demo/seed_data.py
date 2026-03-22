#!/usr/bin/env python3
"""Seed the NDAI marketplace with CVE-2024-3094 demo data.

Creates:
  1. A seller user (the security researcher)
  2. A buyer user (the defense agency)
  3. The XZ Utils backdoor vulnerability listing
  4. A buyer agreement proposal

Usage:
    python3 demo/seed_data.py [--base-url http://localhost:8000]
"""

import argparse
import json
import os
import sys

import httpx

DEFAULT_BASE_URL = "http://localhost:8000"

# Demo users
SELLER = {
    "email": "researcher@xz-security.net",
    "password": "ndai-demo-seller-2024",
    "name": "A. Freund",  # Nod to the real discoverer
}

BUYER = {
    "email": "analyst@defense-agency.gov",
    "password": "ndai-demo-buyer-2024",
    "name": "J. Smith",
}

# CVE-2024-3094 vulnerability submission
VULNERABILITY = {
    "target_software": "xz-utils (liblzma)",
    "target_version": "5.6.0 - 5.6.1",
    "vulnerability_class": "CWE-506",  # Embedded Malicious Code
    "impact_type": "RCE",
    "affected_component": "liblzma ifunc resolver → OpenSSH RSA_public_decrypt",
    "anonymized_summary": (
        "Pre-authentication remote code execution in a widely-deployed "
        "compression library used by OpenSSH on major Linux distributions. "
        "A supply-chain backdoor hooks cryptographic signature verification "
        "during SSH key exchange via shared library injection. Exploitation "
        "requires a specific Ed448-signed trigger — no brute force possible. "
        "Unauthenticated, pre-auth, runs as sshd (typically root). "
        "Affected: Fedora 40/rawhide, Debian testing/unstable, Arch Linux, "
        "Kali Linux, openSUSE Tumbleweed."
    ),
    "cvss_self_assessed": 10.0,
    "discovery_date": "2024-03-29",
    "patch_status": "unpatched",
    "exclusivity": "exclusive",
    "embargo_days": 90,
    "outside_option_value": 0.7,
    "max_disclosure_level": 3,
    "software_category": "os_kernel",
}

# Buyer agreement proposal
AGREEMENT = {
    "budget_cap": 2.5,  # ETH (high-value 0day)
    "alpha_0": 0.5,
    "security_params": {
        "k": 3,  # collusion threshold
        "p": 0.8,  # detection probability
        "C": 10.0,  # breach penalty
    },
}


def register_user(client: httpx.Client, user: dict) -> str:
    """Register a user, return auth token. Idempotent (login if exists)."""
    # Try to register
    resp = client.post("/api/v1/auth/register", json={
        "email": user["email"],
        "password": user["password"],
        "name": user["name"],
    })

    if resp.status_code == 201:
        return resp.json()["token"]
    elif resp.status_code == 409:
        # Already exists, login instead
        resp = client.post("/api/v1/auth/login", json={
            "email": user["email"],
            "password": user["password"],
        })
        resp.raise_for_status()
        return resp.json()["token"]
    else:
        resp.raise_for_status()
        return ""  # unreachable


def seed(base_url: str) -> dict:
    """Seed the marketplace and return IDs for the demo script."""
    client = httpx.Client(base_url=base_url, timeout=30.0)
    result = {}

    # Register users
    print("[*] Registering seller...")
    seller_token = register_user(client, SELLER)
    result["seller_token"] = seller_token
    print(f"[+] Seller: {SELLER['email']}")

    print("[*] Registering buyer...")
    buyer_token = register_user(client, BUYER)
    result["buyer_token"] = buyer_token
    print(f"[+] Buyer: {BUYER['email']}")

    # Create vulnerability listing
    print("[*] Submitting CVE-2024-3094 vulnerability...")
    resp = client.post(
        "/api/v1/vulns/",
        json=VULNERABILITY,
        headers={"Authorization": f"Bearer {seller_token}"},
    )
    resp.raise_for_status()
    vuln_data = resp.json()
    result["vulnerability_id"] = vuln_data["id"]
    print(f"[+] Vulnerability: {vuln_data['id']}")
    print(f"    Target: {vuln_data['target_software']}")
    print(f"    CVSS: {vuln_data['cvss_self_assessed']}")

    # Create buyer agreement
    print("[*] Buyer proposing deal...")
    resp = client.post(
        f"/api/v1/vulns/{vuln_data['id']}/agreements",
        json=AGREEMENT,
        headers={"Authorization": f"Bearer {buyer_token}"},
    )
    resp.raise_for_status()
    agreement_data = resp.json()
    result["agreement_id"] = agreement_data["id"]
    print(f"[+] Agreement: {agreement_data['id']}")
    print(f"    Budget cap: {AGREEMENT['budget_cap']} ETH")
    print(f"    Status: {agreement_data['status']}")

    # Save result for demo script
    result_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seed_result.json")
    with open(result_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\n[+] Seed complete. Result saved to {result_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Seed NDAI marketplace with CVE-2024-3094 demo data")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="API base URL")
    args = parser.parse_args()

    try:
        result = seed(args.base_url)
        print(f"\n[+] Demo ready! IDs:")
        print(f"    Vulnerability: {result['vulnerability_id']}")
        print(f"    Agreement:     {result['agreement_id']}")
    except httpx.ConnectError:
        print(f"\n[!] Cannot connect to {args.base_url}")
        print(f"    Make sure the NDAI server is running.")
        sys.exit(1)
    except httpx.HTTPStatusError as e:
        print(f"\n[!] API error: {e.response.status_code}")
        print(f"    {e.response.text[:200]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
