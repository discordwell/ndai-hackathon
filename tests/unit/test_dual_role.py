"""Unit tests for dual-role user registration (zdayzk)."""

from ndai.api.schemas.auth import RegisterRequest


def test_register_default_role_is_user():
    """Omitting role should default to 'user'."""
    req = RegisterRequest(email="test@example.com", password="pass123")
    assert req.role == "user"


def test_register_explicit_user_role():
    """Explicitly setting role='user' should work."""
    req = RegisterRequest(email="test@example.com", password="pass123", role="user")
    assert req.role == "user"


def test_register_seller_still_works():
    """Existing seller role should still work."""
    req = RegisterRequest(email="test@example.com", password="pass123", role="seller")
    assert req.role == "seller"


def test_register_buyer_still_works():
    """Existing buyer role should still work."""
    req = RegisterRequest(email="test@example.com", password="pass123", role="buyer")
    assert req.role == "buyer"
