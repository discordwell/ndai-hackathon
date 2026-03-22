"""Privacy middleware for Tor hidden service support."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class PrivacyMiddleware(BaseHTTPMiddleware):
    """Strips identifying information from requests.

    Zeroes client IP in ASGI scope and strips proxy headers.
    When privacy_mode is enabled, the server genuinely cannot log
    who made a request — even if compelled.
    """

    async def dispatch(self, request: Request, call_next):
        # Zero out client IP in the scope
        request.scope["client"] = ("0.0.0.0", 0)

        # Strip identifying headers
        headers_to_strip = {
            b"x-real-ip", b"x-forwarded-for", b"cf-connecting-ip",
            b"true-client-ip", b"x-client-ip", b"forwarded",
        }
        request.scope["headers"] = [
            (k, v) for k, v in request.scope["headers"]
            if k.lower() not in headers_to_strip
        ]

        return await call_next(request)


class CSPMiddleware(BaseHTTPMiddleware):
    """Adds Content-Security-Policy headers to block all external resources.

    Critical for Tor users: prevents the browser from making ANY request
    to external origins (fonts, scripts, images, etc.) that could leak
    the user's real IP or create a timing side-channel.
    """

    CSP = "; ".join([
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "font-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ])

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = self.CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response
