"""Deterministic policy enforcer — no LLM, pure constraint validation.

Implements the Conseca pattern: LLM generates constraints (in generator.py),
but enforcement is deterministic regex matching + bounds checking.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class PolicyConstraint:
    """A single enforceable constraint on a named field."""
    field: str
    pattern: str | None = None          # regex the value MUST match (fullmatch)
    deny_patterns: list[str] = field(default_factory=list)  # regexes that MUST NOT match
    max_length: int | None = None
    rationale: str = ""


@dataclass
class FieldResult:
    """Result of enforcing one constraint against a value."""
    field: str
    passed: bool
    violations: list[str] = field(default_factory=list)


@dataclass
class PolicyReport:
    """Aggregate enforcement result for all constraints."""
    all_passed: bool
    results: list[FieldResult]
    policy_hash: str


@dataclass
class Policy:
    """A complete policy: task type + list of constraints + metadata."""
    task_type: str
    constraints: list[PolicyConstraint]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    context_summary: str = ""


def hash_policy(policy: Policy) -> str:
    """SHA-256 of the canonical JSON representation of a policy."""
    canonical = json.dumps(
        {
            "task_type": policy.task_type,
            "constraints": [
                {
                    "field": c.field,
                    "pattern": c.pattern,
                    "deny_patterns": c.deny_patterns,
                    "max_length": c.max_length,
                    "rationale": c.rationale,
                }
                for c in policy.constraints
            ],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def enforce(constraint: PolicyConstraint, value: str) -> FieldResult:
    """Enforce a single constraint against a value. Returns FieldResult."""
    violations: list[str] = []

    # Max length check
    if constraint.max_length is not None and len(value) > constraint.max_length:
        violations.append(
            f"Exceeds max length: {len(value)} > {constraint.max_length}"
        )

    # Pattern match (must match entire value)
    if constraint.pattern:
        try:
            if not re.fullmatch(constraint.pattern, value, re.DOTALL):
                violations.append(f"Does not match required pattern: {constraint.pattern}")
        except re.error as e:
            violations.append(f"Invalid pattern '{constraint.pattern}': {e}")

    # Deny patterns (must NOT match anywhere in value)
    for deny in constraint.deny_patterns:
        try:
            if re.search(deny, value, re.IGNORECASE):
                violations.append(f"Matches denied pattern: {deny}")
        except re.error as e:
            violations.append(f"Invalid deny pattern '{deny}': {e}")

    return FieldResult(
        field=constraint.field,
        passed=len(violations) == 0,
        violations=violations,
    )


def enforce_all(policy: Policy, fields: dict[str, str]) -> PolicyReport:
    """Enforce all constraints in a policy against the given field values.

    Each constraint is checked against the corresponding field value.
    Constraints for fields not present in the dict produce a 'missing field' violation.
    """
    p_hash = hash_policy(policy)
    results: list[FieldResult] = []

    for constraint in policy.constraints:
        value = fields.get(constraint.field)
        if value is None:
            results.append(FieldResult(
                field=constraint.field,
                passed=False,
                violations=[f"Missing required field: {constraint.field}"],
            ))
        else:
            results.append(enforce(constraint, value))

    return PolicyReport(
        all_passed=all(r.passed for r in results),
        results=results,
        policy_hash=p_hash,
    )
