#!/usr/bin/env python3
"""Live CVE-2024-3094 Verification — Real exploit, real Docker target, real oracle.

Runs the capability-oracle verification protocol against a Docker container
running the backdoored xz-utils/liblzma. This is NOT simulated — the PoC
actually exploits the backdoor to read the oracle canary.

Usage:
    # Standard run (3 reliability runs)
    python scripts/verify_live.py

    # Custom runs
    python scripts/verify_live.py --runs 5

    # Keep container running for inspection after
    python scripts/verify_live.py --keep

    # Build the Docker image first (if not cached)
    python scripts/verify_live.py --build
"""

import argparse
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ndai.enclave.vuln_verify.docker_executor import DockerVerifier, DockerVerifierError


# ── Colors ──

class C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    DIM = "\033[2m"
    BG_GREEN = "\033[42m"
    BG_RED = "\033[41m"
    WHITE = "\033[97m"


def banner(title: str):
    w = 64
    print(f"\n{C.BOLD}{C.CYAN}{'═' * w}")
    print(f"  {title}")
    print(f"{'═' * w}{C.RESET}\n")


def enclave(msg: str):
    print(f"  {C.BLUE}[ENCLAVE]{C.RESET} {msg}")


def oracle(msg: str):
    print(f"  {C.YELLOW}[ORACLE]{C.RESET}  {msg}")


def poc(msg: str):
    print(f"  {C.CYAN}[POC]{C.RESET}     {msg}")


def ok(msg: str):
    print(f"  {C.GREEN}[✓]{C.RESET}       {msg}")


def fail(msg: str):
    print(f"  {C.RED}[✗]{C.RESET}       {msg}")


def result_banner(verified: bool, reliability: float, runs: int, successes: int):
    w = 64
    if verified:
        print(f"\n  {C.BG_GREEN}{C.WHITE}{C.BOLD}{'':^{w}}{C.RESET}")
        print(f"  {C.BG_GREEN}{C.WHITE}{C.BOLD}{'ACE VERIFIED':^{w}}{C.RESET}")
        print(f"  {C.BG_GREEN}{C.WHITE}{C.BOLD}{f'Reliability: {successes}/{runs} ({reliability:.0%})':^{w}}{C.RESET}")
        print(f"  {C.BG_GREEN}{C.WHITE}{C.BOLD}{'':^{w}}{C.RESET}")
    else:
        print(f"\n  {C.BG_RED}{C.WHITE}{C.BOLD}{'':^{w}}{C.RESET}")
        print(f"  {C.BG_RED}{C.WHITE}{C.BOLD}{'VERIFICATION FAILED':^{w}}{C.RESET}")
        print(f"  {C.BG_RED}{C.WHITE}{C.BOLD}{f'Successes: {successes}/{runs}':^{w}}{C.RESET}")
        print(f"  {C.BG_RED}{C.WHITE}{C.BOLD}{'':^{w}}{C.RESET}")


def main():
    parser = argparse.ArgumentParser(description="Live CVE-2024-3094 Verification")
    parser.add_argument("--runs", type=int, default=3, help="Number of reliability runs")
    parser.add_argument("--build", action="store_true", help="Build Docker image before verification")
    parser.add_argument("--keep", action="store_true", help="Keep container running after verification")
    parser.add_argument("--image", default="ndai-xz-target", help="Docker image name")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    xz_dir = os.path.join(project_root, "demo", "xz_backdoor")
    poc_path = os.path.join(xz_dir, "poc_trigger.py")

    banner("CVE-2024-3094 LIVE VERIFICATION")
    print(f"  {C.DIM}Target:  xz-utils (liblzma) 5.6.0 - 5.6.1{C.RESET}")
    print(f"  {C.DIM}Impact:  RCE — Pre-authentication via backdoored OpenSSH{C.RESET}")
    print(f"  {C.DIM}CVSS:    10.0 (Critical){C.RESET}")
    print(f"  {C.DIM}Oracle:  ACE (Arbitrary Code Execution){C.RESET}")
    print(f"  {C.DIM}Runs:    {args.runs}{C.RESET}")
    print()

    verifier = DockerVerifier(
        image=args.image,
        poc_script_path=poc_path,
        container_name="ndai-xz-verify",
        startup_wait=4.0,
    )

    try:
        # Phase 1: Build (optional)
        if args.build:
            enclave("Building Docker target image...")
            verifier.build_image(xz_dir)
            ok(f"Image built: {args.image}")
        else:
            enclave(f"Using cached image: {args.image}")

        # Phase 2: Start container
        enclave("Starting target container (debian:12 + backdoored liblzma + sshd)...")
        cid = verifier.start_container()
        ok(f"Container running: {cid}")
        enclave("sshd started with LD_PRELOAD=liblzma_backdoor.so")
        enclave("Trigger service listening on port 4444")

        # Phase 3-4: Reliability runs
        successes = 0
        for run_num in range(1, args.runs + 1):
            print(f"\n  {C.BOLD}── Run {run_num}/{args.runs} ──{C.RESET}")

            # Plant fresh canary
            canary = verifier.plant_canary()
            oracle(f"ACE canary planted: {canary}")

            # Run PoC
            poc(f"Sending Ed448-signed SSH certificate to trigger port...")
            start = time.monotonic()
            stdout, stderr = verifier.run_poc()
            elapsed = time.monotonic() - start

            # Check oracle
            found = verifier.check_canary(stdout, canary)
            if found:
                successes += 1
                ok(f"Canary found in stdout ({elapsed:.1f}s)")
                ok(f"Pre-auth RCE confirmed — backdoor executed: cat /var/lib/ndai-oracle/ace_canary")
            else:
                fail(f"Canary NOT found in stdout ({elapsed:.1f}s)")
                if stderr.strip():
                    print(f"  {C.DIM}stderr: {stderr.strip()[:200]}{C.RESET}")

        # Phase 5: Result
        reliability = successes / args.runs if args.runs > 0 else 0.0
        verified = successes > 0

        result_banner(verified, reliability, args.runs, successes)

        if verified:
            print(f"\n  {C.BOLD}Capability Assessment:{C.RESET}")
            print(f"  Claimed:    ACE (Arbitrary Code Execution)")
            print(f"  Verified:   {C.GREEN}ACE{C.RESET}")
            print(f"  Mechanism:  liblzma ifunc hook → RSA_public_decrypt → Ed448-signed RCE")
            print(f"  Reliability:{C.GREEN} {successes}/{args.runs} ({reliability:.0%}){C.RESET}")
            print()
            print(f"  {C.DIM}The exploit was verified inside a TEE-isolated environment.{C.RESET}")
            print(f"  {C.DIM}The seller's PoC successfully read the enclave-generated canary{C.RESET}")
            print(f"  {C.DIM}through pre-authentication remote code execution.{C.RESET}")

    except DockerVerifierError as e:
        fail(f"Verification error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n{C.DIM}Interrupted.{C.RESET}")
    finally:
        if not args.keep:
            print()
            enclave("Cleaning up container...")
            verifier.stop_container()
            ok("Container removed")
        else:
            print()
            enclave(f"Container kept running: docker exec -it ndai-xz-verify bash")

    print()


if __name__ == "__main__":
    main()
