"""FastAPI application factory."""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ndai.api.routers import agreements, auth, inventions, negotiations, secrets, transcripts

FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(inventions.router, prefix="/api/v1/inventions", tags=["inventions"])
    app.include_router(agreements.router, prefix="/api/v1/agreements", tags=["agreements"])
    app.include_router(negotiations.router, prefix="/api/v1/negotiations", tags=["negotiations"])
    app.include_router(secrets.router, prefix="/api/v1/secrets", tags=["secrets"])
    app.include_router(transcripts.router, prefix="/api/v1/transcripts", tags=["transcripts"])

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
