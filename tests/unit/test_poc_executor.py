"""Tests for PoC executor."""

import pytest

from ndai.enclave.vuln_verify.models import (
    ExpectedOutcome,
    PoCResult,
    PoCSpec,
    ResourceLimits,
)
from ndai.enclave.vuln_verify.poc_executor import PoCExecutor


class TestPoCExecution:
    def test_simple_script(self):
        executor = PoCExecutor(enforce_rlimits=False)
        poc = PoCSpec("bash", "echo 'hello world'", timeout_sec=10)
        result = executor.execute_poc(poc)
        assert result.exit_code == 0
        assert "hello world" in result.stdout
        assert not result.timed_out

    def test_nonzero_exit(self):
        executor = PoCExecutor(enforce_rlimits=False)
        poc = PoCSpec("bash", "exit 42", timeout_sec=10)
        result = executor.execute_poc(poc)
        assert result.exit_code == 42

    def test_stderr_capture(self):
        executor = PoCExecutor(enforce_rlimits=False)
        poc = PoCSpec("bash", "echo 'err' >&2", timeout_sec=10)
        result = executor.execute_poc(poc)
        assert "err" in result.stderr

    def test_timeout(self):
        executor = PoCExecutor(ResourceLimits(max_wall_sec=2), enforce_rlimits=False)
        # Use python to avoid bash signal handling issues
        poc = PoCSpec("python3", "import time; time.sleep(60)", timeout_sec=2)
        result = executor.execute_poc(poc)
        # Should either time out or be killed by signal
        assert result.timed_out or result.signal is not None

    def test_python3_script(self):
        executor = PoCExecutor(enforce_rlimits=False)
        poc = PoCSpec("python3", "print('from python')", timeout_sec=10)
        result = executor.execute_poc(poc)
        assert result.exit_code == 0
        assert "from python" in result.stdout

    def test_output_truncation(self):
        executor = PoCExecutor(ResourceLimits(max_output_bytes=100), enforce_rlimits=False)
        poc = PoCSpec("bash", "python3 -c \"print('x' * 1000)\"", timeout_sec=10)
        result = executor.execute_poc(poc)
        assert len(result.stdout) <= 100

    def test_duration_tracked(self):
        executor = PoCExecutor(enforce_rlimits=False)
        poc = PoCSpec("bash", "sleep 0.1 && echo done", timeout_sec=10)
        result = executor.execute_poc(poc)
        assert result.duration_sec >= 0.1


class TestCheckOutcome:
    def setup_method(self):
        self.executor = PoCExecutor()

    def test_exit_code_match(self):
        result = PoCResult(exit_code=0, stdout="", stderr="", signal=None, timed_out=False, duration_sec=0.1)
        assert self.executor.check_outcome(result, ExpectedOutcome(exit_code=0)) is True
        assert self.executor.check_outcome(result, ExpectedOutcome(exit_code=1)) is False

    def test_signal_match(self):
        result = PoCResult(exit_code=139, stdout="", stderr="", signal=11, timed_out=False, duration_sec=0.1)
        assert self.executor.check_outcome(result, ExpectedOutcome(crash_signal=11)) is True
        assert self.executor.check_outcome(result, ExpectedOutcome(crash_signal=6)) is False

    def test_stdout_contains(self):
        result = PoCResult(exit_code=0, stdout="vulnerable!", stderr="", signal=None, timed_out=False, duration_sec=0.1)
        assert self.executor.check_outcome(result, ExpectedOutcome(stdout_contains="vulnerable")) is True
        assert self.executor.check_outcome(result, ExpectedOutcome(stdout_contains="safe")) is False

    def test_stderr_contains(self):
        result = PoCResult(exit_code=1, stdout="", stderr="segfault", signal=None, timed_out=False, duration_sec=0.1)
        assert self.executor.check_outcome(result, ExpectedOutcome(stderr_contains="segfault")) is True

    def test_no_criteria_returns_false(self):
        """If no expected criteria are specified, check returns False."""
        result = PoCResult(exit_code=0, stdout="", stderr="", signal=None, timed_out=False, duration_sec=0.1)
        assert self.executor.check_outcome(result, ExpectedOutcome()) is False

    def test_multiple_criteria_all_must_match(self):
        result = PoCResult(exit_code=0, stdout="ok", stderr="", signal=None, timed_out=False, duration_sec=0.1)
        # Both match
        assert self.executor.check_outcome(
            result, ExpectedOutcome(exit_code=0, stdout_contains="ok")
        ) is True
        # One fails
        assert self.executor.check_outcome(
            result, ExpectedOutcome(exit_code=1, stdout_contains="ok")
        ) is False
