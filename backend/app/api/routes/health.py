"""
Health-check and system information router.
Dynamically checks database connectivity and reports subsystem status.
"""
import platform
import sys
from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import check_db_connection

router = APIRouter()
settings = get_settings()

_started_at = datetime.now(timezone.utc)


@router.get("/health")
async def health_check():
    """
    Basic liveness probe.
    Returns 200 OK when the API process is alive.
    """
    return {
        "status": "ok",
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": (
            datetime.now(timezone.utc) - _started_at
        ).total_seconds(),
    }


@router.get("/health/detailed")
async def health_check_detailed():
    """
    Detailed readiness probe.
    Checks individual subsystems: API, Database, Redis, and Storage.
    """
    db_connected, db_msg = check_db_connection()

    db_status = {
        "status": "ok" if db_connected else "unreachable",
        "details": db_msg,
    }

    overall_status = "ok" if db_connected else "degraded"

    return {
        "status": overall_status,
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subsystems": {
            "api": {"status": "ok"},
            "database": db_status,
            "redis": {
                "status": "not_configured",
                "note": "Redis integration added in Phase 4",
            },
            "storage": {
                "status": "ok" if settings.storage_base.exists() else "missing",
                "path": str(settings.storage_base),
            },
        },
        "runtime": {
            "python": sys.version,
            "platform": platform.platform(),
        },
    }
