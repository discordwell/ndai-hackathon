#!/usr/bin/env python3
"""NDAI exploit submission CLI.

Submit a proof-of-concept exploit against a known target for
cryptographic verification inside an AWS Nitro Enclave.

Usage:
    # Interactive mode — walks you through everything
    python scripts/ndai_submit.py

    # One-shot mode
    python scripts/ndai_submit.py \
        --server https://zdayzk.com \
        --target apache-httpd \
        --capability ace \
        --poc-file my_exploit.sh \
        --runs 5 \
        --price 0.5

    # Use an existing keypair
    python scripts/ndai_submit.py --key-file ~/.ndai/key.hex

    # Dry run — validate everything without submitting
    python scripts/ndai_submit.py --dry-run

Requirements:
    pip install cryptography httpx
"""

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:
    sys.exit("Missing dependency: pip install httpx")

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
    )
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
        PublicFormat,
    )
except ImportError:
    sys.exit("Missing dependency: pip install cryptography")


DEFAULT_SERVER = "https://zdayzk.com"
KEY_DIR = Path.home() / ".ndai"
KEY_FILE = KEY_DIR / "key.hex"

# ── Styling ──────────────────────────────────────────────────────────

BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
RESET = "\033[0m"


def banner():
    print(f"""{BOLD}
    ███╗   ██╗██████╗  █████╗ ██╗
    ████╗  ██║██╔══██╗██╔══██╗██║
    ██╔██╗ ██║██║  ██║███████║██║
    ██║╚██╗██║██║  ██║██╔══██║██║
    ██║ ╚████║██████╔╝██║  ██║██║
    ╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝╚═╝  {CYAN}exploit submission{RESET}
    """)


def info(msg):
    print(f"  {CYAN}>{RESET} {msg}")


def success(msg):
    print(f"  {GREEN}✓{RESET} {msg}")


def warn(msg):
    print(f"  {YELLOW}!{RESET} {msg}")


def fail(msg):
    print(f"  {RED}✗{RESET} {msg}")


def section(msg):
    print(f"\n{BOLD}── {msg} ──{RESET}\n")


# ── API helpers ──────────────────────────────────────────────────────


class NDAIClient:
    """Thin API client for the NDAI marketplace."""

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self.http = httpx.Client(base_url=self.base, timeout=30)
        self.token = None

    def _headers(self):
        h = {"Content-Type": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def api(self, method, path, data=None):
        resp = self.http.request(method, f"/api/v1{path}", json=data, headers=self._headers())
        if resp.status_code >= 400:
            detail = resp.text[:300]
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            return None, resp.status_code, detail
        return resp.json(), resp.status_code, None

    def register_and_auth(self, privkey: Ed25519PrivateKey) -> str:
        """Ed25519 challenge-response auth. Returns JWT."""
        pk = privkey.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

        # Register (idempotent — 409 is fine, other errors are not)
        reg_sig = privkey.sign(f"NDAI_REGISTER:{pk}".encode()).hex()
        _, status, err = self.api("POST", "/zk-auth/register", {"public_key": pk, "signature": reg_sig})
        if err and status != 409:
            raise RuntimeError(f"Registration failed ({status}): {err}")

        # Challenge
        ch, _, err = self.api("POST", "/zk-auth/challenge", {"public_key": pk})
        if err:
            raise RuntimeError(f"Challenge failed: {err}")

        # Verify
        auth_sig = privkey.sign(f"NDAI_AUTH:{ch['nonce']}".encode()).hex()
        vr, _, err = self.api("POST", "/zk-auth/verify", {
            "public_key": pk, "nonce": ch["nonce"], "signature": auth_sig,
        })
        if err:
            raise RuntimeError(f"Auth verify failed: {err}")

        self.token = vr["access_token"]
        return pk


# ── Key management ───────────────────────────────────────────────────


def load_or_create_key(key_path: Path | None) -> Ed25519PrivateKey:
    """Load an existing Ed25519 key or generate a new one."""
    path = key_path or KEY_FILE

    if path.exists():
        hex_key = path.read_text().strip()
        privkey = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(hex_key))
        info(f"Loaded key from {path}")
        return privkey

    # Generate new key
    privkey = Ed25519PrivateKey.generate()
    raw = privkey.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw)
    path.chmod(0o600)
    success(f"Generated new Ed25519 keypair → {path}")
    pk = privkey.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    info(f"Public key: {pk[:16]}...{pk[-8:]}")
    warn(f"Key is unencrypted on disk. Protect {path} — it controls your marketplace identity.")
    return privkey


# ── Interactive prompts ──────────────────────────────────────────────


def pick_target(client: NDAIClient) -> dict:
    """Let the user choose a target from the marketplace."""
    targets, _, err = client.api("GET", "/targets/")
    if err or not targets:
        fail(f"Could not list targets: {err}")
        sys.exit(1)

    active = [t for t in targets if t["is_active"]]
    if not active:
        fail("No active targets available")
        sys.exit(1)

    print(f"  {'#':<4} {'Target':<35} {'Type':<10} {'Escrow':<10} {'Verified':<6}")
    print(f"  {'─'*4} {'─'*35} {'─'*10} {'─'*10} {'─'*6}")
    for i, t in enumerate(active, 1):
        icon = t.get("icon_emoji", "")
        pre = "yes" if t.get("has_prebuilt") else "no"
        print(f"  {i:<4} {icon} {t['display_name']:<32} {t['poc_script_type']:<10} ${t['escrow_amount_usd']:<9} {pre}")

    while True:
        choice = input(f"\n  {CYAN}Select target [1-{len(active)}]:{RESET} ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(active):
                return active[idx]
        except ValueError:
            # Try by slug
            for t in active:
                if t["slug"] == choice:
                    return t
        warn("Invalid choice, try again")


def get_poc_script(target: dict, poc_file: str | None) -> str:
    """Read PoC from file or prompt for inline entry."""
    if poc_file:
        path = Path(poc_file)
        if not path.exists():
            fail(f"PoC file not found: {poc_file}")
            sys.exit(1)
        size = path.stat().st_size
        if size > 262144:
            fail(f"PoC file too large ({size} bytes, max 256KB)")
            sys.exit(1)
        script = path.read_text()
        info(f"Loaded PoC from {poc_file} ({len(script)} bytes)")
        return script

    print(f"  Enter your PoC script ({target['poc_script_type']}).")
    print(f"  {DIM}The enclave will plant a canary at /var/lib/ndai-oracle/ace_canary{RESET}")
    print(f"  {DIM}Your exploit must read and output the canary value to prove capability.{RESET}")
    print(f"  {DIM}Type EOF on a blank line when done:{RESET}\n")

    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "EOF":
                break
            lines.append(line)
        except EOFError:
            break

    return "\n".join(lines)


def pick_capability() -> str:
    """Choose claimed capability level."""
    caps = [
        ("ace", "Arbitrary Code Execution — read a file as the service user"),
        ("lpe", "Local Privilege Escalation — read a root-only file"),
        ("info_leak", "Information Leak — read process memory"),
        ("callback", "Blind RCE — trigger an outbound connection"),
        ("crash", "Crash — terminate the target process"),
        ("dos", "Denial of Service — make the target unresponsive"),
    ]
    print()
    for i, (code, desc) in enumerate(caps, 1):
        print(f"  {i}. {BOLD}{code:<12}{RESET} {desc}")

    while True:
        choice = input(f"\n  {CYAN}Capability [1-{len(caps)}]:{RESET} ").strip()
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(caps):
                return caps[idx][0]
        except ValueError:
            if choice in [c[0] for c in caps]:
                return choice
        warn("Invalid choice")


# ── Submission flow ──────────────────────────────────────────────────


def submit(client: NDAIClient, target: dict, poc_script: str,
           capability: str, runs: int, price: float, dry_run: bool):
    """Create proposal, optionally trigger verification, poll for result."""

    payload = {
        "target_id": target["id"],
        "poc_script": poc_script,
        "poc_script_type": target["poc_script_type"],
        "claimed_capability": capability,
        "reliability_runs": runs,
        "asking_price_eth": price,
    }

    if dry_run:
        section("DRY RUN — would submit")
        print(json.dumps(payload, indent=2))
        return

    section("Submitting proposal")
    info(f"Target:     {target['display_name']}")
    info(f"Capability: {capability}")
    info(f"Runs:       {runs}")
    info(f"Price:      {price} ETH")
    info(f"PoC size:   {len(poc_script)} bytes")

    proposal, status, err = client.api("POST", "/proposals/", payload)
    if err:
        fail(f"Submission failed ({status}): {err}")
        sys.exit(1)

    pid = proposal["id"]
    success(f"Proposal created: {pid}")
    info(f"Status: {proposal['status']}")

    if proposal["deposit_required"]:
        section("Deposit required")
        info(f"Amount: {proposal['deposit_amount_wei']} wei")
        info(f"Proposal ID (on-chain): {proposal['deposit_proposal_id']}")
        warn("Deposit your escrow, then confirm with:")
        print(f"\n    curl -X POST {client.base}/api/v1/proposals/{pid}/confirm-deposit \\")
        print(f"         -H 'Authorization: Bearer <token>' \\")
        print(f"         -d '{{\"tx_hash\": \"0x...\"}}'")
        print(f"\n  After deposit confirmation, trigger verification:")
        print(f"\n    curl -X POST {client.base}/api/v1/proposals/{pid}/verify \\")
        print(f"         -H 'Authorization: Bearer <token>'")
        return

    # Badge holder — auto-queued, trigger verification
    section("Triggering verification")
    v, _, err = client.api("POST", f"/proposals/{pid}/verify")
    if err:
        fail(f"Could not trigger verification: {err}")
        info(f"Trigger manually: POST /api/v1/proposals/{pid}/verify")
        return

    success("Verification started — enclave is building target environment")
    info("This typically takes 30-120 seconds\n")

    # Poll for result
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    for i in range(120):  # 10 min max
        time.sleep(5)
        detail, _, err = client.api("GET", f"/proposals/{pid}")
        if err:
            warn(f"Poll failed: {err}")
            continue

        status = detail["status"]
        frame = spinner[i % len(spinner)]
        print(f"\r  {frame} {status}...", end="", flush=True)

        if status in ("passed", "failed"):
            print()  # newline after spinner
            section("RESULT")

            if status == "passed":
                print(f"  {GREEN}{BOLD}VERIFICATION PASSED{RESET}")
            else:
                print(f"  {RED}{BOLD}VERIFICATION FAILED{RESET}")

            result = detail.get("verification_result_json", {})
            info(f"Claimed:    {result.get('claimed_capability', '?')}")
            info(f"Verified:   {result.get('verified_capability', 'none')}")
            info(f"Reliability: {result.get('reliability_score', 0):.0%}")
            info(f"Chain hash: {detail.get('verification_chain_hash', 'n/a')}")
            info(f"PCR0:       {detail.get('attestation_pcr0', 'n/a')}")

            if detail.get("error_details"):
                warn(f"Error: {detail['error_details']}")

            return

    print()
    warn("Timed out after 10 minutes. Check status:")
    print(f"    GET {client.base}/api/v1/proposals/{pid}")


# ── Main ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Submit an exploit to the NDAI zero-day marketplace",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                     # interactive mode
  %(prog)s --target apache-httpd --poc-file exploit.sh --capability ace
  %(prog)s --dry-run --poc-file exploit.sh     # validate without submitting

See docs/SUBMIT_GUIDE.md for the full walkthrough.
""",
    )
    parser.add_argument("--server", default=DEFAULT_SERVER, help="API server URL")
    parser.add_argument("--key-file", type=Path, help="Path to Ed25519 private key (hex)")
    parser.add_argument("--target", help="Target slug (e.g. apache-httpd, xz-utils)")
    parser.add_argument("--poc-file", help="Path to PoC script file")
    parser.add_argument("--capability", choices=["ace", "lpe", "info_leak", "callback", "crash", "dos"])
    parser.add_argument("--runs", type=int, default=3, help="Reliability runs (1-20, default 3)")
    parser.add_argument("--price", type=float, default=0.1, help="Asking price in ETH (default 0.1)")
    parser.add_argument("--dry-run", action="store_true", help="Validate without submitting")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    args = parser.parse_args()

    if not args.quiet:
        banner()

    # Auth
    section("Authentication")
    privkey = load_or_create_key(args.key_file)
    client = NDAIClient(args.server)
    pk = client.register_and_auth(privkey)
    success(f"Authenticated as {pk[:16]}...{pk[-8:]}")

    # Target
    section("Target selection")
    if args.target:
        targets, _, err = client.api("GET", "/targets/")
        if err:
            fail(f"Could not list targets: {err}")
            sys.exit(1)
        matches = [t for t in targets if t["slug"] == args.target]
        if not matches:
            fail(f"Target '{args.target}' not found. Available: {[t['slug'] for t in targets]}")
            sys.exit(1)
        target = matches[0]
        info(f"Selected: {target['display_name']}")
    else:
        target = pick_target(client)
    success(f"Target: {target['display_name']} ({target['poc_script_type']})")

    # PoC
    section("Proof of Concept")
    poc_script = get_poc_script(target, args.poc_file)
    success(f"PoC ready ({len(poc_script)} bytes, {target['poc_script_type']})")

    # Capability
    if args.capability:
        capability = args.capability
    else:
        section("Capability claim")
        capability = pick_capability()
    success(f"Claiming: {capability}")

    # Runs & price
    runs = max(1, min(20, args.runs))
    price = args.price

    if not args.quiet and not args.dry_run:
        print(f"\n  {BOLD}Ready to submit:{RESET}")
        print(f"    Target:     {target['display_name']}")
        print(f"    Capability: {capability}")
        print(f"    Runs:       {runs}")
        print(f"    Price:      {price} ETH")
        confirm = input(f"\n  {CYAN}Proceed? [Y/n]:{RESET} ").strip().lower()
        if confirm and confirm != "y":
            info("Aborted")
            return

    submit(client, target, poc_script, capability, runs, price, args.dry_run)


if __name__ == "__main__":
    main()
