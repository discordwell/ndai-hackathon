"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ndai.api.routers import agreements, auth, inventions, negotiations


def create_app() -> FastAPI:
    app = FastAPI(
        title="NDAI",
        description="Non-Disclosure via AI Agents and Trusted Execution Environments",
        version="0.1.0",
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

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app
