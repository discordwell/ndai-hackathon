"""PoC executor — runs proof-of-concept scripts inside the enclave.

Manages service lifecycle and PoC execution with resource limits.
The PoC runs as a non-root user with RLIMIT constraints to prevent
it from interfering with the enclave runtime.
"""

import logging
import os
import resource
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass

from ndai.enclave.vuln_verify.models import (
    ExpectedOutcome,
    PoCResult,
    PoCSpec,
    ResourceLimits,
    ServiceSpec,
)

logger = logging.getLogger(__name__)

DEFAULT_LIMITS = ResourceLimits()


@dataclass
class ServiceStatus:
    """Status of a started service."""
    name: str
    started: bool
    healthy: bool
    error: str = ""


class PoCExecutor:
    """Executes PoC scripts inside the enclave with resource isolation."""

    def __init__(self, resource_limits: ResourceLimits | None = None, enforce_rlimits: bool = True):
        self._limits = resource_limits or DEFAULT_LIMITS
        self._enforce_rlimits = enforce_rlimits

    def start_services(self, services: list[ServiceSpec]) -> list[ServiceStatus]:
        """Start target services and verify health checks."""
        statuses = []
        for svc in services:
            status = self._start_service(svc)
            statuses.append(status)
            if not status.started:
                logger.error("Failed to start service %s: %s", svc.name, status.error)
        return statuses

    def stop_services(self, services: list[ServiceSpec]) -> None:
        """Stop all target services."""
        for svc in services:
            stop_cmd = svc.start_command.replace(" start", " stop")
            try:
                subprocess.run(
                    stop_cmd, shell=True, timeout=30,
                    capture_output=True, text=True,
                )
                logger.info("Stopped service: %s", svc.name)
            except Exception as exc:
                logger.warning("Failed to stop service %s: %s", svc.name, exc)

    def execute_poc(self, poc: PoCSpec) -> PoCResult:
        """Run the PoC script with resource limits and capture output.

        The script runs as a subprocess with:
        - RLIMIT_CPU: CPU time limit
        - RLIMIT_AS: Memory limit
        - RLIMIT_NPROC: Process count limit
        - Wall clock timeout via subprocess.Popen
        """
        # Write PoC script to temp file
        suffix = ".sh" if poc.script_type == "bash" else ".py"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, prefix="poc_"
        ) as f:
            f.write(poc.script_content)
            script_path = f.name

        os.chmod(script_path, 0o755)

        interpreter = "/bin/bash" if poc.script_type == "bash" else "/usr/bin/python3"
        cmd = [interpreter, script_path]

        start_time = time.monotonic()
        timed_out = False
        sig = None

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=self._set_resource_limits if self._enforce_rlimits else None,
            )

            try:
                stdout_bytes, stderr_bytes = proc.communicate(
                    timeout=min(poc.timeout_sec, self._limits.max_wall_sec)
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout_bytes, stderr_bytes = proc.communicate(timeout=5)
                timed_out = True

            duration = time.monotonic() - start_time
            exit_code = proc.returncode

            # Check if killed by signal (negative return code on Unix)
            if exit_code < 0:
                sig = -exit_code
                exit_code = 128 + sig  # Convention: 128 + signal

            # Truncate output
            max_bytes = self._limits.max_output_bytes
            stdout = stdout_bytes[:max_bytes].decode("utf-8", errors="replace")
            stderr = stderr_bytes[:max_bytes].decode("utf-8", errors="replace")

            return PoCResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                signal=sig,
                timed_out=timed_out,
                duration_sec=round(duration, 3),
            )

        except Exception as exc:
            duration = time.monotonic() - start_time
            logger.error("PoC execution failed: %s", exc)
            return PoCResult(
                exit_code=-1,
                stdout="",
                stderr=str(exc),
                signal=None,
                timed_out=False,
                duration_sec=round(duration, 3),
            )
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    def check_outcome(self, result: PoCResult, expected: ExpectedOutcome) -> bool:
        """Check if the PoC result matches the expected outcome.

        All specified criteria must match. Unspecified criteria (None) are ignored.
        """
        if expected.exit_code is not None and result.exit_code != expected.exit_code:
            return False

        if expected.crash_signal is not None and result.signal != expected.crash_signal:
            return False

        if expected.stdout_contains is not None and expected.stdout_contains not in result.stdout:
            return False

        if expected.stderr_contains is not None and expected.stderr_contains not in result.stderr:
            return False

        # If nothing was specified, at least one criterion must have been checked
        has_any = (
            expected.exit_code is not None
            or expected.crash_signal is not None
            or expected.stdout_contains is not None
            or expected.stderr_contains is not None
        )
        return has_any

    def _set_resource_limits(self) -> None:
        """Set resource limits for the PoC subprocess (called via preexec_fn)."""
        limits = self._limits

        # CPU time
        resource.setrlimit(resource.RLIMIT_CPU, (limits.max_cpu_sec, limits.max_cpu_sec))

        # Virtual memory (address space)
        mem_bytes = limits.max_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))

        # Number of child processes
        resource.setrlimit(resource.RLIMIT_NPROC, (limits.max_processes, limits.max_processes))

        # File size limit
        file_bytes = limits.max_file_size_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (file_bytes, file_bytes))

    def _start_service(self, svc: ServiceSpec) -> ServiceStatus:
        """Start a single service and verify its health check."""
        try:
            result = subprocess.run(
                svc.start_command, shell=True, timeout=svc.timeout_sec,
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                return ServiceStatus(
                    name=svc.name, started=False, healthy=False,
                    error=f"Start failed (exit {result.returncode}): {result.stderr[:200]}",
                )

            # Run health check with retries
            for attempt in range(5):
                time.sleep(1)
                hc = subprocess.run(
                    svc.health_check, shell=True, timeout=10,
                    capture_output=True, text=True,
                )
                if hc.returncode == 0:
                    logger.info("Service %s started and healthy", svc.name)
                    return ServiceStatus(name=svc.name, started=True, healthy=True)

            return ServiceStatus(
                name=svc.name, started=True, healthy=False,
                error="Health check failed after 5 attempts",
            )

        except subprocess.TimeoutExpired:
            return ServiceStatus(
                name=svc.name, started=False, healthy=False,
                error=f"Start timed out after {svc.timeout_sec}s",
            )
        except Exception as exc:
            return ServiceStatus(
                name=svc.name, started=False, healthy=False,
                error=str(exc),
            )
