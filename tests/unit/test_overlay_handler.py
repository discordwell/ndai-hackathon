"""Tests for buyer overlay handler."""

import os
import tempfile

import pytest

from ndai.enclave.vuln_verify.models import BuyerOverlay, FileReplacement
from ndai.enclave.vuln_verify.overlay_handler import OverlayError, OverlayHandler


class TestOverlayHandler:
    def test_replace_file_atomic(self):
        """File replacement should be atomic (via rename)."""
        handler = OverlayHandler()

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="test_overlay_", delete=False, mode="w"
        ) as f:
            f.write("original content")
            target_path = f.name

        try:
            fr = FileReplacement(path=target_path, content=b"replaced content")
            handler._replace_file(fr)

            with open(target_path, "rb") as f:
                assert f.read() == b"replaced content"
        finally:
            os.unlink(target_path)

    def test_replace_preserves_permissions(self):
        handler = OverlayHandler()

        with tempfile.NamedTemporaryFile(
            dir="/tmp", prefix="test_perm_", delete=False, mode="w"
        ) as f:
            f.write("original")
            target_path = f.name

        os.chmod(target_path, 0o755)

        try:
            fr = FileReplacement(path=target_path, content=b"new")
            handler._replace_file(fr)
            assert os.stat(target_path).st_mode & 0o777 == 0o755
        finally:
            os.unlink(target_path)

    def test_replace_nonexistent_directory_raises(self):
        handler = OverlayHandler()
        fr = FileReplacement(path="/nonexistent/dir/file.so", content=b"x")
        with pytest.raises(OverlayError, match="does not exist"):
            handler._replace_file(fr)

    def test_apply_overlay_validates(self):
        """Overlay with invalid paths should be rejected."""
        handler = OverlayHandler()
        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/etc/shadow", b"evil")],
        )
        with pytest.raises(OverlayError, match="validation failed"):
            handler.apply_overlay(overlay, [])

    def test_apply_overlay_path_traversal_rejected(self):
        handler = OverlayHandler()
        overlay = BuyerOverlay(
            overlay_id="test",
            file_replacements=[FileReplacement("/usr/lib/../../etc/passwd", b"evil")],
        )
        with pytest.raises(OverlayError, match="validation failed"):
            handler.apply_overlay(overlay, [])

    def test_apply_empty_overlay(self):
        """Empty overlay should succeed without error."""
        handler = OverlayHandler()
        overlay = BuyerOverlay(overlay_id="test", file_replacements=[])
        handler.apply_overlay(overlay, [])  # Should not raise

    def test_decrypt_without_keypair_raises(self):
        handler = OverlayHandler(keypair=None)
        with pytest.raises(OverlayError, match="No keypair"):
            handler.decrypt_overlay(b"encrypted data")

    def test_decrypt_overlay_roundtrip(self):
        """ECIES round-trip: an overlay encrypted to the enclave key decrypts.

        Regression for passing the EnclaveKeypair wrapper (instead of its
        .private_key) to ecies_decrypt, which raised AttributeError and broke
        every real-mode overlay decryption.
        """
        import cbor2

        from ndai.enclave.ephemeral_keys import ecies_encrypt, generate_keypair

        keypair = generate_keypair()
        payload = cbor2.dumps(
            {
                "overlay_id": "ov-1",
                "file_replacements": [{"path": "/usr/lib/libfoo.so", "content": b"patched"}],
                "pre_apply_commands": ["service foo stop"],
                "post_apply_commands": ["service foo start"],
            }
        )
        encrypted = ecies_encrypt(keypair.public_key, payload)

        handler = OverlayHandler(keypair=keypair)
        overlay = handler.decrypt_overlay(encrypted)

        assert overlay.overlay_id == "ov-1"
        assert len(overlay.file_replacements) == 1
        assert overlay.file_replacements[0].path == "/usr/lib/libfoo.so"
        assert overlay.file_replacements[0].content == b"patched"
        assert overlay.pre_apply_commands == ["service foo stop"]
        assert overlay.post_apply_commands == ["service foo start"]
