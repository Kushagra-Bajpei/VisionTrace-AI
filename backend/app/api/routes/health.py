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
from app.db.mongodb import ping_mongo

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

    mongo_ok, mongo_msg, mongo_latency = await ping_mongo()

    db_status = {
        "status": "ok" if db_connected else "unreachable",
        "details": db_msg,
    }

    mongo_status = {
        "status": "ok" if mongo_ok else "unreachable",
        "details": mongo_msg,
        "latency_ms": mongo_latency,
        "database": settings.mongodb_database or "visiontrace",
    }

    overall_status = "ok" if (db_connected or mongo_ok) else "degraded"

    return {
        "status": overall_status,
        "service": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "subsystems": {
            "api": {"status": "ok"},
            "database": db_status,
            "mongodb": mongo_status,
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


@router.get("/health/mongodb")
async def health_check_mongodb():
    """
    Dedicated MongoDB Atlas connection probe.
    Pings MongoDB Atlas cluster and returns latency and collection status.
    """
    is_ok, msg, latency = await ping_mongo()
    return {
        "status": "ok" if is_ok else "error",
        "database": settings.mongodb_database or "visiontrace",
        "details": msg,
        "latency_ms": latency,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
