"""
VisionTrace AI – MongoDB Repositories.
Provides high-level async (FastAPI) and sync (Celery/Worker) data access
methods across all 10 VisionTrace collections with automatic document serialization.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from bson import ObjectId

from app.db.mongodb import (
    get_async_db,
    get_sync_db,
    serialize_doc,
    serialize_docs,
)

logger = logging.getLogger(__name__)


# ── 1. USER REPOSITORY ────────────────────────────────────────────────────────

class MongoUserRepository:
    @staticmethod
    async def get_by_email(email: str) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        doc = await db.users.find_one({"email": email.lower().strip()})
        return serialize_doc(doc)

    @staticmethod
    async def get_by_id(user_id: str) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        doc = await db.users.find_one({"id": str(user_id)})
        return serialize_doc(doc)

    @staticmethod
    async def count_users() -> int:
        db = get_async_db()
        return await db.users.count_documents({})

    @staticmethod
    async def create_user(
        email: str,
        hashed_password: str,
        full_name: str,
        role: str = "investigator",
        is_active: bool = True,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        db = get_async_db()
        now = datetime.now(timezone.utc)
        uid = str(user_id or uuid.uuid4())
        doc = {
            "id": uid,
            "email": email.lower().strip(),
            "hashed_password": hashed_password,
            "full_name": full_name.strip(),
            "role": role,
            "is_active": is_active,
            "created_at": now,
            "updated_at": now,
        }
        await db.users.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    async def list_users() -> List[Dict[str, Any]]:
        db = get_async_db()
        cursor = db.users.find({}).sort("created_at", -1)
        docs = await cursor.to_list(length=100)
        return serialize_docs(docs)


# ── 2. VIDEO REPOSITORY ───────────────────────────────────────────────────────

class MongoVideoRepository:
    @staticmethod
    async def get_by_id(video_id: str) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        doc = await db.videos.find_one({"id": str(video_id)})
        return serialize_doc(doc)

    @staticmethod
    def get_by_id_sync(video_id: str) -> Optional[Dict[str, Any]]:
        """Synchronous video getter for Celery tasks."""
        db = get_sync_db()
        doc = db.videos.find_one({"id": str(video_id)})
        return serialize_doc(doc)

    @staticmethod
    async def create_video(video_doc: Dict[str, Any]) -> Dict[str, Any]:
        db = get_async_db()
        doc = dict(video_doc)
        if "id" not in doc or not doc["id"]:
            doc["id"] = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        await db.videos.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    async def update_video(video_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        up = dict(updates)
        up["updated_at"] = datetime.now(timezone.utc)
        result = await db.videos.find_one_and_update(
            {"id": str(video_id)},
            {"$set": up},
            return_document=True,
        )
        return serialize_doc(result)

    @staticmethod
    def update_video_sync(video_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Synchronous video updater for Celery / thread workers."""
        db = get_sync_db()
        up = dict(updates)
        up["updated_at"] = datetime.now(timezone.utc)
        result = db.videos.find_one_and_update(
            {"id": str(video_id)},
            {"$set": up},
            return_document=True,
        )
        return serialize_doc(result)

    @staticmethod
    async def list_videos(
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = get_async_db()
        query: Dict[str, Any] = {}
        if status and status != "all":
            query["status"] = status
        if search:
            query["original_filename"] = {"$regex": search, "$options": "i"}

        cursor = db.videos.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return serialize_docs(docs)

    @staticmethod
    async def count_videos(status: Optional[str] = None) -> int:
        db = get_async_db()
        query = {"status": status} if status and status != "all" else {}
        return await db.videos.count_documents(query)

    @staticmethod
    async def delete_video(video_id: str) -> bool:
        db = get_async_db()
        vid = str(video_id)
        res = await db.videos.delete_one({"id": vid})
        # Cascade delete related records
        await db.detections.delete_many({"video_id": vid})
        await db.tracks.delete_many({"video_id": vid})
        await db.embeddings.delete_many({"video_id": vid})
        await db.processing_jobs.delete_many({"video_id": vid})
        return res.deleted_count > 0


# ── 3. DETECTIONS (EVENTS) REPOSITORY ─────────────────────────────────────────

class MongoDetectionRepository:
    @staticmethod
    async def get_by_video(
        video_id: str,
        class_name: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        db = get_async_db()
        query: Dict[str, Any] = {"video_id": str(video_id)}
        if class_name and class_name != "all":
            query["attributes.class_name"] = class_name.lower()
        if min_confidence is not None:
            query["confidence"] = {"$gte": float(min_confidence)}

        cursor = db.detections.find(query).sort("timestamp", 1)
        docs = await cursor.to_list(length=5000)
        return serialize_docs(docs)

    @staticmethod
    def get_by_video_sync(video_id: str) -> List[Dict[str, Any]]:
        db = get_sync_db()
        cursor = db.detections.find({"video_id": str(video_id)}).sort("timestamp", 1)
        return serialize_docs(list(cursor))

    @staticmethod
    def insert_detections_sync(detections_list: List[Dict[str, Any]]) -> int:
        """Batch inserts YOLO detections from video worker."""
        if not detections_list:
            return 0
        db = get_sync_db()
        now = datetime.now(timezone.utc)
        docs = []
        for d in detections_list:
            doc = dict(d)
            doc.setdefault("id", str(uuid.uuid4()))
            doc.setdefault("created_at", now)
            docs.append(doc)
        res = db.detections.insert_many(docs)
        return len(res.inserted_ids)

    @staticmethod
    async def count_detections(video_id: Optional[str] = None) -> int:
        db = get_async_db()
        query = {"video_id": str(video_id)} if video_id else {}
        return await db.detections.count_documents(query)


# ── 4. TRACKS REPOSITORY ──────────────────────────────────────────────────────

class MongoTrackRepository:
    @staticmethod
    async def get_by_video(
        video_id: str,
        object_class: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        db = get_async_db()
        query: Dict[str, Any] = {"video_id": str(video_id)}
        if object_class and object_class != "all":
            query["object_class"] = object_class.lower()

        cursor = db.tracks.find(query).sort("track_id", 1)
        docs = await cursor.to_list(length=1000)
        return serialize_docs(docs)

    @staticmethod
    def insert_tracks_sync(tracks_list: List[Dict[str, Any]]) -> int:
        """Batch inserts ByteTrack trajectories from video worker."""
        if not tracks_list:
            return 0
        db = get_sync_db()
        now = datetime.now(timezone.utc)
        docs = []
        for t in tracks_list:
            doc = dict(t)
            doc.setdefault("id", str(uuid.uuid4()))
            doc.setdefault("created_at", now)
            docs.append(doc)
        res = db.tracks.insert_many(docs)
        return len(res.inserted_ids)

    @staticmethod
    async def count_tracks(video_id: Optional[str] = None) -> int:
        db = get_async_db()
        query = {"video_id": str(video_id)} if video_id else {}
        return await db.tracks.count_documents(query)


# ── 5. EMBEDDINGS REPOSITORY (CLIP & VECTOR SEARCH) ──────────────────────────

class MongoEmbeddingRepository:
    @staticmethod
    def insert_embeddings_sync(embeddings_list: List[Dict[str, Any]]) -> int:
        """Batch inserts 512-dim CLIP visual/crop embeddings from worker."""
        if not embeddings_list:
            return 0
        db = get_sync_db()
        now = datetime.now(timezone.utc)
        docs = []
        for e in embeddings_list:
            doc = dict(e)
            doc.setdefault("id", str(uuid.uuid4()))
            doc.setdefault("created_at", now)
            docs.append(doc)
        res = db.embeddings.insert_many(docs)
        return len(res.inserted_ids)

    @staticmethod
    async def search_by_vector(
        query_vector: List[float],
        video_id: Optional[str] = None,
        top_k: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Executes semantic visual similarity search.
        Evaluates Atlas Vector Search ($vectorSearch) if configured,
        or computes exact in-memory cosine similarity via NumPy.
        """
        db = get_async_db()
        query: Dict[str, Any] = {}
        if video_id:
            query["video_id"] = str(video_id)

        # Retrieve candidate embeddings
        cursor = db.embeddings.find(query)
        candidates = await cursor.to_list(length=1000)
        if not candidates:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        results = []
        for doc in candidates:
            emb_arr = doc.get("embedding")
            if not emb_arr or len(emb_arr) != len(query_vector):
                continue
            e_vec = np.array(emb_arr, dtype=np.float32)
            e_norm = np.linalg.norm(e_vec)
            if e_norm == 0:
                continue
            score = float(np.dot(q_vec, e_vec) / (q_norm * e_norm))
            clean = serialize_doc(doc)
            clean["similarity_score"] = round(score, 4)
            results.append(clean)

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]


# ── 6. INVESTIGATION CASES REPOSITORY ─────────────────────────────────────────

class MongoCaseRepository:
    @staticmethod
    async def get_by_id(case_id: str) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        doc = await db.cases.find_one({"id": str(case_id)})
        return serialize_doc(doc)

    @staticmethod
    async def create_case(case_doc: Dict[str, Any]) -> Dict[str, Any]:
        db = get_async_db()
        doc = dict(case_doc)
        if "id" not in doc or not doc["id"]:
            doc["id"] = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        doc.setdefault("status", "open")
        doc.setdefault("priority", "medium")
        doc.setdefault("tags", [])
        await db.cases.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    async def update_case(case_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        up = dict(updates)
        up["updated_at"] = datetime.now(timezone.utc)
        result = await db.cases.find_one_and_update(
            {"id": str(case_id)},
            {"$set": up},
            return_document=True,
        )
        return serialize_doc(result)

    @staticmethod
    async def list_cases(
        user_id: Optional[str] = None,
        role: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        db = get_async_db()
        query: Dict[str, Any] = {}
        # Role-based case visibility: Admin sees all; investigators see owned/assigned
        if role and role != "admin" and user_id:
            query["$or"] = [
                {"owner_id": str(user_id)},
                {"lead_investigator_id": str(user_id)},
                {"reviewer_id": str(user_id)},
            ]

        cursor = db.cases.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return serialize_docs(docs)

    @staticmethod
    async def delete_case(case_id: str) -> bool:
        db = get_async_db()
        cid = str(case_id)
        res = await db.cases.delete_one({"id": cid})
        await db.evidence.delete_many({"case_id": cid})
        await db.reports.delete_many({"case_id": cid})
        return res.deleted_count > 0


# ── 7. EVIDENCE REPOSITORY ────────────────────────────────────────────────────

class MongoEvidenceRepository:
    @staticmethod
    async def get_by_case(case_id: str) -> List[Dict[str, Any]]:
        db = get_async_db()
        cursor = db.evidence.find({"case_id": str(case_id)}).sort("sequence_number", 1)
        docs = await cursor.to_list(length=1000)
        return serialize_docs(docs)

    @staticmethod
    async def get_by_id(evidence_id: str) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        doc = await db.evidence.find_one({"id": str(evidence_id)})
        return serialize_doc(doc)

    @staticmethod
    async def create_evidence(evidence_doc: Dict[str, Any]) -> Dict[str, Any]:
        db = get_async_db()
        doc = dict(evidence_doc)
        if "id" not in doc or not doc["id"]:
            doc["id"] = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        await db.evidence.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    async def update_evidence(evidence_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        up = dict(updates)
        up["updated_at"] = datetime.now(timezone.utc)
        result = await db.evidence.find_one_and_update(
            {"id": str(evidence_id)},
            {"$set": up},
            return_document=True,
        )
        return serialize_doc(result)

    @staticmethod
    async def delete_evidence(evidence_id: str) -> bool:
        db = get_async_db()
        res = await db.evidence.delete_one({"id": str(evidence_id)})
        return res.deleted_count > 0


# ── 8. REPORT REPOSITORY ──────────────────────────────────────────────────────

class MongoReportRepository:
    @staticmethod
    async def get_by_id(report_id: str) -> Optional[Dict[str, Any]]:
        db = get_async_db()
        doc = await db.reports.find_one({"id": str(report_id)})
        return serialize_doc(doc)

    @staticmethod
    async def get_by_case(case_id: str) -> List[Dict[str, Any]]:
        db = get_async_db()
        cursor = db.reports.find({"case_id": str(case_id)}).sort("created_at", -1)
        docs = await cursor.to_list(length=100)
        return serialize_docs(docs)

    @staticmethod
    async def list_reports(skip: int = 0, limit: int = 50) -> List[Dict[str, Any]]:
        db = get_async_db()
        cursor = db.reports.find({}).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return serialize_docs(docs)

    @staticmethod
    async def create_report(report_doc: Dict[str, Any]) -> Dict[str, Any]:
        db = get_async_db()
        doc = dict(report_doc)
        if "id" not in doc or not doc["id"]:
            doc["id"] = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        doc.setdefault("created_at", now)
        doc.setdefault("updated_at", now)
        doc.setdefault("status", "draft")
        await db.reports.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    async def delete_report(report_id: str) -> bool:
        db = get_async_db()
        res = await db.reports.delete_one({"id": str(report_id)})
        return res.deleted_count > 0


# ── 9. AUDIT LOG REPOSITORY ───────────────────────────────────────────────────

class MongoAuditRepository:
    @staticmethod
    async def log_event(
        action: str,
        target_type: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        target_id: Optional[str] = None,
        outcome: str = "success",
        client_ip: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        db = get_async_db()
        doc = {
            "id": str(uuid.uuid4()),
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "actor_id": str(actor_id) if actor_id else None,
            "actor_email": actor_email,
            "outcome": outcome,
            "client_ip": client_ip,
            "details": details or {},
            "created_at": datetime.now(timezone.utc),
        }
        await db.audit_logs.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    def log_event_sync(
        action: str,
        target_type: str,
        actor_id: Optional[str] = None,
        actor_email: Optional[str] = None,
        target_id: Optional[str] = None,
        outcome: str = "success",
        client_ip: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Synchronous audit log entry for background workers and sync callers."""
        db = get_sync_db()
        doc = {
            "id": str(uuid.uuid4()),
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id) if target_id else None,
            "actor_id": str(actor_id) if actor_id else None,
            "actor_email": actor_email,
            "outcome": outcome,
            "client_ip": client_ip,
            "details": details or {},
            "created_at": datetime.now(timezone.utc),
        }
        db.audit_logs.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    async def list_logs(skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        db = get_async_db()
        cursor = db.audit_logs.find({}).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return serialize_docs(docs)

    @staticmethod
    async def count_logs() -> int:
        db = get_async_db()
        return await db.audit_logs.count_documents({})


# ── 10. PROCESSING JOBS REPOSITORY ───────────────────────────────────────────

class MongoJobRepository:
    @staticmethod
    async def create_job(video_id: str, task_id: Optional[str] = None) -> Dict[str, Any]:
        db = get_async_db()
        now = datetime.now(timezone.utc)
        doc = {
            "id": str(uuid.uuid4()),
            "video_id": str(video_id),
            "task_id": task_id,
            "status": "queued",
            "progress": 0.0,
            "stage": "enqueued",
            "error_message": None,
            "created_at": now,
            "updated_at": now,
        }
        await db.processing_jobs.insert_one(doc)
        return serialize_doc(doc)  # type: ignore

    @staticmethod
    def update_job_sync(
        video_id: str,
        status: str,
        progress: float,
        stage: str,
        error_message: Optional[str] = None,
    ) -> None:
        db = get_sync_db()
        now = datetime.now(timezone.utc)
        db.processing_jobs.update_one(
            {"video_id": str(video_id)},
            {
                "$set": {
                    "status": status,
                    "progress": progress,
                    "stage": stage,
                    "error_message": error_message,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
