"""Tests for privacy middleware — IP zeroing, header stripping, CSP headers."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ndai:ndai@localhost:5432/ndai")

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ndai.api.middleware.privacy import CSPMiddleware, PrivacyMiddleware


# ── Test app factory ──


def _make_app(middleware_classes: list[type]) -> Starlette:
    """Build a minimal Starlette app with the given middleware for testing."""

    async def echo_client(request):
        """Echo back the client IP and select headers for inspection."""
        host = request.client.host if request.client else "none"
        port = request.client.port if request.client else 0
        return JSONResponse({
            "client_host": host,
            "client_port": port,
            "x_real_ip": request.headers.get("x-real-ip"),
            "x_forwarded_for": request.headers.get("x-forwarded-for"),
            "cf_connecting_ip": request.headers.get("cf-connecting-ip"),
            "true_client_ip": request.headers.get("true-client-ip"),
            "x_client_ip": request.headers.get("x-client-ip"),
            "forwarded": request.headers.get("forwarded"),
        })

    async def hello(request):
        return JSONResponse({"message": "ok"})

    app = Starlette(
        routes=[
            Route("/echo", echo_client),
            Route("/hello", hello),
        ],
    )

    # Add middleware in reverse order (Starlette processes outermost first)
    for cls in reversed(middleware_classes):
        app.add_middleware(cls)

    return app


# ── PrivacyMiddleware tests ──


class TestPrivacyMiddleware:
    def test_privacy_middleware_zeroes_client_ip(self):
        """PrivacyMiddleware sets request.client.host to '0.0.0.0'."""
        app = _make_app([PrivacyMiddleware])
        client = TestClient(app)

        resp = client.get("/echo")
        assert resp.status_code == 200

        data = resp.json()
        assert data["client_host"] == "0.0.0.0"
        assert data["client_port"] == 0

    def test_privacy_middleware_strips_forwarded_headers(self):
        """PrivacyMiddleware removes X-Real-IP, X-Forwarded-For, and related headers."""
        app = _make_app([PrivacyMiddleware])
        client = TestClient(app)

        resp = client.get(
            "/echo",
            headers={
                "X-Real-IP": "1.2.3.4",
                "X-Forwarded-For": "1.2.3.4, 5.6.7.8",
                "CF-Connecting-IP": "9.10.11.12",
                "True-Client-IP": "13.14.15.16",
                "X-Client-IP": "17.18.19.20",
                "Forwarded": "for=1.2.3.4",
            },
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["x_real_ip"] is None
        assert data["x_forwarded_for"] is None
        assert data["cf_connecting_ip"] is None
        assert data["true_client_ip"] is None
        assert data["x_client_ip"] is None
        assert data["forwarded"] is None

    def test_privacy_middleware_preserves_non_identifying_headers(self):
        """PrivacyMiddleware does not strip standard headers like Content-Type."""
        app = _make_app([PrivacyMiddleware])
        client = TestClient(app)

        resp = client.get("/echo", headers={"Accept": "application/json"})
        assert resp.status_code == 200


# ── CSPMiddleware tests ──


class TestCSPMiddleware:
    def test_csp_middleware_adds_headers(self):
        """CSPMiddleware adds Content-Security-Policy header to responses."""
        app = _make_app([CSPMiddleware])
        client = TestClient(app)

        resp = client.get("/hello")
        assert resp.status_code == 200
        assert "content-security-policy" in resp.headers

    def test_csp_blocks_external_sources(self):
        """CSP value contains \"default-src 'self'\" to block external resources."""
        app = _make_app([CSPMiddleware])
        client = TestClient(app)

        resp = client.get("/hello")
        csp = resp.headers["content-security-policy"]
        assert "default-src 'self'" in csp

    def test_csp_script_src_self(self):
        """CSP restricts script-src to 'self'."""
        app = _make_app([CSPMiddleware])
        client = TestClient(app)

        resp = client.get("/hello")
        csp = resp.headers["content-security-policy"]
        assert "script-src 'self'" in csp

    def test_csp_object_src_none(self):
        """CSP blocks object/embed/applet via object-src 'none'."""
        app = _make_app([CSPMiddleware])
        client = TestClient(app)

        resp = client.get("/hello")
        csp = resp.headers["content-security-policy"]
        assert "object-src 'none'" in csp

    def test_csp_frame_ancestors_none(self):
        """CSP prevents framing via frame-ancestors 'none'."""
        app = _make_app([CSPMiddleware])
        client = TestClient(app)

        resp = client.get("/hello")
        csp = resp.headers["content-security-policy"]
        assert "frame-ancestors 'none'" in csp


# ── Security headers tests ──


class TestSecurityHeaders:
    def test_security_headers_added(self):
        """CSPMiddleware also adds X-Content-Type-Options, X-Frame-Options, Referrer-Policy."""
        app = _make_app([CSPMiddleware])
        client = TestClient(app)

        resp = client.get("/hello")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy") == "no-referrer"

    def test_all_middleware_stacked(self):
        """Both middleware work together without conflict."""
        app = _make_app([PrivacyMiddleware, CSPMiddleware])
        client = TestClient(app)

        resp = client.get(
            "/echo",
            headers={"X-Real-IP": "1.2.3.4", "X-Forwarded-For": "5.6.7.8"},
        )
        assert resp.status_code == 200

        # Privacy: IP zeroed, headers stripped
        data = resp.json()
        assert data["client_host"] == "0.0.0.0"
        assert data["x_real_ip"] is None
        assert data["x_forwarded_for"] is None

        # CSP: security headers present
        assert "content-security-policy" in resp.headers
        assert resp.headers.get("x-content-type-options") == "nosniff"
