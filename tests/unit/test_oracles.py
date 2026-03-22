"""Tests for the capability oracle system."""

import os
import tempfile

import pytest

from ndai.enclave.vuln_verify.models import CapabilityLevel, CapabilityResult, PoCResult
from ndai.enclave.vuln_verify.oracles import OracleManager


@pytest.fixture
def oracle_dir():
    """Create a temp directory for oracle files."""
    d = tempfile.mkdtemp(prefix="ndai_oracle_test_")
    yield d
    import shutil
    shutil.rmtree(d, ignore_errors=True)


class TestOraclePlanting:
    def test_plant_ace_creates_canary(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        canary_path = os.path.join(oracle_dir, "ace_canary")
        assert os.path.exists(canary_path)
        with open(canary_path) as f:
            canary = f.read()
        assert len(canary) == 64  # 32 bytes hex = 64 chars
        oracle.cleanup()

    def test_plant_lpe_creates_root_only_canary(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.LPE, service_user="www-data")
        # Both ACE and LPE canaries should exist
        assert os.path.exists(os.path.join(oracle_dir, "ace_canary"))
        assert os.path.exists(os.path.join(oracle_dir, "lpe_canary"))
        # LPE canary should be root-only (0600)
        mode = os.stat(os.path.join(oracle_dir, "lpe_canary")).st_mode & 0o777
        assert mode == 0o600
        oracle.cleanup()

    def test_plant_info_leak_sets_env(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.INFO_LEAK, service_user="www-data")
        assert "NDAI_INFO_CANARY" in os.environ
        assert len(os.environ["NDAI_INFO_CANARY"]) == 64
        oracle.cleanup()
        # Clean up env
        os.environ.pop("NDAI_INFO_CANARY", None)

    def test_plant_callback_creates_token_file(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.CALLBACK, service_user="www-data")
        token_path = os.path.join(oracle_dir, "callback_token")
        assert os.path.exists(token_path)
        with open(token_path) as f:
            content = f.read()
        # Format: 127.0.0.1:PORT:TOKEN
        parts = content.split(":")
        assert parts[0] == "127.0.0.1"
        assert int(parts[1]) > 0  # Valid port
        oracle.cleanup()

    def test_plant_crash_no_files(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.CRASH, service_user="www-data")
        # Crash oracle doesn't need canary files
        assert not os.path.exists(os.path.join(oracle_dir, "ace_canary"))
        oracle.cleanup()

    def test_canaries_are_unique(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.LPE, service_user="www-data")
        ace_canary = oracle._canaries["ace"]
        lpe_canary = oracle._canaries["lpe"]
        assert ace_canary != lpe_canary
        oracle.cleanup()

    def test_fresh_canaries_each_plant(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        first = oracle._canaries["ace"]
        oracle.cleanup()
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        second = oracle._canaries["ace"]
        assert first != second
        oracle.cleanup()


class TestOracleChecking:
    def test_ace_canary_found(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        canary = oracle._canaries["ace"]

        result = PoCResult(
            exit_code=0, stdout=f"got it: {canary}", stderr="",
            signal=None, timed_out=False, duration_sec=1.0,
        )
        cap = oracle.check_result(result, CapabilityLevel.ACE)
        assert cap.ace_canary_found is True
        assert cap.verified_level == CapabilityLevel.ACE
        oracle.cleanup()

    def test_ace_canary_not_found(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")

        result = PoCResult(
            exit_code=0, stdout="no canary here", stderr="",
            signal=None, timed_out=False, duration_sec=1.0,
        )
        cap = oracle.check_result(result, CapabilityLevel.ACE)
        assert cap.ace_canary_found is False
        assert cap.verified_level is None
        oracle.cleanup()

    def test_lpe_canary_found(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.LPE, service_user="www-data")
        lpe_canary = oracle._canaries["lpe"]

        result = PoCResult(
            exit_code=0, stdout=f"root: {lpe_canary}", stderr="",
            signal=None, timed_out=False, duration_sec=1.0,
        )
        cap = oracle.check_result(result, CapabilityLevel.LPE)
        assert cap.lpe_canary_found is True
        assert cap.verified_level == CapabilityLevel.LPE
        oracle.cleanup()

    def test_crash_detected(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.CRASH, service_user="www-data")

        result = PoCResult(
            exit_code=139, stdout="", stderr="",
            signal=11, timed_out=False, duration_sec=0.5,
        )
        cap = oracle.check_result(result, CapabilityLevel.CRASH)
        assert cap.crash_detected is True
        assert cap.verified_level == CapabilityLevel.CRASH
        oracle.cleanup()

    def test_dos_detected(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.DOS, service_user="www-data")

        result = PoCResult(
            exit_code=0, stdout="", stderr="",
            signal=None, timed_out=True, duration_sec=120.0,
        )
        cap = oracle.check_result(result, CapabilityLevel.DOS)
        assert cap.dos_detected is True
        assert cap.verified_level == CapabilityLevel.DOS
        oracle.cleanup()

    def test_claimed_ace_only_got_crash(self, oracle_dir):
        """Seller claims ACE but exploit only crashes the target."""
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")

        result = PoCResult(
            exit_code=139, stdout="", stderr="segfault",
            signal=11, timed_out=False, duration_sec=0.5,
        )
        cap = oracle.check_result(result, CapabilityLevel.ACE)
        assert cap.claimed == CapabilityLevel.ACE
        assert cap.verified_level == CapabilityLevel.CRASH  # Downgraded
        assert cap.ace_canary_found is False
        assert cap.crash_detected is True
        oracle.cleanup()

    def test_nothing_detected(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")

        result = PoCResult(
            exit_code=0, stdout="clean exit", stderr="",
            signal=None, timed_out=False, duration_sec=1.0,
        )
        cap = oracle.check_result(result, CapabilityLevel.ACE)
        assert cap.verified_level is None
        oracle.cleanup()

    def test_canary_in_stderr(self, oracle_dir):
        """Canary can appear in stderr too."""
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        canary = oracle._canaries["ace"]

        result = PoCResult(
            exit_code=0, stdout="", stderr=f"debug: {canary}",
            signal=None, timed_out=False, duration_sec=1.0,
        )
        cap = oracle.check_result(result, CapabilityLevel.ACE)
        assert cap.ace_canary_found is True
        oracle.cleanup()


class TestCleanup:
    def test_cleanup_removes_dir(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        oracle.cleanup()
        assert not os.path.exists(oracle_dir)

    def test_double_cleanup_safe(self, oracle_dir):
        oracle = OracleManager(oracle_dir=oracle_dir)
        oracle.plant_oracles(CapabilityLevel.ACE, service_user="www-data")
        oracle.cleanup()
        oracle.cleanup()  # Should not raise
