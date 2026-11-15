"""
Video processing background tasks.
Handles asynchronous frame extraction, real-time progress persistence,
duplicate task suppression, and safe error transitions.
"""
import logging
import socket
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.event import Event
from app.models.video import Video
from app.services.embedding_service import embedding_service
from app.services.tracking_service import tracking_service
from app.services.video_service import video_service

logger = logging.getLogger(__name__)
settings = get_settings()


def is_broker_available(broker_url: str) -> bool:
    """Fast 150ms probe to check if the background queue broker is reachable."""
    try:
        host = "127.0.0.1"
        port = 6379
        if "://" in broker_url:
            clean = broker_url.split("://")[-1].split("/")[0]
            if "@" in clean:
                clean = clean.split("@")[-1]
            if ":" in clean:
                parts = clean.split(":")
                host = parts[0]
                port = int(parts[1])
            else:
                host = clean
        with socket.create_connection((host, port), timeout=0.15):
            return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def _run_task_in_thread(video_id_str: str) -> None:
    """
    Runs process_video_task synchronously in a background thread.
    Used as a dev-mode fallback when the Celery/Redis broker is unavailable.
    Uses .run() to bypass Celery's broker and invoke the task body directly.
    Each invocation opens its own DB session (via SessionLocal inside the task).
    """
    try:
        logger.info("Dev-mode thread: starting inline processing for video %s", video_id_str)
        process_video_task.run(video_id_str)
        logger.info("Dev-mode thread: finished inline processing for video %s", video_id_str)
    except Exception as exc:
        logger.exception("Dev-mode thread: unhandled error processing video %s: %s", video_id_str, exc)


def enqueue_video_processing(video_id: uuid.UUID, db: Session) -> Tuple[bool, Optional[str]]:
    """
    Safely enqueues a video for background processing with Celery.

    In development mode, when the Redis/Celery broker is unavailable, the task
    is executed directly in a background thread so that processing still works
    without needing Redis installed locally.

    Guarantees:
    1. Atomic status transition: sets status to 'queued' only when task delivery succeeds.
    2. Never leaves a video stuck in a phantom 'queued' state if delivery fails.
    Returns (success, error_message).
    """
    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        return False, f"Video '{video_id}' not found"

    if video.status in ("queued", "processing"):
        return True, "Job is already queued or processing"

    # Fast probe: check if broker is reachable
    broker_online = is_broker_available(settings.celery_broker_url)

    # ── Development fallback: run inline in a background thread ─────────────
    if not broker_online and settings.app_env == "development":
        video.status = "queued"
        video.processing_progress = 0.0
        video.error_message = None
        try:
            db.commit()
        except Exception:
            db.rollback()
            return False, "Database error while setting video to queued state."

        video_id_str = str(video_id)
        thread = threading.Thread(
            target=_run_task_in_thread,
            args=(video_id_str,),
            daemon=True,
            name=f"vt-process-{video_id_str[:8]}",
        )
        thread.start()
        logger.info(
            "Dev-mode: Redis broker offline. Running video %s processing in background thread %s.",
            video_id,
            thread.name,
        )
        return True, None

    # ── Production / broker offline in production: return error ─────────────
    if not broker_online:
        video.status = "uploaded"
        video.error_message = "Background worker broker unavailable (port 6379 offline). Ready to retry."
        try:
            db.commit()
        except Exception:
            db.rollback()
        logger.info(
            "Broker %s is offline. Video %s kept in 'uploaded' state.",
            settings.celery_broker_url,
            video_id,
        )
        return False, "Background worker broker unavailable. Ready to retry."

    # ── Happy path: enqueue via Celery ───────────────────────────────────────
    try:
        task = process_video_task.apply_async(args=[str(video_id)], retry=False)
        video.status = "queued"
        video.processing_progress = 0.0
        video.error_message = None
        db.commit()
        logger.info("Enqueued video processing task %s for video %s", task.id, video_id)
        return True, None
    except Exception as exc:
        db.rollback()
        video.status = "uploaded"
        video.error_message = f"Queue broker unavailable: {str(exc)}. Ready to retry."
        try:
            db.commit()
        except Exception:
            db.rollback()
        logger.warning(
            "Could not enqueue processing for video %s (broker unavailable: %s). Kept in 'uploaded' state.",
            video_id,
            exc,
        )
        return False, f"Worker broker unavailable: {str(exc)}"


@celery_app.task(bind=True, name="app.tasks.video_tasks.process_video_task")
def process_video_task(self, video_id_str: str) -> Dict[str, Any]:
    """
    Asynchronous Celery task that processes an uploaded CCTV video:
    1. Prevents duplicate concurrent execution via atomic DB conditional update.
    2. Validates video file existence and integrity.
    3. Samples frames at configurable interval (default: 1 frame per second).
    4. Deterministically saves extracted frames to storage/frames/{video_id}/frame_{index:06d}.jpg.
    5. Persists real progress milestones to the database.
    6. Ensures full completion: marks status='completed' and progress=100 only after
       all frames and metadata are safely committed.
    """
    try:
        video_uuid = uuid.UUID(video_id_str)
    except ValueError:
        return {"status": "failed", "error": f"Invalid UUID string: {video_id_str}"}

    db: Session = SessionLocal()
    try:
        # ── 1. Atomic Lock: Prevent concurrent duplicate execution ───────────────
        stmt = (
            update(Video)
            .where(
                Video.id == video_uuid,
                Video.status.in_(["uploaded", "queued", "failed"]),
            )
            .values(
                status="processing",
                processing_progress=0.0,
                error_message=None,
            )
            .returning(Video.id, Video.filename, Video.original_filename, Video.video_metadata)
        )
        result = db.execute(stmt)
        row = result.fetchone()
        db.commit()

        if not row:
            logger.info("Video %s is already processing or completed. Suppressing duplicate job.", video_id_str)
            return {"status": "skipped", "reason": "Already processing or completed"}

        _, filename, original_filename, existing_meta = row
        existing_meta = existing_meta or {}

        # ── 2. Validate video file on disk ───────────────────────────────────────
        video_path = video_service.resolve_safe_path(video_service.videos_dir, filename)
        if not video_path.exists():
            err_msg = f"Video file '{filename}' not found on storage disk."
            _mark_failed(db, video_uuid, err_msg)
            return {"status": "failed", "error": err_msg}

        # ── 3. Callbacks for progress and deletion check ─────────────────────────
        last_reported_progress = 0.0

        def update_progress(pct: float):
            nonlocal last_reported_progress
            if pct - last_reported_progress >= 4.0 or pct >= 99.0:
                last_reported_progress = pct
                try:
                    db.execute(
                        update(Video)
                        .where(Video.id == video_uuid)
                        .values(processing_progress=round(pct, 1))
                    )
                    db.commit()
                except Exception:
                    db.rollback()

        def on_extraction_progress(pct: float):
            # Scale frame extraction to 0% -> 35%
            scaled = (pct / 100.0) * 35.0
            update_progress(scaled)

        def on_tracking_progress(pct: float):
            # Scale YOLO & ByteTrack tracking to 35% -> 85%
            scaled = 35.0 + (pct / 100.0) * 50.0
            update_progress(scaled)

        def should_cancel() -> bool:
            # Check if video was deleted from DB while task is executing
            exists = db.scalar(select(Video.id).where(Video.id == video_uuid))
            return exists is None

        # ── 4. Extract frames sequentially ───────────────────────────────────────
        logger.info(
            "Starting frame extraction for video %s (%s) at %.1f fps",
            video_uuid,
            original_filename,
            settings.frame_extraction_fps,
        )

        extracted_count, frame_records = video_service.extract_frames(
            video_path=video_path,
            video_id=video_id_str,
            target_fps=settings.frame_extraction_fps,
            progress_callback=on_extraction_progress,
            should_cancel_callback=should_cancel,
        )

        # If deleted during extraction, clean up and exit cleanly
        if should_cancel():
            logger.info("Video %s was deleted during processing. Aborting.", video_uuid)
            video_service.delete_files(filename, video_id=video_id_str)
            return {"status": "aborted", "reason": "Video was deleted during processing"}

        if extracted_count == 0:
            err_msg = "No decodable video frames could be extracted from video stream."
            _mark_failed(db, video_uuid, err_msg)
            return {"status": "failed", "error": err_msg}

        # ── 5. Run YOLO object detection and ByteTrack tracking ──────────────────
        logger.info(
            "Running YOLO detection and ByteTrack tracking on %d extracted frames for video %s",
            len(frame_records),
            video_uuid,
        )
        update_progress(35.0)

        detections, tracks = tracking_service.detect_and_track_frames(
            video_id=video_uuid,
            frame_records=frame_records,
            progress_callback=on_tracking_progress,
            should_cancel_callback=should_cancel,
        )

        if should_cancel():
            logger.info("Video %s was deleted during tracking. Aborting.", video_uuid)
            video_service.delete_files(filename, video_id=video_id_str)
            return {"status": "aborted", "reason": "Video was deleted during tracking"}

        # ── 6. Persist Detections, Tracks, and Summary Metadata ──────────────────
        update_progress(82.0)
        persist_stats = tracking_service.persist_tracking_results(
            db=db,
            video_id=video_uuid,
            detections=detections,
            tracks=tracks,
        )

        # ── 7. Visual Similarity Indexing (CLIP Keyframes & Detection Crops) ─────────
        update_progress(85.0)
        persisted_events = db.scalars(
            select(Event).where(Event.video_id == video_uuid, Event.event_type == "object_detection")
        ).all()

        visual_stats = {"indexed_keyframes": 0, "indexed_crops": 0, "skipped": 0, "errors": []}
        try:
            visual_stats = embedding_service.index_video_visuals(
                db=db,
                video_id=video_uuid,
                frame_records=frame_records,
                detections=persisted_events,
                progress_callback=update_progress,
                should_cancel_callback=should_cancel,
            )
        except Exception as emb_exc:
            logger.warning("Visual indexing non-fatal error for video %s: %s", video_uuid, emb_exc)
            visual_stats["errors"].append(str(emb_exc))

        # ── 8. Atomic Completion: Commit progress=100 and status='completed' ─────
        updated_metadata = dict(existing_meta)
        updated_metadata.update(
            {
                "extracted_frames_count": extracted_count,
                "frame_interval_seconds": round(1.0 / settings.frame_extraction_fps, 2),
                "frames_dir": f"frames/{video_id_str}",
                "detections_count": persist_stats["detections_count"],
                "tracks_count": persist_stats["tracks_count"],
                "detected_classes": persist_stats["detected_classes"],
                "yolo_model": settings.yolo_model_name,
                "tracker": settings.yolo_tracker_config,
                "clip_model": embedding_service.full_model_identifier,
                "indexed_keyframes": visual_stats["indexed_keyframes"],
                "indexed_crops": visual_stats["indexed_crops"],
            }
        )

        db.execute(
            update(Video)
            .where(Video.id == video_uuid)
            .values(
                status="completed",
                processing_progress=100.0,
                error_message=None,
                video_metadata=updated_metadata,
            )
        )
        db.commit()

        logger.info(
            "Video %s processing completed: %d frames, %d detections, %d tracks. Classes: %s",
            video_uuid,
            extracted_count,
            persist_stats["detections_count"],
            persist_stats["tracks_count"],
            persist_stats["detected_classes"],
        )
        return {
            "status": "completed",
            "video_id": video_id_str,
            "extracted_frames_count": extracted_count,
            "detections_count": persist_stats["detections_count"],
            "tracks_count": persist_stats["tracks_count"],
            "detected_classes": persist_stats["detected_classes"],
        }

    except Exception as exc:
        db.rollback()
        logger.exception("Unexpected error processing video %s: %s", video_id_str, exc)
        _mark_failed(db, video_uuid, f"Processing failed: {str(exc)}")
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


def _mark_failed(db: Session, video_id: uuid.UUID, error_msg: str):
    """Safely records task failure in the database."""
    try:
        db.execute(
            update(Video)
            .where(Video.id == video_id)
            .values(
                status="failed",
                error_message=error_msg,
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("Failed to update video %s status to failed: %s", video_id, exc)
