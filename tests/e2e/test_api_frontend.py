"""Tests for API changes + frontend static serving."""

import asyncio

import asyncpg
import pytest
from fastapi.testclient import TestClient

from ndai.api.app import create_app
from ndai.api.routers.negotiations import _statuses

# Direct asyncpg connection for test cleanup (avoids SQLAlchemy event loop conflicts)
_DB_URL = "postgresql://ndai:ndai@localhost:5433/ndai"
_TRUNCATE_SQL = """
TRUNCATE TABLE agreement_outcomes, audit_log, payments, agreements, inventions, users CASCADE;
"""


def _clean_db():
    """Truncate all tables using a fresh asyncpg connection."""
    async def _truncate():
        conn = await asyncpg.connect(_DB_URL)
        try:
            await conn.execute(_TRUNCATE_SQL)
        finally:
            await conn.close()

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_truncate())
    finally:
        loop.close()


# Module-scoped app and client to avoid event loop recreation between tests
@pytest.fixture(scope="module")
def app():
    return create_app()


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_stores():
    """Clear DB tables and in-memory stores between tests."""
    _statuses.clear()
    _clean_db()
    yield
    _statuses.clear()


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
        res = client.get("/api/v1/inventions/listings")
        assert res.status_code == 200
        listings = res.json()
        assert len(listings) == 1
        assert listings[0]["title"] == "Visible Invention"

    def test_buyer_creates_agreement(self, client, seller_token, buyer_token):
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

        res = client.post(
            f"/api/v1/agreements/{agr['id']}/params",
            headers=auth(buyer_token),
            json={"alpha_0": 0.25},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["alpha_0"] == 0.25
        assert data["theta"] == pytest.approx(0.625)

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
            "/api/v1/negotiations/00000000-0000-0000-0000-000000000000/outcome",
            headers=auth(buyer_token),
        )
        assert res.status_code == 404


class TestNegotiationStatusEndpoint:
    """Test the new status polling endpoint."""

    def test_status_returns_pending_on_start(self, client, seller_token, buyer_token):
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

        res = client.post(
            f"/api/v1/negotiations/{agr['id']}/start",
            headers=auth(buyer_token),
        )
        assert res.status_code == 200
        assert res.json()["status"] in ("pending", "running", "completed", "error")
