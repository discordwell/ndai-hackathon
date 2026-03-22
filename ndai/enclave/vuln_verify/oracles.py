"""Capability oracles — enclave-generated challenges that prove exploit capabilities.

The key insight: the SELLER doesn't define success criteria. The ENCLAVE generates
random canary values and plants them in locations that require specific capability
levels to access. The seller's PoC must retrieve and output the canary to prove
it achieves the claimed capability.

Oracle types:
- ACE:       Canary readable by service user → PoC must achieve code execution
- LPE:       Canary readable only by root → PoC must escalate privileges
- Info Leak: Canary loaded into target's process memory → PoC must read process memory
- Callback:  TCP listener → PoC must trigger target to connect back
- Crash:     Target process dies with specific signal
- DoS:       Target stops responding to health checks
"""

import logging
import os
import secrets
import socket
import stat
import threading
import time
from dataclasses import dataclass, field

from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    CapabilityResult,
    PoCResult,
)

logger = logging.getLogger(__name__)

ORACLE_DIR = "/var/lib/ndai-oracle"
CANARY_LENGTH = 32  # 32 hex chars = 128 bits of entropy


@dataclass
class CallbackState:
    """State for the callback listener."""
    port: int = 0
    token: str = ""
    received: bool = False
    _server_socket: socket.socket | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)


class OracleManager:
    """Plants and checks capability oracles inside the enclave.

    Usage:
        oracle = OracleManager()
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        # ... run PoC ...
        result = oracle.check_result(poc_result, CapabilityLevel.ACE)
    """

    def __init__(self, oracle_dir: str = ORACLE_DIR):
        self._dir = oracle_dir
        self._canaries: dict[str, str] = {}  # "ace" -> canary value
        self._callback = CallbackState()

    def plant_oracles(self, capability: CapabilityLevel, service_user: str = "www-data") -> None:
        """Plant capability oracles based on claimed level.

        Plants ALL oracles at or below the claimed level so we can detect
        what the exploit actually achieves (it might claim ACE but only get crash).
        """
        os.makedirs(self._dir, exist_ok=True)

        # Always plant crash detection (lowest tier)
        # Crash is detected from PoCResult.signal, no file needed

        if capability in (CapabilityLevel.ACE, CapabilityLevel.LPE,
                          CapabilityLevel.INFO_LEAK, CapabilityLevel.CALLBACK):
            self._plant_ace_canary(service_user)

        if capability == CapabilityLevel.LPE:
            self._plant_lpe_canary()

        if capability == CapabilityLevel.INFO_LEAK:
            self._plant_info_canary(service_user)

        if capability == CapabilityLevel.CALLBACK:
            self._start_callback_listener()

        logger.info(
            "Oracles planted for %s: canaries=%s callback=%s",
            capability.value,
            list(self._canaries.keys()),
            self._callback.port > 0,
        )

    def check_result(self, poc_result: PoCResult, claimed: CapabilityLevel) -> CapabilityResult:
        """Check which capability oracles were satisfied by the PoC result.

        Returns a CapabilityResult with the highest verified level and
        individual oracle outcomes.
        """
        ace_found = self._check_canary("ace", poc_result)
        lpe_found = self._check_canary("lpe", poc_result)
        info_found = self._check_canary("info", poc_result)
        callback_ok = self._check_callback()
        crash = poc_result.signal is not None
        dos = poc_result.timed_out

        # Determine highest verified level
        verified = None
        if lpe_found:
            verified = CapabilityLevel.LPE
        elif callback_ok:
            verified = CapabilityLevel.CALLBACK
        elif ace_found:
            verified = CapabilityLevel.ACE
        elif info_found:
            verified = CapabilityLevel.INFO_LEAK
        elif dos:
            verified = CapabilityLevel.DOS
        elif crash:
            verified = CapabilityLevel.CRASH

        return CapabilityResult(
            claimed=claimed,
            verified_level=verified,
            ace_canary_found=ace_found,
            lpe_canary_found=lpe_found,
            info_canary_found=info_found,
            callback_received=callback_ok,
            crash_detected=crash,
            dos_detected=dos,
        )

    def cleanup(self) -> None:
        """Remove oracle files and stop listeners."""
        if self._callback._server_socket:
            try:
                self._callback._server_socket.close()
            except Exception:
                pass

        try:
            import shutil
            shutil.rmtree(self._dir, ignore_errors=True)
        except Exception:
            pass
        self._canaries.clear()

    def _generate_canary(self) -> str:
        """Generate a cryptographically random canary value."""
        return secrets.token_hex(CANARY_LENGTH)

    def _plant_ace_canary(self, service_user: str) -> None:
        """Plant canary readable by the service user (proves ACE)."""
        canary = self._generate_canary()
        path = os.path.join(self._dir, "ace_canary")
        with open(path, "w") as f:
            f.write(canary)
        # Readable by anyone (service user can read it IF they get code execution)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)  # 0644
        self._canaries["ace"] = canary
        logger.info("ACE canary planted at %s", path)

    def _plant_lpe_canary(self) -> None:
        """Plant canary readable only by root (proves LPE)."""
        canary = self._generate_canary()
        path = os.path.join(self._dir, "lpe_canary")
        with open(path, "w") as f:
            f.write(canary)
        # Only root can read (service user must escalate to access)
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        self._canaries["lpe"] = canary
        logger.info("LPE canary planted at %s (root-only)", path)

    def _plant_info_canary(self, service_user: str) -> None:
        """Plant canary in a way that simulates in-memory data.

        For info leak testing, we write the canary to a file that the
        service loads into memory (via environment variable or config).
        The PoC must read it from process memory, not from disk.
        """
        canary = self._generate_canary()
        path = os.path.join(self._dir, "info_canary")
        with open(path, "w") as f:
            f.write(canary)
        # The canary is also set as an environment variable for the target service.
        # A real info leak (like Heartbleed) would read it from the process's memory.
        os.environ["NDAI_INFO_CANARY"] = canary
        # Make the file itself unreadable to the service user
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)  # 0600 (root only)
        self._canaries["info"] = canary
        logger.info("Info leak canary planted (env + root-only file)")

    def _start_callback_listener(self) -> None:
        """Start a TCP listener for callback oracle verification."""
        token = self._generate_canary()
        self._callback.token = token

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("127.0.0.1", 0))  # OS assigns port
        sock.listen(1)
        sock.settimeout(120)  # Max wait time
        port = sock.getsockname()[1]

        self._callback.port = port
        self._callback._server_socket = sock

        # Write the expected token to the oracle dir so the PoC knows what to send
        token_path = os.path.join(self._dir, "callback_token")
        with open(token_path, "w") as f:
            f.write(f"127.0.0.1:{port}:{token}")
        os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)

        # Start listener in background thread
        def _listen():
            try:
                conn, addr = sock.accept()
                data = conn.recv(4096).decode("utf-8", errors="replace").strip()
                if token in data:
                    self._callback.received = True
                    logger.info("Callback received from %s with valid token", addr)
                else:
                    logger.info("Callback received from %s but token mismatch", addr)
                conn.close()
            except socket.timeout:
                logger.info("Callback listener timed out — no connection received")
            except Exception as exc:
                logger.warning("Callback listener error: %s", exc)

        thread = threading.Thread(target=_listen, daemon=True)
        thread.start()
        self._callback._thread = thread
        logger.info("Callback listener started on port %d", port)

    def _check_canary(self, oracle_type: str, poc_result: PoCResult) -> bool:
        """Check if a canary value appears in PoC output."""
        canary = self._canaries.get(oracle_type)
        if not canary:
            return False
        return canary in poc_result.stdout or canary in poc_result.stderr

    def _check_callback(self) -> bool:
        """Check if the callback listener received a valid connection."""
        if not self._callback.token:
            return False
        # Give the listener a moment to process
        if self._callback._thread and self._callback._thread.is_alive():
            self._callback._thread.join(timeout=5)
        return self._callback.received
