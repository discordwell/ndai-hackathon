"""Tests for the deterministic policy engine and LLM-powered generator."""

import json
from unittest.mock import MagicMock

import pytest

from ndai.enclave.policy.engine import (
    Policy,
    PolicyConstraint,
    PolicyReport,
    FieldResult,
    enforce,
    enforce_all,
    hash_policy,
)


class TestEnforce:
    def test_valid_string_passes(self):
        c = PolicyConstraint(field="summary", max_length=200, rationale="keep it short")
        result = enforce(c, "A short summary of the meeting.")
        assert result.passed is True
        assert result.violations == []

    def test_url_denied(self):
        c = PolicyConstraint(
            field="result",
            deny_patterns=[r"https?://\S+"],
            rationale="no URLs allowed",
        )
        result = enforce(c, "Check out https://evil.com for details")
        assert result.passed is False
        assert any("denied pattern" in v.lower() for v in result.violations)

    def test_max_length_enforced(self):
        c = PolicyConstraint(field="text", max_length=10)
        result = enforce(c, "This is way too long for the limit")
        assert result.passed is False
        assert any("max length" in v.lower() for v in result.violations)

    def test_pattern_must_match(self):
        c = PolicyConstraint(field="sentiment", pattern=r"(positive|neutral|negative)")
        assert enforce(c, "positive").passed is True
        assert enforce(c, "unknown").passed is False

    def test_multiple_violations(self):
        c = PolicyConstraint(
            field="text",
            max_length=5,
            deny_patterns=[r"bad"],
        )
        result = enforce(c, "bad and long")
        assert result.passed is False
        assert len(result.violations) == 2

    def test_empty_constraint_passes(self):
        c = PolicyConstraint(field="anything")
        result = enforce(c, "literally anything goes")
        assert result.passed is True


class TestEnforceAll:
    def test_all_pass(self):
        policy = Policy(
            task_type="recall",
            constraints=[
                PolicyConstraint(field="result", max_length=2000),
                PolicyConstraint(field="status", pattern=r"(ok|error)"),
            ],
        )
        report = enforce_all(policy, {"result": "Done", "status": "ok"})
        assert report.all_passed is True
        assert len(report.results) == 2

    def test_partial_failure(self):
        policy = Policy(
            task_type="recall",
            constraints=[
                PolicyConstraint(field="result", max_length=5),
                PolicyConstraint(field="status", pattern=r"ok"),
            ],
        )
        report = enforce_all(policy, {"result": "Way too long", "status": "ok"})
        assert report.all_passed is False
        assert report.results[0].passed is False
        assert report.results[1].passed is True

    def test_missing_field_fails(self):
        policy = Policy(
            task_type="recall",
            constraints=[PolicyConstraint(field="required_field")],
        )
        report = enforce_all(policy, {})
        assert report.all_passed is False
        assert "Missing" in report.results[0].violations[0]

    def test_multiple_fields(self):
        policy = Policy(
            task_type="props",
            constraints=[
                PolicyConstraint(field="summary", max_length=500),
                PolicyConstraint(
                    field="sentiment",
                    pattern=r"(positive|neutral|negative)",
                ),
                PolicyConstraint(
                    field="action_items",
                    deny_patterns=[r"https?://\S+"],
                ),
            ],
        )
        fields = {
            "summary": "Team is on track.",
            "sentiment": "positive",
            "action_items": "Review PR #42, update docs",
        }
        report = enforce_all(policy, fields)
        assert report.all_passed is True


class TestHashPolicy:
    def test_determinism(self):
        policy = Policy(
            task_type="recall",
            constraints=[
                PolicyConstraint(field="a", max_length=10),
                PolicyConstraint(field="b", deny_patterns=["x"]),
            ],
        )
        h1 = hash_policy(policy)
        h2 = hash_policy(policy)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_different_policies_different_hashes(self):
        p1 = Policy(task_type="recall", constraints=[PolicyConstraint(field="a")])
        p2 = Policy(task_type="props", constraints=[PolicyConstraint(field="a")])
        assert hash_policy(p1) != hash_policy(p2)

    def test_hash_ignores_generated_at(self):
        """generated_at is metadata, not part of the canonical hash."""
        p1 = Policy(task_type="t", constraints=[], generated_at="2024-01-01")
        p2 = Policy(task_type="t", constraints=[], generated_at="2025-12-31")
        assert hash_policy(p1) == hash_policy(p2)


# ── Generator tests ──

from ndai.enclave.policy.generator import generate_policy


class TestGeneratePolicy:
    def test_llm_generated_constraints_merged(self):
        mock_client = MagicMock()
        llm_response = json.dumps([
            {
                "field": "extra_field",
                "deny_patterns": [r"secret"],
                "max_length": 100,
                "rationale": "LLM-generated constraint",
            }
        ])
        mock_client.create_message.return_value = "resp"
        mock_client.extract_text.return_value = llm_response

        policy = generate_policy("recall", "check API status", mock_client)
        assert policy.task_type == "recall"
        # Should have default recall constraints + the extra_field from LLM
        fields = [c.field for c in policy.constraints]
        assert "result" in fields  # default
        assert "extra_field" in fields  # LLM-generated

    def test_fallback_on_bad_json(self):
        mock_client = MagicMock()
        mock_client.create_message.return_value = "resp"
        mock_client.extract_text.return_value = "not valid json at all"

        policy = generate_policy("recall", "some context", mock_client)
        assert policy.task_type == "recall"
        # Should still have defaults
        assert len(policy.constraints) > 0
        assert policy.constraints[0].field == "result"

    def test_fallback_on_llm_exception(self):
        mock_client = MagicMock()
        mock_client.create_message.side_effect = RuntimeError("API down")

        policy = generate_policy("props", "meeting about roadmap", mock_client)
        assert policy.task_type == "props"
        fields = [c.field for c in policy.constraints]
        assert "executive_summary" in fields
        assert "sentiment" in fields

    def test_defaults_not_overridden_by_llm(self):
        """LLM constraints for fields covered by defaults should be ignored."""
        mock_client = MagicMock()
        llm_response = json.dumps([
            {"field": "result", "max_length": 99999, "rationale": "trying to weaken defaults"},
        ])
        mock_client.create_message.return_value = "resp"
        mock_client.extract_text.return_value = llm_response

        policy = generate_policy("recall", "context", mock_client)
        result_constraints = [c for c in policy.constraints if c.field == "result"]
        assert len(result_constraints) == 1
        assert result_constraints[0].max_length == 2000  # default, not 99999
