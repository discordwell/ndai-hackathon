#!/usr/bin/env python3
"""Pre-demo health check — verify all dependencies are available.

Run this before the demo to catch issues early.

Usage:
    python demo/health_check.py [--base-url http://localhost:8000]
"""

import argparse
import os
import shutil
import sys

CHECKS_PASSED = 0
CHECKS_FAILED = 0


def check(name: str, ok: bool, detail: str = ""):
    global CHECKS_PASSED, CHECKS_FAILED
    if ok:
        CHECKS_PASSED += 1
        print(f"  ✓ {name}")
    else:
        CHECKS_FAILED += 1
        print(f"  ✗ {name}: {detail}")


def main():
    parser = argparse.ArgumentParser(description="Pre-demo health check")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    print("NDAI Demo Health Check")
    print("=" * 40)

    # 1. Python dependencies
    print("\n[Python Dependencies]")
    try:
        import httpx
        check("httpx", True)
    except ImportError:
        check("httpx", False, "pip install httpx")

    try:
        from cryptography.hazmat.primitives.asymmetric.ed448 import Ed448PrivateKey
        check("cryptography (Ed448)", True)
    except ImportError:
        check("cryptography", False, "pip install cryptography")

    try:
        import web3
        check("web3.py", True)
    except ImportError:
        check("web3.py", False, "pip install web3")

    # 2. Demo files
    print("\n[Demo Files]")
    demo_dir = os.path.join(os.path.dirname(__file__), "xz_backdoor")
    check("demo/xz_backdoor/ exists", os.path.isdir(demo_dir))
    check("test_ed448_private.pem", os.path.isfile(os.path.join(demo_dir, "test_ed448_private.pem")),
          "Run: python demo/xz_backdoor/generate_keys.py")
    check("test_ed448_public.h", os.path.isfile(os.path.join(demo_dir, "test_ed448_public.h")),
          "Run: python demo/xz_backdoor/generate_keys.py")
    check("backdoor_hook.c", os.path.isfile(os.path.join(demo_dir, "backdoor_hook.c")))
    check("poc_trigger.py", os.path.isfile(os.path.join(demo_dir, "poc_trigger.py")))

    # 3. Docker
    print("\n[Docker]")
    check("docker available", shutil.which("docker") is not None, "Docker not installed")

    # 4. API server
    print("\n[API Server]")
    try:
        import httpx
        resp = httpx.get(f"{args.base_url}/health", timeout=5)
        check(f"API reachable at {args.base_url}", resp.status_code == 200)
    except Exception:
        check(f"API reachable at {args.base_url}", False, "Server not running")

    # 5. LLM API key
    print("\n[LLM Provider]")
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    check("OPENAI_API_KEY set", bool(openai_key), "export OPENAI_API_KEY=sk-...")

    # Summary
    print(f"\n{'=' * 40}")
    total = CHECKS_PASSED + CHECKS_FAILED
    if CHECKS_FAILED == 0:
        print(f"All {total} checks passed. Ready for demo!")
    else:
        print(f"{CHECKS_PASSED}/{total} passed, {CHECKS_FAILED} failed.")
        print("Fix the above issues before running the demo.")
        sys.exit(1)


if __name__ == "__main__":
    main()
