"""
VisionTrace AI – MongoDB Atlas Database Module.
Provides asynchronous connection pooling with Motor for FastAPI routes,
synchronous client with PyMongo for Celery workers, collection accessors,
document serialization, and index management.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import motor.motor_asyncio
import pymongo
from bson import ObjectId

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class MongoDBManager:
    """
    Singleton manager for MongoDB Atlas connection lifecycle.
    Maintains both an asynchronous Motor client (for FastAPI async request handlers)
    and a synchronous PyMongo client (for Celery background tasks & synchronous threads).
    """

    async_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
    sync_client: Optional[pymongo.MongoClient] = None
    async_db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None
    sync_db: Optional[pymongo.database.Database] = None
    is_connected: bool = False
    last_error: Optional[str] = None


mongo_manager = MongoDBManager()


def is_uri_configured(uri: Optional[str] = None) -> bool:
    """
    Validates whether MONGODB_URI is provided and contains real credentials
    rather than template placeholders (e.g. <db_username>:<db_password>).
    """
    u = uri or settings.mongodb_uri
    if not u or not u.strip():
        return False
    # Check for template angle brackets or common placeholder strings
    if "<db_username>" in u or "<db_password>" in u or "<username>" in u or "<password>" in u:
        return False
    if "<" in u and ">" in u:
        return False
    return True


def get_mongodb_uri() -> str:
    """Retrieves and normalizes the MongoDB connection URI from settings/env."""
    uri = settings.mongodb_uri or ""
    return uri.strip()


async def connect_to_mongo() -> bool:
    """
    Initializes asynchronous and synchronous MongoDB clients.
    Verifies connectivity using an admin ping.
    Suppresses recurring background thread errors if the URI is not yet configured.
    """
    uri = get_mongodb_uri()
    db_name = settings.mongodb_database or "visiontrace"

    if not is_uri_configured(uri):
        mongo_manager.is_connected = False
        mongo_manager.last_error = "MONGODB_URI contains placeholder credentials (<db_username>:<db_password>)"
        logger.info(
            "ℹ️ MongoDB Atlas: MONGODB_URI in backend/.env contains template placeholders (<db_username>:<db_password>). "
            "Update backend/.env with your Atlas database username & password to activate MongoDB."
        )
        return False

    logger.info("Connecting to MongoDB Atlas database: %s", db_name)
    try:
        # 1. Asynchronous Client (Motor)
        async_client = motor.motor_asyncio.AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
            maxPoolSize=50,
            minPoolSize=5,
        )

        # 2. Synchronous Client (PyMongo for Celery / threads)
        sync_client = pymongo.MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
            maxPoolSize=20,
        )

        # Verify connectivity via admin ping
        t0 = time.perf_counter()
        await async_client.admin.command("ping")
        latency = (time.perf_counter() - t0) * 1000

        mongo_manager.async_client = async_client
        mongo_manager.async_db = async_client[db_name]
        mongo_manager.sync_client = sync_client
        mongo_manager.sync_db = sync_client[db_name]
        mongo_manager.is_connected = True
        mongo_manager.last_error = None

        logger.info(" Connected to MongoDB Atlas (%s) in %.2fms", db_name, latency)

        # Ensure collection indexes
        await init_mongo_indexes()
        return True

    except Exception as exc:
        mongo_manager.is_connected = False
        mongo_manager.last_error = str(exc)

        # Cleanly close clients so PyMongo does not spawn repeating background error threads
        if 'async_client' in locals() and async_client:
            try:
                async_client.close()
            except Exception:
                pass
        if 'sync_client' in locals() and sync_client:
            try:
                sync_client.close()
            except Exception:
                pass

        mongo_manager.async_client = None
        mongo_manager.async_db = None
        mongo_manager.sync_client = None
        mongo_manager.sync_db = None

        logger.warning(
            "⚠️ MongoDB Atlas connection check failed: %s (Will retry once valid credentials are provided in backend/.env)",
            exc,
        )
        return False


async def close_mongo_connection() -> None:
    """Gracefully closes all MongoDB client connection pools."""
    logger.info("Closing MongoDB connections...")
    if mongo_manager.async_client:
        try:
            mongo_manager.async_client.close()
        except Exception:
            pass
        mongo_manager.async_client = None
        mongo_manager.async_db = None

    if mongo_manager.sync_client:
        try:
            mongo_manager.sync_client.close()
        except Exception:
            pass
        mongo_manager.sync_client = None
        mongo_manager.sync_db = None

    mongo_manager.is_connected = False
    logger.info("MongoDB connection pools closed.")


async def ping_mongo() -> Tuple[bool, str, float]:
    """
    Checks the real-time health and latency of the MongoDB Atlas connection.
    Returns (is_ok, message, latency_ms).
    """
    uri = get_mongodb_uri()
    if not is_uri_configured(uri):
        return False, "MONGODB_URI contains placeholder credentials. Set real username/password in backend/.env", 0.0

    if not mongo_manager.async_client:
        return False, "MongoDB client is not connected", 0.0

    try:
        t0 = time.perf_counter()
        await mongo_manager.async_client.admin.command("ping")
        latency = round((time.perf_counter() - t0) * 1000, 2)
        return True, f"MongoDB Atlas OK ({latency}ms)", latency
    except Exception as exc:
        return False, f"MongoDB Atlas Ping Failed: {str(exc)}", 0.0


async def init_mongo_indexes() -> None:
    """
    Provisions optimal indexes across all 10 MongoDB collections.
    Idempotent: safe to run on every application startup.
    """
    if mongo_manager.async_db is None:
        return

    db = mongo_manager.async_db
    try:
        # 1. users
        await db.users.create_index([("email", pymongo.ASCENDING)], unique=True)
        await db.users.create_index([("role", pymongo.ASCENDING)])

        # 2. videos
        await db.videos.create_index([("uploaded_by", pymongo.ASCENDING)])
        await db.videos.create_index([("status", pymongo.ASCENDING)])
        await db.videos.create_index([("created_at", pymongo.DESCENDING)])
        await db.videos.create_index([("file_hash", pymongo.ASCENDING)])

        # 3. detections (events)
        await db.detections.create_index([("video_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)])
        await db.detections.create_index([("video_id", pymongo.ASCENDING), ("attributes.class_name", pymongo.ASCENDING)])
        await db.detections.create_index([("confidence", pymongo.DESCENDING)])

        # 4. tracks
        await db.tracks.create_index([("video_id", pymongo.ASCENDING), ("track_id", pymongo.ASCENDING)])
        await db.tracks.create_index([("video_id", pymongo.ASCENDING), ("object_class", pymongo.ASCENDING)])

        # 5. embeddings
        await db.embeddings.create_index([("video_id", pymongo.ASCENDING), ("timestamp", pymongo.ASCENDING)])
        await db.embeddings.create_index([("embedding_type", pymongo.ASCENDING)])

        # 6. cases (investigations)
        await db.cases.create_index([("owner_id", pymongo.ASCENDING)])
        await db.cases.create_index([("status", pymongo.ASCENDING)])
        await db.cases.create_index([("priority", pymongo.ASCENDING)])
        await db.cases.create_index([("created_at", pymongo.DESCENDING)])

        # 7. evidence
        await db.evidence.create_index([("case_id", pymongo.ASCENDING), ("sequence_number", pymongo.ASCENDING)])
        await db.evidence.create_index([("video_id", pymongo.ASCENDING)])

        # 8. reports
        await db.reports.create_index([("case_id", pymongo.ASCENDING)])
        await db.reports.create_index([("created_by", pymongo.ASCENDING)])
        await db.reports.create_index([("created_at", pymongo.DESCENDING)])

        # 9. audit_logs
        await db.audit_logs.create_index([("created_at", pymongo.DESCENDING)])
        await db.audit_logs.create_index([("action", pymongo.ASCENDING)])
        await db.audit_logs.create_index([("actor_id", pymongo.ASCENDING)])
        await db.audit_logs.create_index([("target_type", pymongo.ASCENDING), ("target_id", pymongo.ASCENDING)])

        # 10. processing_jobs
        await db.processing_jobs.create_index([("video_id", pymongo.ASCENDING)])
        await db.processing_jobs.create_index([("status", pymongo.ASCENDING)])

        logger.info(" Provisioned indexes for 10 MongoDB collections.")
    except Exception as exc:
        logger.warning("Warning during MongoDB index provisioning: %s", exc)


def get_async_db() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """Dependency injection helper for FastAPI asynchronous route handlers."""
    if mongo_manager.async_db is None:
        uri = get_mongodb_uri()
        if not is_uri_configured(uri):
            raise ConnectionError(
                "MongoDB Atlas is not configured with real credentials. "
                "Please replace <db_username>:<db_password> in backend/.env."
            )
        db_name = settings.mongodb_database or "visiontrace"
        mongo_manager.async_client = motor.motor_asyncio.AsyncIOMotorClient(uri, serverSelectionTimeoutMS=5000)
        mongo_manager.async_db = mongo_manager.async_client[db_name]
    return mongo_manager.async_db


def get_sync_db() -> pymongo.database.Database:
    """Synchronous database accessor for Celery workers and background threads."""
    if mongo_manager.sync_db is None:
        uri = get_mongodb_uri()
        if not is_uri_configured(uri):
            raise ConnectionError(
                "MongoDB Atlas is not configured with real credentials. "
                "Please replace <db_username>:<db_password> in backend/.env."
            )
        db_name = settings.mongodb_database or "visiontrace"
        mongo_manager.sync_client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=5000)
        mongo_manager.sync_db = mongo_manager.sync_client[db_name]
    return mongo_manager.sync_db


# ── Document Formatting & Normalization Helpers ──────────────────────────────

def serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Normalizes a MongoDB document for JSON serialization and Pydantic validation:
    - Ensures 'id' is a string matching either doc['id'] or str(doc['_id']).
    - Converts datetime fields to ISO strings or preserves them.
    - Leaves original '_id' intact or removes if necessary.
    """
    if doc is None:
        return None

    clean = dict(doc)
    if "_id" in clean:
        if "id" not in clean or not clean["id"]:
            clean["id"] = str(clean["_id"])
        del clean["_id"]

    for k, v in clean.items():
        if isinstance(v, ObjectId):
            clean[k] = str(v)
        elif isinstance(v, datetime):
            clean[k] = v.isoformat()
        elif isinstance(v, dict):
            clean[k] = serialize_doc(v)
        elif isinstance(v, list):
            clean[k] = [
                serialize_doc(item) if isinstance(item, dict)
                else str(item) if isinstance(item, ObjectId)
                else item.isoformat() if isinstance(item, datetime)
                else item
                for item in v
            ]
    return clean


def serialize_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Serializes a list of MongoDB documents."""
    return [serialize_doc(d) for d in docs if d is not None]  # type: ignore
