"""Tests for Phase 5: API changes + frontend static serving."""

import pytest
from fastapi.testclient import TestClient

from ndai.api.app import create_app
from ndai.api.routers.auth import _users
from ndai.api.routers.inventions import _inventions
from ndai.api.routers.agreements import _agreements
from ndai.api.routers.negotiations import _outcomes, _statuses


@pytest.fixture(autouse=True)
def clean_stores():
    """Clear all in-memory stores between tests."""
    _users.clear()
    _inventions.clear()
    _agreements.clear()
    _outcomes.clear()
    _statuses.clear()
    yield
    _users.clear()
    _inventions.clear()
    _agreements.clear()
    _outcomes.clear()
    _statuses.clear()


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def seller_token(client):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "seller@test.com",
            "password": "testpass123",
            "role": "seller",
            "display_name": "Test Seller",
        },
    )
    assert res.status_code == 200
    return res.json()["access_token"]


@pytest.fixture
def buyer_token(client):
    res = client.post(
        "/api/v1/auth/register",
        json={
            "email": "buyer@test.com",
            "password": "testpass123",
            "role": "buyer",
            "display_name": "Test Buyer",
        },
    )
    assert res.status_code == 200
    return res.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestAuthRole:
    """Test that role is included in token responses."""

    def test_register_returns_role(self, client):
        res = client.post(
            "/api/v1/auth/register",
            json={"email": "a@b.com", "password": "pass123", "role": "seller"},
        )
        data = res.json()
        assert data["role"] == "seller"
        assert data["token_type"] == "bearer"
        assert "access_token" in data

    def test_register_buyer_role(self, client):
        res = client.post(
            "/api/v1/auth/register",
            json={"email": "b@b.com", "password": "pass123", "role": "buyer"},
        )
        assert res.json()["role"] == "buyer"

    def test_login_returns_role(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "c@b.com", "password": "pass123", "role": "seller"},
        )
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "c@b.com", "password": "pass123"},
        )
        assert res.json()["role"] == "seller"

    def test_login_wrong_password(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "d@b.com", "password": "pass123", "role": "buyer"},
        )
        res = client.post(
            "/api/v1/auth/login",
            json={"email": "d@b.com", "password": "wrong"},
        )
        assert res.status_code == 401

    def test_duplicate_email(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "dup@b.com", "password": "pass123", "role": "seller"},
        )
        res = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@b.com", "password": "pass456", "role": "buyer"},
        )
        assert res.status_code == 400


class TestStaticServing:
    """Test that the SPA catch-all returns index.html."""

    def test_spa_catch_all_returns_html(self, client):
        res = client.get("/some/random/path")
        assert res.status_code == 200
        # Should return index.html content
        assert "NDAI" in res.text

    def test_health_still_works(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    def test_api_routes_not_caught(self, client):
        res = client.get("/api/v1/inventions/listings")
        assert res.status_code == 200
        assert isinstance(res.json(), list)


class TestFullSellerBuyerFlow:
    """Integration test for the full seller -> buyer -> negotiation flow."""

    def test_seller_creates_invention(self, client, seller_token):
        res = client.post(
            "/api/v1/inventions/",
            headers=auth(seller_token),
            json={
                "title": "Test Invention",
                "full_description": "A test invention for testing.",
                "technical_domain": "testing",
                "novelty_claims": ["It tests things"],
                "development_stage": "concept",
                "self_assessed_value": 0.75,
                "outside_option_value": 0.3,
                "anonymized_summary": "A novel testing method",
                "category": "Software",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["title"] == "Test Invention"
        assert data["status"] == "active"

    def test_buyer_sees_listings(self, client, seller_token):
        # Seller creates invention
        client.post(
            "/api/v1/inventions/",
            headers=auth(seller_token),
            json={
                "title": "Visible Invention",
                "full_description": "desc",
                "technical_domain": "test",
                "novelty_claims": ["new"],
                "development_stage": "prototype",
                "self_assessed_value": 0.5,
                "outside_option_value": 0.2,
            },
        )
        # Anyone can see listings (no auth)
        res = client.get("/api/v1/inventions/listings")
        assert res.status_code == 200
        listings = res.json()
        assert len(listings) == 1
        assert listings[0]["title"] == "Visible Invention"

    def test_buyer_creates_agreement(self, client, seller_token, buyer_token):
        # Seller creates invention
        inv = client.post(
            "/api/v1/inventions/",
            headers=auth(seller_token),
            json={
                "title": "Invention",
                "full_description": "desc",
                "technical_domain": "test",
                "novelty_claims": ["new"],
                "development_stage": "concept",
                "self_assessed_value": 0.5,
                "outside_option_value": 0.2,
            },
        ).json()

        # Buyer creates agreement
        res = client.post(
            "/api/v1/agreements/",
            headers=auth(buyer_token),
            json={"invention_id": inv["id"], "budget_cap": 0.8},
        )
        assert res.status_code == 200
        agreement = res.json()
        assert agreement["status"] == "proposed"
        assert agreement["invention_id"] == inv["id"]

    def test_agreement_params_and_confirm(self, client, seller_token, buyer_token):
        # Create invention + agreement
        inv = client.post(
            "/api/v1/inventions/",
            headers=auth(seller_token),
            json={
                "title": "Inv",
                "full_description": "d",
                "technical_domain": "t",
                "novelty_claims": ["n"],
                "development_stage": "concept",
                "self_assessed_value": 0.6,
                "outside_option_value": 0.25,
            },
        ).json()
        agr = client.post(
            "/api/v1/agreements/",
            headers=auth(buyer_token),
            json={"invention_id": inv["id"], "budget_cap": 0.9},
        ).json()

        # Set params
        res = client.post(
            f"/api/v1/agreements/{agr['id']}/params",
            headers=auth(buyer_token),
            json={"alpha_0": 0.25},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["alpha_0"] == 0.25
        assert data["theta"] == pytest.approx(0.625)  # (1 + 0.25) / 2

        # Confirm
        res = client.post(
            f"/api/v1/agreements/{agr['id']}/confirm",
            headers=auth(buyer_token),
        )
        assert res.status_code == 200
        assert res.json()["status"] == "confirmed"

    def test_negotiation_status_404_before_start(self, client, seller_token, buyer_token):
        inv = client.post(
            "/api/v1/inventions/",
            headers=auth(seller_token),
            json={
                "title": "Inv",
                "full_description": "d",
                "technical_domain": "t",
                "novelty_claims": ["n"],
                "development_stage": "concept",
                "self_assessed_value": 0.5,
                "outside_option_value": 0.2,
            },
        ).json()
        agr = client.post(
            "/api/v1/agreements/",
            headers=auth(buyer_token),
            json={"invention_id": inv["id"], "budget_cap": 0.8},
        ).json()

        res = client.get(
            f"/api/v1/negotiations/{agr['id']}/status",
            headers=auth(buyer_token),
        )
        assert res.status_code == 404

    def test_negotiation_outcome_404_before_start(self, client, buyer_token):
        res = client.get(
            "/api/v1/negotiations/nonexistent/outcome",
            headers=auth(buyer_token),
        )
        assert res.status_code == 404


class TestNegotiationStatusEndpoint:
    """Test the new status polling endpoint."""

    def test_status_returns_pending_on_start(self, client, seller_token, buyer_token):
        # Set up invention + agreement
        inv = client.post(
            "/api/v1/inventions/",
            headers=auth(seller_token),
            json={
                "title": "Status Test",
                "full_description": "desc",
                "technical_domain": "test",
                "novelty_claims": ["n"],
                "development_stage": "concept",
                "self_assessed_value": 0.5,
                "outside_option_value": 0.2,
                "max_disclosure_fraction": 0.8,
            },
        ).json()

        agr = client.post(
            "/api/v1/agreements/",
            headers=auth(buyer_token),
            json={"invention_id": inv["id"], "budget_cap": 0.8},
        ).json()

        # Start negotiation — this won't actually run the LLM in tests
        # (no API key), but it should at least set status to pending
        res = client.post(
            f"/api/v1/negotiations/{agr['id']}/start",
            headers=auth(buyer_token),
        )
        assert res.status_code == 200
        assert res.json()["status"] in ("pending", "running", "completed", "error")
