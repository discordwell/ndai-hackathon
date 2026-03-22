"""Buyer overlay handler — decrypts and applies file replacements inside the enclave.

The buyer's overlay is ECIES-encrypted to the enclave's ephemeral public key.
After decryption, files are atomically replaced in the target environment.
The seller never sees the overlay contents.
"""

import logging
import os
import subprocess
import tempfile

import cbor2

from ndai.enclave.vuln_verify.models import BuyerOverlay, FileReplacement, ServiceSpec
from ndai.enclave.vuln_verify.security import validate_buyer_overlay

logger = logging.getLogger(__name__)


class OverlayError(Exception):
    """Error during overlay processing."""


class OverlayHandler:
    """Receives and applies buyer overlay inside the enclave."""

    def __init__(self, keypair=None):
        """Initialize with optional enclave keypair for ECIES decryption."""
        self._keypair = keypair

    def decrypt_overlay(self, encrypted_payload: bytes) -> BuyerOverlay:
        """Decrypt ECIES-encrypted overlay using enclave's ephemeral key.

        The payload format matches the existing ECIES scheme from ephemeral_keys.py:
        [parent_ephemeral_pubkey_DER | nonce(12) | ciphertext | tag(16)]

        The decrypted payload is CBOR-encoded BuyerOverlay.
        """
        if self._keypair is None:
            raise OverlayError("No keypair available for decryption")

        from ndai.enclave.ephemeral_keys import ecies_decrypt
        plaintext = ecies_decrypt(self._keypair, encrypted_payload)

        # Decode CBOR to dict, then construct BuyerOverlay
        data = cbor2.loads(plaintext)
        return BuyerOverlay(
            overlay_id=data["overlay_id"],
            file_replacements=[
                FileReplacement(path=fr["path"], content=fr["content"])
                for fr in data.get("file_replacements", [])
            ],
            pre_apply_commands=data.get("pre_apply_commands", []),
            post_apply_commands=data.get("post_apply_commands", []),
        )

    def apply_overlay(self, overlay: BuyerOverlay, services: list[ServiceSpec]) -> None:
        """Stop services → replace files → restart services.

        File replacement is atomic: write to tempfile in same directory,
        then os.rename() over the target.
        """
        # Validate overlay before applying
        errors = validate_buyer_overlay(overlay)
        if errors:
            raise OverlayError(f"Overlay validation failed: {'; '.join(errors)}")

        # Pre-apply commands (typically service stops)
        for cmd in overlay.pre_apply_commands:
            logger.info("Pre-apply: %s", cmd)
            self._run_command(cmd)

        # Replace files atomically
        for fr in overlay.file_replacements:
            self._replace_file(fr)

        # Post-apply commands (typically service restarts)
        for cmd in overlay.post_apply_commands:
            logger.info("Post-apply: %s", cmd)
            self._run_command(cmd)

        logger.info(
            "Overlay applied: %d files replaced",
            len(overlay.file_replacements),
        )

    def _replace_file(self, replacement: FileReplacement) -> None:
        """Atomically replace a single file."""
        target_path = replacement.path

        # Verify the target directory exists
        target_dir = os.path.dirname(target_path)
        if not os.path.isdir(target_dir):
            raise OverlayError(f"Target directory does not exist: {target_dir}")

        # Write to temp file in same directory (for atomic rename)
        fd, tmp_path = tempfile.mkstemp(dir=target_dir, prefix=".overlay_")
        try:
            os.write(fd, replacement.content)
            os.close(fd)

            # Preserve original permissions if file exists
            if os.path.exists(target_path):
                st = os.stat(target_path)
                os.chmod(tmp_path, st.st_mode)

            # Atomic rename
            os.rename(tmp_path, target_path)
            logger.info("Replaced: %s (%d bytes)", target_path, len(replacement.content))
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _run_command(self, cmd: str) -> None:
        """Run a validated command (service start/stop only)."""
        try:
            result = subprocess.run(
                cmd, shell=True, timeout=30,
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                logger.warning("Command failed: %s → %s", cmd, result.stderr[:200])
        except subprocess.TimeoutExpired:
            logger.warning("Command timed out: %s", cmd)
