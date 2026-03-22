"""Unit tests for known targets, verification proposals, and badges."""

import uuid
from datetime import datetime, timezone

import pytest

from ndai.api.schemas.known_target import (
    BadgePurchaseRequest,
    DepositConfirmRequest,
    KnownTargetResponse,
    ProposalCreateRequest,
    ProposalResponse,
)
from ndai.models.known_target import KnownTarget, TargetBuild
from ndai.models.verification_proposal import VerificationProposal
from ndai.models.zk_identity import VulnIdentity


# ── Model construction ──


class TestKnownTargetModel:
    def test_create_known_target(self):
        target = KnownTarget(
            slug="chrome-linux",
            display_name="Google Chrome (Linux)",
            platform="linux",
            current_version="124.0.6367.91",
            verification_method="nitro",
            base_image="ubuntu:22.04",
            poc_script_type="html",
            poc_instructions="Submit an HTML exploit.",
            escrow_amount_usd=100,
            icon_emoji="\U0001f310",
        )
        assert target.slug == "chrome-linux"
        assert target.platform == "linux"
        assert target.verification_method == "nitro"
        assert target.escrow_amount_usd == 100

    def test_create_target_build(self):
        build = TargetBuild(
            target_id=uuid.uuid4(),
            version="124.0.6367.91",
            build_type="eif",
            cache_key="abc123def456",
            artifact_path="/opt/ndai/eifs/chrome-124-abc123.eif",
            status="ready",
        )
        assert build.build_type == "eif"
        assert build.status == "ready"

    def test_windows_target_no_base_image(self):
        target = KnownTarget(
            slug="windows-server",
            display_name="Windows Server 2022",
            platform="windows",
            current_version="10.0.20348",
            verification_method="ec2_windows",
            base_image=None,
            poc_script_type="powershell",
            poc_instructions="Submit a PowerShell exploit.",
            platform_config_json={"ami_id": "ami-12345"},
        )
        assert target.base_image is None
        assert target.platform_config_json["ami_id"] == "ami-12345"

    def test_ios_target_higher_escrow(self):
        target = KnownTarget(
            slug="ios-latest",
            display_name="Apple iOS (Latest)",
            platform="ios",
            current_version="18.4",
            verification_method="manual",
            poc_script_type="manual",
            poc_instructions="Manual verification.",
            escrow_amount_usd=500,
        )
        assert target.escrow_amount_usd == 500


class TestVerificationProposalModel:
    def test_create_proposal(self):
        proposal = VerificationProposal(
            seller_pubkey="a" * 64,
            target_id=uuid.uuid4(),
            target_version="124.0.6367.91",
            poc_script="<html><script>alert(1)</script></html>",
            poc_script_type="html",
            claimed_capability="ace",
            asking_price_eth=5.0,
            status="pending_deposit",
            deposit_required=True,
        )
        assert proposal.claimed_capability == "ace"
        assert proposal.status == "pending_deposit"
        assert proposal.deposit_required is True

    def test_proposal_badge_holder_no_deposit(self):
        proposal = VerificationProposal(
            seller_pubkey="b" * 64,
            target_id=uuid.uuid4(),
            target_version="124.0.6367.91",
            poc_script="#!/bin/bash\nid",
            poc_script_type="bash",
            claimed_capability="lpe",
            asking_price_eth=10.0,
            deposit_required=False,
            status="queued",
        )
        assert proposal.deposit_required is False
        assert proposal.status == "queued"


class TestVulnIdentityBadge:
    def test_default_no_badge(self):
        identity = VulnIdentity(public_key="c" * 64, has_badge=False)
        assert identity.has_badge is False
        assert identity.badge_type is None

    def test_purchased_badge(self):
        identity = VulnIdentity(
            public_key="d" * 64,
            has_badge=True,
            badge_type="purchased",
            badge_tx_hash="0x" + "a" * 64,
            badge_awarded_at=datetime.now(timezone.utc),
        )
        assert identity.has_badge is True
        assert identity.badge_type == "purchased"

    def test_earned_badge(self):
        identity = VulnIdentity(
            public_key="e" * 64,
            has_badge=True,
            badge_type="earned",
        )
        assert identity.badge_type == "earned"


# ── Schema validation ──


class TestSchemas:
    def test_proposal_create_request_valid(self):
        req = ProposalCreateRequest(
            target_id=str(uuid.uuid4()),
            poc_script="<html><body>exploit</body></html>",
            poc_script_type="html",
            claimed_capability="ace",
            asking_price_eth=3.0,
        )
        assert req.reliability_runs == 3  # default

    def test_proposal_create_request_max_script(self):
        req = ProposalCreateRequest(
            target_id=str(uuid.uuid4()),
            poc_script="x" * 262144,  # 256KB limit
            poc_script_type="bash",
            claimed_capability="lpe",
            asking_price_eth=1.0,
        )
        assert len(req.poc_script) == 262144

    def test_proposal_create_request_rejects_negative_price(self):
        with pytest.raises(Exception):
            ProposalCreateRequest(
                target_id=str(uuid.uuid4()),
                poc_script="test",
                poc_script_type="bash",
                claimed_capability="crash",
                asking_price_eth=-1.0,
            )

    def test_proposal_create_request_rejects_invalid_capability(self):
        with pytest.raises(Exception):
            ProposalCreateRequest(
                target_id=str(uuid.uuid4()),
                poc_script="test",
                poc_script_type="bash",
                claimed_capability="magic",
                asking_price_eth=1.0,
            )

    def test_deposit_confirm_request_valid(self):
        req = DepositConfirmRequest(tx_hash="0x" + "a" * 64)
        assert req.tx_hash.startswith("0x")

    def test_deposit_confirm_request_rejects_short(self):
        with pytest.raises(Exception):
            DepositConfirmRequest(tx_hash="0xshort")

    def test_badge_purchase_request_valid(self):
        req = BadgePurchaseRequest(
            tx_hash="0x" + "b" * 64,
            eth_address="0x" + "c" * 40,
        )
        assert req.eth_address.startswith("0x")

    def test_badge_purchase_request_rejects_bad_address(self):
        with pytest.raises(Exception):
            BadgePurchaseRequest(
                tx_hash="0x" + "b" * 64,
                eth_address="not-an-address",
            )

    def test_known_target_response_serialization(self):
        resp = KnownTargetResponse(
            id=str(uuid.uuid4()),
            slug="chrome-linux",
            display_name="Google Chrome (Linux)",
            platform="linux",
            current_version="124.0",
            verification_method="nitro",
            poc_script_type="html",
            poc_instructions="Test",
            escrow_amount_usd=100,
            icon_emoji="\U0001f310",
            is_active=True,
            has_prebuilt=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.slug == "chrome-linux"
        assert resp.has_prebuilt is False

    def test_proposal_response_optional_fields(self):
        resp = ProposalResponse(
            id=str(uuid.uuid4()),
            seller_pubkey="a" * 64,
            target_id=str(uuid.uuid4()),
            target_version="124.0",
            poc_script_type="html",
            claimed_capability="ace",
            reliability_runs=3,
            asking_price_eth=5.0,
            deposit_required=True,
            status="pending_deposit",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        assert resp.deposit_amount_wei is None
        assert resp.created_vuln_id is None
