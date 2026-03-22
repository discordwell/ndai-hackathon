"""Tests for bounty schema validation (Pydantic models)."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ndai:ndai@localhost:5432/ndai")

import pytest
from pydantic import ValidationError

from ndai.api.schemas.bounty import (
    BountyCreateRequest,
    BountyRespondRequest,
    BountyResponse,
    BountyListingResponse,
)


class TestBountyCreateRequest:
    def test_bounty_create_valid(self):
        """Valid BountyCreateRequest instantiates without error."""
        req = BountyCreateRequest(
            target_software="Apache httpd",
            target_version_constraint=">=2.4.0,<2.4.58",
            desired_impact="RCE",
            desired_vulnerability_class="CWE-787",
            budget_eth=5.0,
            description="Looking for pre-auth RCE in mod_proxy",
            deadline="2025-12-31T23:59:59Z",
        )
        assert req.target_software == "Apache httpd"
        assert req.budget_eth == 5.0
        assert req.desired_impact == "RCE"

    def test_bounty_create_minimal_fields(self):
        """Only required fields — optional fields default to None."""
        req = BountyCreateRequest(
            target_software="OpenSSL",
            desired_impact="InfoLeak",
            budget_eth=1.5,
            description="Heartbleed-class memory disclosure",
        )
        assert req.target_version_constraint is None
        assert req.desired_vulnerability_class is None
        assert req.deadline is None

    def test_bounty_create_negative_budget_rejected(self):
        """budget_eth <= 0 is rejected by the gt=0.0 constraint."""
        with pytest.raises(ValidationError) as exc_info:
            BountyCreateRequest(
                target_software="nginx",
                desired_impact="DoS",
                budget_eth=-1.0,
                description="Negative budget should fail",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("budget_eth",) for e in errors)

    def test_bounty_create_zero_budget_rejected(self):
        """budget_eth == 0 is also rejected (gt=0.0 means strictly greater)."""
        with pytest.raises(ValidationError) as exc_info:
            BountyCreateRequest(
                target_software="nginx",
                desired_impact="DoS",
                budget_eth=0.0,
                description="Zero budget should fail",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("budget_eth",) for e in errors)

    def test_bounty_create_invalid_impact_type(self):
        """desired_impact is a free-form str in the schema — no enum validation.

        This test documents the current behavior: any string is accepted.
        If the field is later changed to a Literal/Enum, this test should be
        updated to assert a ValidationError for invalid values.
        """
        # Currently accepted because desired_impact is just `str`
        req = BountyCreateRequest(
            target_software="curl",
            desired_impact="INVALID_TYPE",
            budget_eth=2.0,
            description="Testing invalid impact type",
        )
        assert req.desired_impact == "INVALID_TYPE"


class TestBountyRespondRequest:
    def test_bounty_respond_valid(self):
        """Valid BountyRespondRequest instantiates without error."""
        req = BountyRespondRequest(
            target_software="Apache httpd",
            target_version="2.4.57",
            vulnerability_class="CWE-787",
            impact_type="RCE",
            affected_component="mod_proxy",
            anonymized_summary="Stack buffer overflow in proxy header parsing",
            cvss_self_assessed=9.8,
            asking_price_eth=10.0,
            discovery_date="2025-01-15",
        )
        assert req.target_software == "Apache httpd"
        assert req.cvss_self_assessed == 9.8
        assert req.asking_price_eth == 10.0

    def test_bounty_respond_minimal_fields(self):
        """Only required fields — optional fields default to None."""
        req = BountyRespondRequest(
            target_software="OpenSSL",
            target_version="3.1.4",
            vulnerability_class="CWE-125",
            impact_type="InfoLeak",
            cvss_self_assessed=7.5,
            asking_price_eth=3.0,
            discovery_date="2025-06-01",
        )
        assert req.affected_component is None
        assert req.anonymized_summary is None

    def test_bounty_respond_cvss_out_of_range(self):
        """cvss_self_assessed must be 0.0-10.0 (ge=0.0, le=10.0)."""
        with pytest.raises(ValidationError) as exc_info:
            BountyRespondRequest(
                target_software="nginx",
                target_version="1.25.0",
                vulnerability_class="CWE-400",
                impact_type="DoS",
                cvss_self_assessed=11.0,  # Out of range
                asking_price_eth=1.0,
                discovery_date="2025-03-01",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("cvss_self_assessed",) for e in errors)

    def test_bounty_respond_negative_cvss_rejected(self):
        """Negative CVSS score is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            BountyRespondRequest(
                target_software="nginx",
                target_version="1.25.0",
                vulnerability_class="CWE-400",
                impact_type="DoS",
                cvss_self_assessed=-0.1,
                asking_price_eth=1.0,
                discovery_date="2025-03-01",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("cvss_self_assessed",) for e in errors)

    def test_bounty_respond_zero_price_rejected(self):
        """asking_price_eth must be > 0 (gt=0.0)."""
        with pytest.raises(ValidationError) as exc_info:
            BountyRespondRequest(
                target_software="nginx",
                target_version="1.25.0",
                vulnerability_class="CWE-400",
                impact_type="DoS",
                cvss_self_assessed=5.0,
                asking_price_eth=0.0,
                discovery_date="2025-03-01",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("asking_price_eth",) for e in errors)

    def test_bounty_respond_boundary_cvss_values(self):
        """CVSS boundary values 0.0 and 10.0 should be accepted (ge/le)."""
        req_zero = BountyRespondRequest(
            target_software="test",
            target_version="1.0",
            vulnerability_class="CWE-000",
            impact_type="DoS",
            cvss_self_assessed=0.0,
            asking_price_eth=1.0,
            discovery_date="2025-01-01",
        )
        assert req_zero.cvss_self_assessed == 0.0

        req_ten = BountyRespondRequest(
            target_software="test",
            target_version="1.0",
            vulnerability_class="CWE-000",
            impact_type="RCE",
            cvss_self_assessed=10.0,
            asking_price_eth=1.0,
            discovery_date="2025-01-01",
        )
        assert req_ten.cvss_self_assessed == 10.0
