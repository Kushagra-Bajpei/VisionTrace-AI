"""
Phase 4A Tests – Celery Tasks, Frame Extraction & Background Processing Lifecycle.
Tests task registration, synthetic video frame extraction, duplicate task suppression,
atomic status transitions, broker unavailability handling, and frame API endpoints.
"""
import io
import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import patch
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from app.models.video import Video
from app.services.video_service import video_service
from app.tasks.video_tasks import enqueue_video_processing, process_video_task

settings = get_settings()

from tests.conftest import (
    shared_test_engine as test_engine,
    SharedTestingSessionLocal as TestingSessionLocal,
)


def generate_test_mp4(duration_seconds: int = 2) -> bytes:
    """Generate a clean synthetic MP4 video with known duration and frame rate (10 fps)."""
    temp_filename = f"temp_synth_{uuid.uuid4().hex}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 10.0
    width, height = 320, 240
    out = cv2.VideoWriter(temp_filename, fourcc, fps, (width, height))

    total_frames = int(fps * duration_seconds)
    for i in range(total_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = (i * 10 % 255, 120, 180)
        out.write(frame)
    out.release()

    with open(temp_filename, "rb") as f:
        data = f.read()

    if os.path.exists(temp_filename):
        os.remove(temp_filename)

    return data


def test_celery_configuration():
    """Verify Celery application config, serializer, and task discovery."""
    assert celery_app.conf.task_serializer == "json"
    assert celery_app.conf.result_serializer == "json"
    assert celery_app.conf.timezone == "UTC"
    assert "app.tasks.video_tasks.process_video_task" in celery_app.tasks


def test_frame_extraction_synthetic_video():
    """Extract frames from synthetic video at 1.0 fps and verify deterministic output."""
    raw_bytes = generate_test_mp4(duration_seconds=2)
    video_id = str(uuid.uuid4())
    temp_video_path = settings.videos_dir / f"test_{video_id}.mp4"

    with open(temp_video_path, "wb") as f:
        f.write(raw_bytes)

    try:
        progress_reports = []

        def track_progress(pct: float):
            progress_reports.append(pct)

        count, frames = video_service.extract_frames(
            video_path=temp_video_path,
            video_id=video_id,
            target_fps=1.0,
            progress_callback=track_progress,
        )

        # 2-second video at 1.0 fps samples t=0.0, 1.0 (2 frames in 20-frame stream)
        assert count == 2
        assert len(frames) == 2
        assert frames[0]["filename"] == "frame_000000.jpg"
        assert frames[0]["timestamp_seconds"] == 0.0
        assert frames[1]["filename"] == "frame_000001.jpg"
        assert frames[1]["timestamp_seconds"] == 1.0
        assert len(progress_reports) > 0
    finally:
        video_service.delete_files(f"test_{video_id}.mp4", video_id=video_id)


def test_process_video_task_lifecycle(monkeypatch):
    """Test full processing lifecycle from uploaded -> processing -> completed with DB updates."""
    # Override SessionLocal in video_tasks to use test in-memory SQLite
    monkeypatch.setattr("app.tasks.video_tasks.SessionLocal", TestingSessionLocal)

    raw_bytes = generate_test_mp4(duration_seconds=2)
    unique_filename = f"lifecycle_{uuid.uuid4().hex}.mp4"
    video_path = settings.videos_dir / unique_filename
    with open(video_path, "wb") as f:
        f.write(raw_bytes)

    db = TestingSessionLocal()
    video = Video(
        filename=unique_filename,
        original_filename="sample_cam.mp4",
        file_path=f"videos/{unique_filename}",
        file_size=len(raw_bytes),
        duration=2.0,
        fps=10.0,
        status="uploaded",
        processing_progress=0.0,
        video_metadata={"codec": "mp4v"},
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    video_id_str = str(video.id)
    db.close()

    try:
        # Run Celery task directly
        res = process_video_task(video_id_str)
        assert res["status"] == "completed"
        assert res["extracted_frames_count"] == 2

        # Verify database state
        db2 = TestingSessionLocal()
        v_updated = db2.scalar(select(Video).where(Video.id == uuid.UUID(video_id_str)))
        assert v_updated is not None
        assert v_updated.status == "completed"
        assert v_updated.processing_progress == 100.0
        assert v_updated.video_metadata["extracted_frames_count"] == 2
        assert v_updated.video_metadata["frames_dir"] == f"frames/{video_id_str}"
        db2.close()
    finally:
        video_service.delete_files(unique_filename, video_id=video_id_str)


def test_duplicate_job_suppression(monkeypatch):
    """Verify that calling process_video_task on an already completed video is skipped."""
    monkeypatch.setattr("app.tasks.video_tasks.SessionLocal", TestingSessionLocal)

    db = TestingSessionLocal()
    video = Video(
        filename="dummy.mp4",
        original_filename="dummy.mp4",
        file_path="videos/dummy.mp4",
        file_size=100,
        status="completed",
        processing_progress=100.0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    video_id_str = str(video.id)
    db.close()

    res = process_video_task(video_id_str)
    assert res["status"] == "skipped"
    assert "Already processing or completed" in res["reason"]


def test_missing_video_file_failure(monkeypatch):
    """Verify that missing file transitions video to 'failed' status with descriptive error."""
    monkeypatch.setattr("app.tasks.video_tasks.SessionLocal", TestingSessionLocal)

    db = TestingSessionLocal()
    video = Video(
        filename="nonexistent_ghost_file.mp4",
        original_filename="ghost.mp4",
        file_path="videos/nonexistent_ghost_file.mp4",
        file_size=100,
        status="queued",
        processing_progress=0.0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    video_id_str = str(video.id)
    db.close()

    res = process_video_task(video_id_str)
    assert res["status"] == "failed"
    assert "not found" in res["error"]

    db2 = TestingSessionLocal()
    v_updated = db2.scalar(select(Video).where(Video.id == uuid.UUID(video_id_str)))
    assert v_updated.status == "failed"
    assert "not found" in v_updated.error_message
    db2.close()


def test_enqueue_broker_unavailable_graceful_recovery():
    """Verify that if Celery broker is unavailable, video stays 'uploaded' with actionable retry message."""
    db = TestingSessionLocal()
    video = Video(
        filename="offline_broker.mp4",
        original_filename="offline.mp4",
        file_path="videos/offline_broker.mp4",
        file_size=100,
        status="uploaded",
        processing_progress=0.0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)

    # 1. Simulate fast broker offline probe (port 6379 not listening)
    with patch("app.tasks.video_tasks.is_broker_available", return_value=False):
        success, err = enqueue_video_processing(video.id, db)
        assert success is False
        assert "broker unavailable" in err.lower()

    db.refresh(video)
    # Architectural requirement 1: Never leave in phantom 'queued' state
    assert video.status == "uploaded"
    assert "broker unavailable" in video.error_message.lower()
    assert "Ready to retry" in video.error_message

    # 2. Simulate broker connection drop during publish
    with patch("app.tasks.video_tasks.is_broker_available", return_value=True), patch(
        "app.tasks.video_tasks.process_video_task.apply_async",
        side_effect=Exception("Redis connection refused"),
    ):
        success, err = enqueue_video_processing(video.id, db)
        assert success is False
        assert "Redis connection refused" in err

    db.refresh(video)
    assert video.status == "uploaded"
    assert "Queue broker unavailable" in video.error_message
    db.close()


def test_frames_api_endpoints(client: TestClient, monkeypatch):
    """Test listing extracted frames and serving individual frame files with traversal guard."""
    monkeypatch.setattr("app.tasks.video_tasks.SessionLocal", TestingSessionLocal)

    raw_bytes = generate_test_mp4(duration_seconds=1)
    unique_name = f"api_test_{uuid.uuid4().hex}.mp4"
    video_path = settings.videos_dir / unique_name
    with open(video_path, "wb") as f:
        f.write(raw_bytes)

    db = TestingSessionLocal()
    video = Video(
        filename=unique_name,
        original_filename="front_cam.mp4",
        file_path=f"videos/{unique_name}",
        file_size=len(raw_bytes),
        duration=1.0,
        fps=10.0,
        status="uploaded",
        processing_progress=0.0,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    video_id = video.id
    db.close()

    try:
        # Extract frames
        process_video_task(str(video_id))

        # 1. Test GET /frames
        frames_res = client.get(f"/api/v1/videos/{video_id}/frames")
        assert frames_res.status_code == 200
        frames_data = frames_res.json()
        assert len(frames_data) >= 1
        first_frame = frames_data[0]
        assert "filename" in first_frame
        assert "timestamp_seconds" in first_frame
        assert "preview_url" in first_frame

        # 2. Test GET /frames/{frame_filename}
        frame_file_res = client.get(f"/api/v1/videos/{video_id}/frames/{first_frame['filename']}")
        assert frame_file_res.status_code == 200
        assert frame_file_res.headers["content-type"] == "image/jpeg"

        # 3. Test path traversal protection on frames endpoint
        bad_frame_res = client.get(f"/api/v1/videos/{video_id}/frames/../../etc/passwd")
        assert bad_frame_res.status_code in (400, 404)
    finally:
        video_service.delete_files(unique_name, video_id=str(video_id))
