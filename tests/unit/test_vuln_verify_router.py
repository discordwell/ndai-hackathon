"""Regression tests for the vuln-verify HTTP router and its data-model contracts.

These lock in the fix for a half-finished rename (ExpectedOutcome → ClaimedCapability,
CapabilityResult → boolean ``*_matches``) that left the entire sealed-0day-verification
API non-functional:

* ``VerificationResultRecord`` had drifted away from the columns its own migration
  created (``unpatched_matches``/``patched_matches`` booleans), so the ORM model could
  not be persisted at all.
* The router read ``request.expected_outcome`` / ``record.expected_outcome`` and built a
  ``VerificationResultResponse`` from capability fields that no longer existed.

Every endpoint crashed before the fix; none had any HTTP-level coverage, which is why
the breakage went unnoticed. The pure-contract tests below would each have failed
against the broken code, and the TestClient tests exercise the full request → record →
response path.
"""

import os
import uuid
from types import SimpleNamespace

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ndai:ndai@localhost:5432/ndai")

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from ndai.api.dependencies import get_current_user
from ndai.api.routers import vuln_verify
from ndai.api.schemas.vuln_verify import VerificationResultResponse
from ndai.db.session import get_db
from ndai.enclave.vuln_verify.models import CapabilityLevel
from ndai.models.vuln_verify import TargetSpecRecord, VerificationResultRecord
from ndai.tee.vuln_verify_orchestrator import VerificationOutcome

# ── Pure data-model / schema contract tests (no DB, no HTTP) ──


class TestDataModelContract:
    def test_verification_result_record_accepts_matches_kwargs(self):
        """The router constructs the record with boolean ``*_matches`` kwargs.

        Before the fix the ORM model exposed ``unpatched_result``/``verified_level``
        instead, so this construction raised ``TypeError``.
        """
        record = VerificationResultRecord(
            id=uuid.uuid4(),
            spec_id=uuid.uuid4(),
            agreement_id=uuid.uuid4(),
            buyer_id=uuid.uuid4(),
            unpatched_matches=True,
            patched_matches=False,
            overlap_detected=True,
            verification_chain_hash="a" * 64,
            attestation_pcr0="pcr0",
        )
        assert record.unpatched_matches is True
        assert record.patched_matches is False

    def test_record_columns_match_migration(self):
        """ORM columns must match the e5f6a7b8c9d0 migration exactly (no drift)."""
        cols = {c.name for c in VerificationResultRecord.__table__.columns}
        assert {"unpatched_matches", "patched_matches", "unpatched_exit_code",
                "patched_exit_code"} <= cols
        # The drifted columns that never existed in the DB must be gone.
        assert "unpatched_result" not in cols
        assert "verified_level" not in cols

    def test_target_spec_claimed_capability_maps_to_legacy_column(self):
        """``claimed_capability`` attribute is persisted in the ``expected_outcome`` column."""
        record = TargetSpecRecord(
            id=uuid.uuid4(),
            vulnerability_id=uuid.uuid4(),
            base_image="ubuntu:22.04",
            packages=[],
            claimed_capability={"level": "ace", "reliability_runs": 3},
        )
        assert record.claimed_capability == {"level": "ace", "reliability_runs": 3}
        assert TargetSpecRecord.__table__.columns["expected_outcome"] is not None
        assert not hasattr(TargetSpecRecord, "expected_outcome")

    def test_response_builds_from_orchestrator_outcome(self):
        """The response schema accepts exactly the keys the router emits from an outcome."""
        outcome = VerificationOutcome(
            unpatched_matches=True,
            patched_matches=None,
            overlap_detected=False,
            verification_chain_hash="b" * 64,
            pcr0="deadbeef",
            timestamp="2026-01-01T00:00:00Z",
        )
        result_dict = {
            "unpatched_matches": outcome.unpatched_matches,
            "patched_matches": outcome.patched_matches,
            "overlap_detected": outcome.overlap_detected,
            "verification_chain_hash": outcome.verification_chain_hash,
            "pcr0": outcome.pcr0,
        }
        resp = VerificationResultResponse(**result_dict)
        assert resp.unpatched_matches is True
        assert resp.patched_matches is None
        assert resp.pcr0 == "deadbeef"

    def test_claimed_capability_rehydration_round_trip(self):
        """A stored ClaimedCapabilitySchema dict rehydrates with the level coerced to enum."""
        cap = vuln_verify._claimed_capability_from_record(
            {"level": "lpe", "crash_signal": None, "exit_code": None, "reliability_runs": 7}
        )
        assert cap.level is CapabilityLevel.LPE
        assert cap.reliability_runs == 7

    def test_claimed_capability_rehydration_defaults_on_empty(self):
        """Missing/empty stored capability falls back to a safe CRASH default."""
        cap = vuln_verify._claimed_capability_from_record(None)
        assert cap.level is CapabilityLevel.CRASH
        assert cap.reliability_runs == 3


# ── HTTP-level tests with dependency overrides ──


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    """Minimal async-session stand-in for the router's DB dependency."""

    def __init__(self, execute_result=None):
        self.added: list = []
        self._execute_result = execute_result

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    async def execute(self, *args, **kwargs):
        return _FakeResult(self._execute_result)


@pytest.fixture
def app_client():
    app = FastAPI()
    app.include_router(vuln_verify.router, prefix="/api/v1/vuln-verify")
    client = TestClient(app)
    yield app, client
    app.dependency_overrides.clear()
    vuln_verify._verify_statuses.clear()
    vuln_verify._build_statuses.clear()


def _valid_spec_payload(vuln_id: str) -> dict:
    return {
        "vulnerability_id": vuln_id,
        "base_image": "ubuntu:22.04",
        "packages": [{"name": "apache2", "version": "2.4.52-1ubuntu4.3"}],
        "config_files": [],
        "services": [],
        "poc": {"script_type": "bash", "script_content": "echo pwn", "timeout_sec": 60},
        "claimed_capability": {"level": "ace", "reliability_runs": 3},
    }


class TestCreateTargetSpec:
    def test_persists_claimed_capability(self, app_client, monkeypatch):
        app, client = app_client
        seller_id = str(uuid.uuid4())
        vuln_id = uuid.uuid4()
        vuln = SimpleNamespace(id=vuln_id, seller_id=seller_id)

        async def _fake_get_vulnerability(db, vid):
            return vuln

        monkeypatch.setattr(
            "ndai.db.repositories.get_vulnerability", _fake_get_vulnerability
        )
        session = _FakeSession()
        app.dependency_overrides[get_current_user] = lambda: seller_id
        app.dependency_overrides[get_db] = lambda: session

        resp = client.post(
            "/api/v1/vuln-verify/target-specs", json=_valid_spec_payload(str(vuln_id))
        )

        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["base_image"] == "ubuntu:22.04"
        assert body["package_count"] == 1
        # The record stored the claimed-capability spec (the bug read a nonexistent field).
        assert len(session.added) == 1
        stored = session.added[0].claimed_capability
        assert stored["level"] == "ace"
        assert stored["reliability_runs"] == 3

    def test_rejects_non_seller(self, app_client, monkeypatch):
        app, client = app_client
        vuln_id = uuid.uuid4()
        vuln = SimpleNamespace(id=vuln_id, seller_id=str(uuid.uuid4()))  # not the caller

        async def _fake_get_vulnerability(db, vid):
            return vuln

        monkeypatch.setattr(
            "ndai.db.repositories.get_vulnerability", _fake_get_vulnerability
        )
        app.dependency_overrides[get_current_user] = lambda: str(uuid.uuid4())
        app.dependency_overrides[get_db] = lambda: _FakeSession()

        resp = client.post(
            "/api/v1/vuln-verify/target-specs", json=_valid_spec_payload(str(vuln_id))
        )
        assert resp.status_code == 403

    def test_rejects_invalid_capability_level(self, app_client):
        """An unknown capability level is rejected at the boundary (422), not deep in a task.

        Without the Literal constraint the bad value would persist and only blow up later
        when the enclave build/verify task calls ``CapabilityLevel(level)``.
        """
        app, client = app_client
        app.dependency_overrides[get_current_user] = lambda: str(uuid.uuid4())
        app.dependency_overrides[get_db] = lambda: _FakeSession()

        payload = _valid_spec_payload(str(uuid.uuid4()))
        payload["claimed_capability"]["level"] = "totally-bogus-level"
        resp = client.post("/api/v1/vuln-verify/target-specs", json=payload)
        assert resp.status_code == 422


class TestGetVerificationResult:
    def test_in_memory_returns_boolean_verdicts(self, app_client):
        app, client = app_client
        agreement_id = str(uuid.uuid4())
        vuln_verify._verify_statuses[agreement_id] = {
            "status": "completed",
            "result": {
                "unpatched_matches": True,
                "patched_matches": False,
                "overlap_detected": True,
                "verification_chain_hash": "c" * 64,
                "pcr0": "cafe",
            },
        }
        app.dependency_overrides[get_current_user] = lambda: str(uuid.uuid4())
        app.dependency_overrides[get_db] = lambda: _FakeSession()

        resp = client.get(f"/api/v1/vuln-verify/{agreement_id}/result")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["unpatched_matches"] is True
        assert body["patched_matches"] is False
        assert body["pcr0"] == "cafe"

    def test_db_fallback_maps_record_booleans(self, app_client):
        app, client = app_client
        agreement_id = str(uuid.uuid4())

        record = VerificationResultRecord(
            id=uuid.uuid4(),
            spec_id=uuid.uuid4(),
            agreement_id=uuid.UUID(agreement_id),
            buyer_id=uuid.uuid4(),
            unpatched_matches=True,
            patched_matches=None,
            overlap_detected=False,
            verification_chain_hash="d" * 64,
            attestation_pcr0="pcr0hex",
        )
        app.dependency_overrides[get_current_user] = lambda: str(uuid.uuid4())
        app.dependency_overrides[get_db] = lambda: _FakeSession(execute_result=record)

        resp = client.get(f"/api/v1/vuln-verify/{agreement_id}/result")
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["unpatched_matches"] is True
        assert body["patched_matches"] is None
        assert body["pcr0"] == "pcr0hex"

    def test_missing_result_returns_404(self, app_client):
        app, client = app_client
        agreement_id = str(uuid.uuid4())
        app.dependency_overrides[get_current_user] = lambda: str(uuid.uuid4())
        app.dependency_overrides[get_db] = lambda: _FakeSession(execute_result=None)

        resp = client.get(f"/api/v1/vuln-verify/{agreement_id}/result")
        assert resp.status_code == 404
