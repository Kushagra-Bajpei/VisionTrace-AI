"""
Phase 3 Video Library API Tests.
Tests upload validation, OpenCV metadata extraction, thumbnail generation,
HTTP Range streaming, video filtering, stats summary, security traversal checks, and deletion.
"""
import io
import os
import uuid
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.database import Base, get_db
from app.main import app
from app.services.video_service import video_service

from tests.conftest import (
    shared_test_engine as test_engine,
    SharedTestingSessionLocal as TestingSessionLocal,
)


def generate_sample_mp4() -> bytes:
    """Generate a clean 1-second synthetic MP4 video in memory."""
    temp_filename = f"temp_test_{uuid.uuid4().hex}.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    fps = 10.0
    width, height = 320, 240
    out = cv2.VideoWriter(temp_filename, fourcc, fps, (width, height))

    # Write 10 colored frames (1 second of footage)
    for i in range(10):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        frame[:, :] = (i * 20, 100, 200)
        out.write(frame)
    out.release()

    with open(temp_filename, "rb") as f:
        data = f.read()

    if os.path.exists(temp_filename):
        os.remove(temp_filename)

    return data


def test_reject_invalid_extension(client: TestClient):
    """Verify that non-video file extensions are rejected with 400 Bad Request."""
    fake_file = io.BytesIO(b"malicious script or text file")
    response = client.post(
        "/api/v1/videos/upload",
        files={"file": ("malware.exe", fake_file, "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "Unsupported video format" in response.json()["detail"]


def test_reject_invalid_mime_type(client: TestClient):
    """Verify that unsupported MIME types with video extension are rejected."""
    fake_file = io.BytesIO(b"fake image bytes")
    response = client.post(
        "/api/v1/videos/upload",
        files={"file": ("photo.mp4", fake_file, "image/png")},
    )
    assert response.status_code == 400
    assert "Unsupported MIME type" in response.json()["detail"]


def test_reject_corrupted_video_content(client: TestClient):
    """Verify that a corrupted video file is caught during OpenCV integrity inspection."""
    corrupted_data = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00isomcorruptedjunkbytes" + b"\x00" * 200
    fake_file = io.BytesIO(corrupted_data)
    response = client.post(
        "/api/v1/videos/upload",
        files={"file": ("corrupt.mp4", fake_file, "video/mp4")},
    )
    assert response.status_code == 400
    assert "Corrupted or unreadable" in response.json()["detail"]


def test_reject_file_size_limit(client: TestClient, monkeypatch):
    """Verify that uploads exceeding MAX_UPLOAD_SIZE_MB are rejected with 413."""
    settings = get_settings()
    monkeypatch.setattr(settings, "max_upload_size_mb", 0)  # 0 MB forces immediate exceed

    small_payload = io.BytesIO(b"data that exceeds zero limit")
    response = client.post(
        "/api/v1/videos/upload",
        files={"file": ("clip.mp4", small_payload, "video/mp4")},
    )
    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"]


def test_upload_and_extract_metadata(client: TestClient):
    """Upload synthetic MP4 footage and verify automatic metadata extraction."""
    video_bytes = generate_sample_mp4()
    file_payload = ("lobby_cam_01.mp4", io.BytesIO(video_bytes), "video/mp4")

    response = client.post(
        "/api/v1/videos/upload",
        files={"file": file_payload},
    )
    assert response.status_code == 201
    data = response.json()

    assert data["original_filename"] == "lobby_cam_01.mp4"
    assert data["status"] == "uploaded"
    assert data["width"] == 320
    assert data["height"] == 240
    assert data["fps"] == 10.0
    assert data["duration"] == 1.0
    assert data["thumbnail_path"] is not None
    assert "id" in data

    video_id = data["id"]

    # 1. Test get video details
    get_res = client.get(f"/api/v1/videos/{video_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == video_id

    # 2. Test video summary stats
    stats_res = client.get("/api/v1/videos/stats/summary")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert stats["total_videos"] >= 1
    assert stats["uploaded_count"] >= 1
    assert stats["total_duration_seconds"] >= 1.0

    # 3. Test thumbnail retrieval
    thumb_res = client.get(f"/api/v1/videos/{video_id}/thumbnail")
    assert thumb_res.status_code == 200
    assert thumb_res.headers["content-type"] == "image/jpeg"

    # 4. Test video streaming without Range (full file 200)
    full_stream_res = client.get(f"/api/v1/videos/{video_id}/stream")
    assert full_stream_res.status_code == 200
    assert full_stream_res.headers["accept-ranges"] == "bytes"

    # 5. Test video streaming with Range request (206 Partial Content)
    stream_res = client.get(
        f"/api/v1/videos/{video_id}/stream",
        headers={"Range": "bytes=0-100"},
    )
    assert stream_res.status_code == 206
    assert "bytes 0-100/" in stream_res.headers["content-range"]

    # 6. Test search filter
    search_res = client.get("/api/v1/videos?search=lobby")
    assert search_res.status_code == 200
    assert len(search_res.json()) >= 1

    search_miss = client.get("/api/v1/videos?search=nonexistent")
    assert search_miss.status_code == 200
    assert len(search_miss.json()) == 0

    # 7. Test status filter
    status_res = client.get("/api/v1/videos?status=uploaded")
    assert status_res.status_code == 200
    assert len(status_res.json()) >= 1

    # 8. Test delete video
    del_res = client.delete(f"/api/v1/videos/{video_id}")
    assert del_res.status_code == 204

    # Verify video is gone
    get_after = client.get(f"/api/v1/videos/{video_id}")
    assert get_after.status_code == 404


def test_get_nonexistent_video(client: TestClient):
    """Verify 404 when querying a non-existent video UUID."""
    random_id = uuid.uuid4()
    res = client.get(f"/api/v1/videos/{random_id}")
    assert res.status_code == 404
    assert f"Video '{random_id}' not found" in res.json()["detail"]


def test_delete_nonexistent_video(client: TestClient):
    """Verify 404 when attempting to delete a non-existent video UUID."""
    random_id = uuid.uuid4()
    res = client.delete(f"/api/v1/videos/{random_id}")
    assert res.status_code == 404


def test_path_traversal_protection():
    """Verify that resolve_safe_path raises 400 on attempted directory traversal."""
    settings = get_settings()
    base = settings.videos_dir
    with pytest.raises(HTTPException) as exc_info:
        video_service.resolve_safe_path(base, "../../etc/passwd")
    assert exc_info.value.status_code == 400
    assert "Path traversal detected" in exc_info.value.detail
