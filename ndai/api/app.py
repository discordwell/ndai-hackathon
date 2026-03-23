"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ndai.api.routers import agreements, auth, badges, bounties, enclave, inventions, messaging, negotiations, poker, proposals, rfps, secrets, serious_customer, targets, transcripts, vulns, vuln_verify, vuln_demo, delivery, zk_auth, zk_auctions, zk_vulns

_frontend_override = os.environ.get("FRONTEND_DIR", "")
FRONTEND_DIST = Path(_frontend_override) if _frontend_override else Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down the DB engine."""
    from ndai.db.session import engine

    logger.info("NDAI starting up (database=%s)", engine.url.database)
    yield
    await engine.dispose()
    logger.info("NDAI shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="NDAI",
        description="Non-Disclosure via AI Agents and Trusted Execution Environments",
        version="0.1.0",
        lifespan=lifespan,
    )

    from ndai.config import settings

    cors_origins = getattr(settings, "cors_origins", None) or ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Security headers
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    if settings.privacy_mode:
        from ndai.api.middleware.privacy import PrivacyMiddleware, CSPMiddleware
        app.add_middleware(PrivacyMiddleware)
        app.add_middleware(CSPMiddleware)

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(inventions.router, prefix="/api/v1/inventions", tags=["inventions"])
    app.include_router(agreements.router, prefix="/api/v1/agreements", tags=["agreements"])
    app.include_router(negotiations.router, prefix="/api/v1/negotiations", tags=["negotiations"])
    app.include_router(secrets.router, prefix="/api/v1/secrets", tags=["secrets"])
    app.include_router(transcripts.router, prefix="/api/v1/transcripts", tags=["transcripts"])
    app.include_router(poker.router, prefix="/api/v1/poker", tags=["poker"])
    app.include_router(vulns.router, prefix="/api/v1/vulns", tags=["vulnerabilities"])
    app.include_router(vuln_verify.router, prefix="/api/v1/vuln-verify", tags=["vuln-verify"])
    app.include_router(vuln_demo.router, prefix="/api/v1/vuln-demo", tags=["vuln-demo"])
    app.include_router(rfps.router, prefix="/api/v1/rfps", tags=["rfps"])
    app.include_router(delivery.router, prefix="/api/v1/delivery", tags=["delivery"])
    app.include_router(zk_auth.router, prefix="/api/v1/zk-auth", tags=["zk-auth"])
    app.include_router(zk_vulns.router, prefix="/api/v1/zk-vulns", tags=["zk-vulnerabilities"])
    app.include_router(bounties.router, prefix="/api/v1/bounties", tags=["bounties"])
    app.include_router(messaging.router, prefix="/api/v1/messaging", tags=["messaging"])
    app.include_router(targets.router, prefix="/api/v1/targets", tags=["targets"])
    app.include_router(proposals.router, prefix="/api/v1/proposals", tags=["proposals"])
    app.include_router(badges.router, prefix="/api/v1/badges", tags=["badges"])
    app.include_router(enclave.router, prefix="/api/v1/enclave", tags=["enclave"])
    app.include_router(serious_customer.router, prefix="/api/v1/serious-customer", tags=["serious-customer"])
    app.include_router(zk_auctions.router, prefix="/api/v1/zk-auctions", tags=["zk-auctions"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Static file serving — only if frontend is built
    if FRONTEND_DIST.exists():
        assets_dir = FRONTEND_DIST / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="static")

        # SPA catch-all: serve index.html for all non-API routes
        @app.get("/{path:path}")
        async def spa_catch_all(request: Request, path: str):
            index = FRONTEND_DIST / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return {"detail": "Frontend not built. Run: make frontend-build"}

    return app
