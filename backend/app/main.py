"""
VisionTrace AI – FastAPI Application Entry Point
"""
import logging

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.api.router import api_router
from app.core.config import get_settings
from app.core.database import check_db_connection, init_db

settings = get_settings()
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Application factory.

    Kept synchronous for Phase 1 so that FastAPI TestClient works
    without async lifespan complications on Windows.
    Lifespan hooks (DB pool, Redis) are added in Phase 2 and 4.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-powered video investigation platform. "
            "Detect, track, and search CCTV footage with natural language."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Exception Handlers ────────────────────────────────────────────────────
    @app.exception_handler(OperationalError)
    async def database_operational_exception_handler(request: Request, exc: OperationalError):
        logger.error("Database operational error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "detail": (
                    "Database service is currently unavailable. "
                    "If running with PostgreSQL, ensure the server/container is started on port 5432 "
                    "(e.g., 'docker compose up -d db') or configure a local SQLite database in .env."
                )
            },
        )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api/v1")

    # ── Root ──────────────────────────────────────────────────────────────────
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "message": "VisionTrace AI API",
            "docs": "/docs",
            "health": "/api/v1/health",
        }

    # ── Startup log ───────────────────────────────────────────────────────────
    @app.on_event("startup")
    async def on_startup():
        logger.info(
            "🚀 %s v%s started [%s]",
            settings.app_name,
            settings.app_version,
            settings.app_env,
        )
        init_db()
        is_ok, msg = check_db_connection()
        if is_ok:
            logger.info(" Database status: %s", msg)
        else:
            logger.warning("⚠️ Database connection check: %s", msg)

    return app


app = create_app()
