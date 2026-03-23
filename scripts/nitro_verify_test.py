"""Test real Nitro Enclave verification on EC2."""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

BASE = "http://localhost:8000/api/v1"


def api(method, path, data=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  FAIL {method} {path} -> {e.code}: {body[:300]}")
        return None


def main():
    # Auth
    privkey = Ed25519PrivateKey.generate()
    pk = privkey.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    reg_sig = privkey.sign(f"NDAI_REGISTER:{pk}".encode()).hex()
    api("POST", "/zk-auth/register", {"public_key": pk, "signature": reg_sig})

    ch = api("POST", "/zk-auth/challenge", {"public_key": pk})
    auth_sig = privkey.sign(f"NDAI_AUTH:{ch['nonce']}".encode()).hex()
    vr = api("POST", "/zk-auth/verify", {"public_key": pk, "nonce": ch["nonce"], "signature": auth_sig})
    token = vr["access_token"]
    print("Authenticated")

    # Grant badge (use sg docker if not in docker group)
    cmd = f"docker exec ndai-hackathon-postgres-1 psql -U ndai -d ndai -c \"UPDATE vuln_identities SET has_badge = true WHERE public_key = '{pk}';\""
    result = subprocess.run(cmd, shell=True, capture_output=True)
    if result.returncode != 0:
        # Try with sg docker
        subprocess.run(f'sg docker -c \'{cmd}\'', shell=True, check=True, capture_output=True)
    print("Badge granted")

    # Get Apache target
    targets = api("GET", "/targets/", token=token)
    apache = [t for t in targets if t["slug"] == "apache-httpd"]
    apache_id = apache[0]["id"]
    print(f"Target: {apache[0]['display_name']} ({apache_id})")

    # Create proposal
    p = api("POST", "/proposals/", data={
        "target_id": apache_id,
        "poc_script": "#!/bin/bash\ncat /var/lib/ndai-oracle/ace_canary",
        "poc_script_type": "bash",
        "claimed_capability": "ace",
        "reliability_runs": 1,
        "asking_price_eth": 0.05,
    }, token=token)
    pid = p["id"]
    print(f"Proposal: {pid} (status={p['status']})")

    # Trigger verification
    v = api("POST", f"/proposals/{pid}/verify", token=token)
    print(f"Triggered: {v}")

    # Poll for result
    print("\nWaiting for Nitro verification...")
    for i in range(60):
        time.sleep(5)
        detail = api("GET", f"/proposals/{pid}", token=token)
        if not detail:
            print(f"  [{i+1}] Failed to fetch proposal")
            continue
        status = detail["status"]
        if status in ("passed", "failed"):
            print(f"\n{'='*60}")
            print(f"VERIFICATION {'PASSED' if status == 'passed' else 'FAILED'}")
            print(f"{'='*60}")
            pcr0 = detail.get("attestation_pcr0", "unknown")
            chain_hash = detail.get("verification_chain_hash", "unknown")
            result = detail.get("verification_result_json", {})
            print(f"PCR0:       {pcr0}")
            print(f"Chain hash: {chain_hash}")
            print(f"Result:     {json.dumps(result, indent=2)}")
            if detail.get("error_details"):
                print(f"Error:      {detail['error_details']}")
            return 0 if status == "passed" else 1
        print(f"  [{i+1}/60] {status}...")

    print("Timed out waiting for verification (5 min)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
