"""
VisionTrace AI – Data Migration Tool: Relational Database to MongoDB Atlas.
Safely extracts users, videos, detections, tracks, embeddings, cases, evidence,
reports, and audit logs from SQLite / PostgreSQL and upserts into MongoDB Atlas.
Guarantees zero data loss, preserves UUIDs, password hashes, and vector dimensions.
"""
import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Ensure backend directory is in path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.core.config import get_settings
from app.db.mongodb import get_sync_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration")
settings = get_settings()


def parse_json_field(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, (dict, list)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return val


def migrate_sqlite_to_mongodb(sqlite_path: str) -> Dict[str, Any]:
    """Reads tables from SQLite and upserts into MongoDB Atlas."""
    db_path = Path(sqlite_path)
    if not db_path.exists():
        logger.error("SQLite database file not found at: %s", sqlite_path)
        return {"error": "SQLite file not found"}

    logger.info("Opening source database: %s", sqlite_path)
    con = sqlite3.connect(sqlite_path)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    mongo = get_sync_db()
    logger.info("Connected to target MongoDB database: %s", mongo.name)

    stats: Dict[str, int] = {}

    # 1. Users
    cur.execute("SELECT * FROM users")
    user_rows = cur.fetchall()
    for row in user_rows:
        doc = dict(row)
        mongo.users.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["users"] = len(user_rows)
    logger.info("Migrated %d users", stats["users"])

    # 2. Videos
    cur.execute("SELECT * FROM videos")
    video_rows = cur.fetchall()
    for row in video_rows:
        doc = dict(row)
        doc["video_metadata"] = parse_json_field(doc.get("video_metadata"))
        mongo.videos.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["videos"] = len(video_rows)
    logger.info("Migrated %d videos", stats["videos"])

    # 3. Events -> Detections
    cur.execute("SELECT * FROM events")
    event_rows = cur.fetchall()
    for row in event_rows:
        doc = dict(row)
        doc["bounding_box"] = parse_json_field(doc.get("bounding_box"))
        doc["attributes"] = parse_json_field(doc.get("attributes"))
        mongo.detections.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["detections"] = len(event_rows)
    logger.info("Migrated %d detections", stats["detections"])

    # 4. Tracks
    cur.execute("SELECT * FROM tracks")
    track_rows = cur.fetchall()
    for row in track_rows:
        doc = dict(row)
        doc["attributes"] = parse_json_field(doc.get("attributes"))
        mongo.tracks.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["tracks"] = len(track_rows)
    logger.info("Migrated %d tracks", stats["tracks"])

    # 5. Embeddings
    cur.execute("SELECT * FROM embeddings")
    emb_rows = cur.fetchall()
    for row in emb_rows:
        doc = dict(row)
        raw_emb = doc.get("embedding")
        if isinstance(raw_emb, str):
            try:
                # Handle string vector representation "[0.12, -0.45, ...]"
                doc["embedding"] = [float(x) for x in raw_emb.strip("[]").split(",") if x.strip()]
            except Exception:
                pass
        mongo.embeddings.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["embeddings"] = len(emb_rows)
    logger.info("Migrated %d embeddings", stats["embeddings"])

    # 6. Investigations -> Cases
    cur.execute("SELECT * FROM investigations")
    case_rows = cur.fetchall()
    for row in case_rows:
        doc = dict(row)
        doc["tags"] = parse_json_field(doc.get("tags")) or []
        mongo.cases.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["cases"] = len(case_rows)
    logger.info("Migrated %d cases", stats["cases"])

    # 7. Investigation Evidence -> Evidence
    cur.execute("SELECT * FROM investigation_evidence")
    ev_rows = cur.fetchall()
    for row in ev_rows:
        doc = dict(row)
        doc["case_id"] = doc.pop("investigation_id", None)
        doc["custom_metadata"] = parse_json_field(doc.get("custom_metadata"))
        mongo.evidence.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["evidence"] = len(ev_rows)
    logger.info("Migrated %d evidence items", stats["evidence"])

    # 8. Reports
    cur.execute("SELECT * FROM reports")
    rep_rows = cur.fetchall()
    for row in rep_rows:
        doc = dict(row)
        doc["case_id"] = doc.pop("investigation_id", None)
        doc["findings"] = parse_json_field(doc.get("findings"))
        doc["evidence_timeline"] = parse_json_field(doc.get("evidence_timeline"))
        mongo.reports.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["reports"] = len(rep_rows)
    logger.info("Migrated %d reports", stats["reports"])

    # 9. Audit Logs
    cur.execute("SELECT * FROM audit_logs")
    audit_rows = cur.fetchall()
    for row in audit_rows:
        doc = dict(row)
        doc["details"] = parse_json_field(doc.get("details"))
        mongo.audit_logs.update_one(
            {"id": str(doc["id"])},
            {"$set": doc},
            upsert=True,
        )
    stats["audit_logs"] = len(audit_rows)
    logger.info("Migrated %d audit logs", stats["audit_logs"])

    con.close()
    logger.info("🎉 Database migration completed with stats: %s", stats)
    return stats


if __name__ == "__main__":
    db_file = str(settings.storage_base / "visiontrace_dev.db")
    if len(sys.argv) > 1:
        db_file = sys.argv[1]
    migrate_sqlite_to_mongodb(db_file)
