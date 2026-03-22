"""Docker-aware verification executor for live 0day demos.

Runs capability-oracle verification against a real Docker container
instead of localhost. The container runs the vulnerable software,
canaries are planted inside via docker exec, and the PoC runs inside
the container to prove exploitation.
"""

import logging
import os
import secrets
import subprocess
import time

logger = logging.getLogger(__name__)

CANARY_LENGTH = 32
ORACLE_DIR = "/var/lib/ndai-oracle"


class DockerVerifierError(Exception):
    """Error during Docker-based verification."""


class DockerVerifier:
    """Runs capability-oracle verification against a Docker container.

    Usage:
        v = DockerVerifier("ndai-xz-target", poc_script_path="/path/to/poc_trigger.py")
        v.start_container()
        canary = v.plant_canary()
        stdout, stderr = v.run_poc()
        verified = v.check_canary(stdout, canary)
        v.stop_container()
    """

    def __init__(
        self,
        image: str,
        poc_script_path: str,
        container_name: str = "ndai-verify-target",
        network_mode: str = "host",
        startup_wait: float = 3.0,
    ):
        self.image = image
        self.poc_script_path = poc_script_path
        self.container_name = container_name
        self.network_mode = network_mode
        self.startup_wait = startup_wait
        self.container_id: str | None = None

    def _run(self, cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
        """Run a command and return the result."""
        logger.debug("Running: %s", " ".join(cmd))
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )

    def build_image(self, dockerfile_dir: str) -> None:
        """Build the Docker image from a Dockerfile directory."""
        result = self._run([
            "docker", "build",
            "-f", os.path.join(dockerfile_dir, "Dockerfile.target"),
            "-t", self.image,
            dockerfile_dir,
        ], timeout=300)
        if result.returncode != 0:
            raise DockerVerifierError(f"Docker build failed: {result.stderr[:500]}")
        logger.info("Docker image built: %s", self.image)

    def start_container(self) -> str:
        """Start the target container. Returns container ID."""
        # Remove any existing container with the same name
        self._run(["docker", "rm", "-f", self.container_name])

        result = self._run([
            "docker", "run", "-d",
            "--name", self.container_name,
            f"--network={self.network_mode}",
            self.image,
        ])
        if result.returncode != 0:
            raise DockerVerifierError(f"Docker run failed: {result.stderr[:500]}")

        self.container_id = result.stdout.strip()[:12]
        logger.info("Container started: %s (%s)", self.container_name, self.container_id)

        # Wait for services to start
        time.sleep(self.startup_wait)

        # Health check: verify trigger service is listening
        for attempt in range(5):
            hc = self._run([
                "docker", "exec", self.container_name,
                "test", "-e", "/proc/1/status",
            ])
            if hc.returncode == 0:
                break
            time.sleep(1)

        return self.container_id

    def plant_canary(self) -> str:
        """Plant an ACE oracle canary inside the container. Returns canary value."""
        canary = secrets.token_hex(CANARY_LENGTH)

        # Create oracle directory and write canary
        result = self._run([
            "docker", "exec", self.container_name,
            "sh", "-c",
            f"mkdir -p {ORACLE_DIR} && echo -n '{canary}' > {ORACLE_DIR}/ace_canary && chmod 644 {ORACLE_DIR}/ace_canary",
        ])
        if result.returncode != 0:
            raise DockerVerifierError(f"Failed to plant canary: {result.stderr[:200]}")

        # Verify canary was planted
        verify = self._run([
            "docker", "exec", self.container_name,
            "cat", f"{ORACLE_DIR}/ace_canary",
        ])
        if verify.stdout.strip() != canary:
            raise DockerVerifierError(f"Canary verification failed: got '{verify.stdout.strip()}'")

        logger.info("ACE canary planted: %s", canary[:16] + "...")
        return canary

    def run_poc(self, target: str = "127.0.0.1", trigger_port: int = 4444) -> tuple[str, str]:
        """Copy PoC into container and execute it. Returns (stdout, stderr)."""
        # Copy PoC script into container
        self._run([
            "docker", "cp", self.poc_script_path,
            f"{self.container_name}:/tmp/poc_trigger.py",
        ])

        # Also copy the private key (needed by poc_trigger.py)
        key_path = os.path.join(os.path.dirname(self.poc_script_path), "test_ed448_private.pem")
        if os.path.exists(key_path):
            self._run([
                "docker", "cp", key_path,
                f"{self.container_name}:/tmp/test_ed448_private.pem",
            ])

        # Execute PoC inside the container
        result = self._run([
            "docker", "exec", self.container_name,
            "python3", "/tmp/poc_trigger.py",
            "--target", target,
            "--trigger-port", str(trigger_port),
            "--command", f"cat {ORACLE_DIR}/ace_canary",
        ], timeout=30)

        logger.info("PoC exit code: %d, stdout length: %d", result.returncode, len(result.stdout))
        return result.stdout, result.stderr

    def check_canary(self, stdout: str, canary: str) -> bool:
        """Check if the canary value appears in the PoC output."""
        return canary in stdout

    def stop_container(self) -> None:
        """Stop and remove the container."""
        if self.container_name:
            self._run(["docker", "stop", self.container_name])
            self._run(["docker", "rm", "-f", self.container_name])
            logger.info("Container stopped and removed: %s", self.container_name)
            self.container_id = None

    def run_full_verification(self, runs: int = 3, progress_callback=None) -> dict:
        """Run the complete verification protocol with reliability testing.

        Returns a result dict with verification status and reliability score.
        """
        def emit(event, data=None):
            if progress_callback:
                progress_callback(event, data or {})

        try:
            # Phase 1: Start container
            emit("container_starting", {"image": self.image})
            cid = self.start_container()
            emit("container_started", {"container_id": cid})

            # Phase 2-4: Run PoC N times with fresh canaries
            successes = 0
            for run_num in range(1, runs + 1):
                # Fresh canary each run
                canary = self.plant_canary()
                emit("canary_planted", {"run": run_num, "canary": canary[:16] + "..."})

                # Run PoC
                emit("poc_running", {"run": run_num, "total": runs})
                stdout, stderr = self.run_poc()

                # Check oracle
                found = self.check_canary(stdout, canary)
                if found:
                    successes += 1
                emit("poc_result", {
                    "run": run_num,
                    "canary_found": found,
                    "successes": successes,
                    "total": run_num,
                })

            # Phase 5: Result
            reliability = successes / runs if runs > 0 else 0.0
            verified = successes > 0
            result = {
                "verified": verified,
                "capability": "ACE" if verified else None,
                "reliability": reliability,
                "successes": successes,
                "runs": runs,
            }
            emit("verification_complete", result)
            return result

        finally:
            # Phase 6: Cleanup
            emit("cleanup", {})
            self.stop_container()
