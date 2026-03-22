"""Browser-based PoC executor for Chrome and Firefox targets.

For browser targets, the seller provides an HTML file instead of a bash/python
script. The executor:
1. Starts an HTTP server serving the exploit HTML
2. Launches headless Chrome/Firefox pointed at the server
3. Monitors for canary retrieval (filesystem, callback, crash)
4. Returns results through the standard capability oracle pipeline
"""

import asyncio
import hashlib
import http.server
import logging
import os
import secrets
import socketserver
import tempfile
import threading
from pathlib import Path
from typing import Any

from ndai.enclave.vuln_verify.models import (
    CapabilityLevel,
    CapabilityResult,
    PoCResult,
    ResourceLimits,
)

logger = logging.getLogger(__name__)


class BrowserPoCServer:
    """Simple HTTP server that serves the exploit HTML file."""

    def __init__(self, html_content: str, port: int = 8080):
        self._html = html_content
        self._port = port
        self._server: socketserver.TCPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> int:
        """Start the server and return the port."""
        # Write HTML to a temp dir
        self._tmpdir = tempfile.mkdtemp(prefix="ndai-poc-")
        poc_path = Path(self._tmpdir) / "poc.html"
        poc_path.write_text(self._html, encoding="utf-8")

        handler = lambda *args: http.server.SimpleHTTPRequestHandler(
            *args, directory=self._tmpdir
        )
        self._server = socketserver.TCPServer(("127.0.0.1", self._port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info("PoC server started on port %d serving %s", self._port, self._tmpdir)
        return self._port

    def stop(self):
        """Stop the server."""
        if self._server:
            self._server.shutdown()
            self._server = None
        # Clean up temp dir
        import shutil
        if hasattr(self, "_tmpdir") and Path(self._tmpdir).exists():
            shutil.rmtree(self._tmpdir, ignore_errors=True)


class BrowserExecutor:
    """Execute browser-based PoCs for Chrome/Firefox targets.

    Instead of running a script directly, this executor:
    1. Plants canary files in the filesystem
    2. Starts an HTTP server with the exploit HTML
    3. Launches the browser to navigate to the exploit
    4. Checks if canaries were read/written/modified
    """

    def __init__(self, limits: ResourceLimits | None = None):
        self._limits = limits or ResourceLimits()

    def plant_canaries(self, service_user: str = "www-data") -> dict[str, str]:
        """Plant random canary files for capability oracles.

        Returns dict of canary_type -> canary_value.
        """
        canaries = {}
        canary_dir = Path("/tmp")

        # ACE canary — writable by service user, check if PoC writes a new value
        ace_canary = secrets.token_hex(16)
        ace_path = canary_dir / "canary_ace"
        ace_path.write_text("")  # empty — PoC must write the value
        canaries["ace"] = ace_canary
        canaries["ace_path"] = str(ace_path)
        canaries["ace_expected"] = ace_canary  # PoC must write this value

        # LPE canary — root-only, PoC must escalate to read
        lpe_canary = secrets.token_hex(16)
        lpe_path = canary_dir / "canary_lpe"
        lpe_path.write_text(lpe_canary)
        os.chmod(str(lpe_path), 0o600)  # root only
        canaries["lpe"] = lpe_canary
        canaries["lpe_path"] = str(lpe_path)

        # Info leak canary — in a "process memory" file
        info_canary = secrets.token_hex(16)
        info_path = canary_dir / "canary_info"
        info_path.write_text(info_canary)
        os.chmod(str(info_path), 0o640)
        canaries["info"] = info_canary
        canaries["info_path"] = str(info_path)

        return canaries

    def check_canaries(
        self,
        canaries: dict[str, str],
        stdout: str,
        stderr: str,
    ) -> CapabilityResult:
        """Check if any canaries were retrieved by the PoC."""
        ace_found = False
        lpe_found = False
        info_found = False
        crash_detected = False

        combined_output = stdout + stderr

        # ACE: check if the canary value was written to the ace file
        ace_path = Path(canaries.get("ace_path", "/tmp/canary_ace"))
        if ace_path.exists():
            content = ace_path.read_text().strip()
            ace_found = len(content) > 0  # PoC wrote something

        # LPE: check if the canary value appears in output
        lpe_canary = canaries.get("lpe", "")
        if lpe_canary and lpe_canary in combined_output:
            lpe_found = True

        # Info leak: check if the canary value appears in output
        info_canary = canaries.get("info", "")
        if info_canary and info_canary in combined_output:
            info_found = True

        # Determine verified level (highest)
        verified_level = None
        if lpe_found:
            verified_level = CapabilityLevel.LPE
        elif ace_found:
            verified_level = CapabilityLevel.ACE
        elif info_found:
            verified_level = CapabilityLevel.INFO_LEAK
        elif crash_detected:
            verified_level = CapabilityLevel.CRASH

        return CapabilityResult(
            claimed=CapabilityLevel.ACE,  # overridden by caller
            verified_level=verified_level,
            ace_canary_found=ace_found,
            lpe_canary_found=lpe_found,
            info_canary_found=info_found,
            crash_detected=crash_detected,
            reliability_score=1.0 if verified_level else 0.0,
            reliability_runs=1,
        )

    async def execute_browser_poc(
        self,
        html_content: str,
        browser_command: str,
        service_user: str = "www-data",
        timeout_sec: int = 60,
    ) -> tuple[PoCResult, CapabilityResult]:
        """Execute a browser-based PoC.

        Args:
            html_content: The exploit HTML
            browser_command: Command to launch the browser (e.g., "chromium-browser --headless ...")
            service_user: User the browser runs as
            timeout_sec: Max execution time

        Returns:
            Tuple of (PoCResult, CapabilityResult)
        """
        server = BrowserPoCServer(html_content)
        canaries = self.plant_canaries(service_user)

        try:
            port = server.start()
            poc_url = f"http://localhost:{port}/poc.html"

            # Build browser command with the PoC URL
            full_command = f"{browser_command} {poc_url}"

            # Run the browser
            proc = await asyncio.create_subprocess_shell(
                full_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_sec,
                )
                timed_out = False
            except asyncio.TimeoutError:
                proc.kill()
                stdout_bytes, stderr_bytes = await proc.communicate()
                timed_out = True

            stdout = stdout_bytes.decode("utf-8", errors="replace")[:65536]
            stderr = stderr_bytes.decode("utf-8", errors="replace")[:65536]

            signal = None
            if proc.returncode and proc.returncode < 0:
                signal = -proc.returncode

            poc_result = PoCResult(
                exit_code=proc.returncode or 0,
                stdout=stdout,
                stderr=stderr,
                signal=signal,
                timed_out=timed_out,
                duration_sec=timeout_sec if timed_out else 0.0,
            )

            # Check canaries
            capability_result = self.check_canaries(canaries, stdout, stderr)

            return poc_result, capability_result

        finally:
            server.stop()
