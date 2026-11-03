"""
Unit and integration tests for Phase 6: Visual Similarity Search & CLIP Multimodal Ranking.
"""
import os
import uuid
import numpy as np
import cv2
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app
from app.core.config import get_settings
from app.models.video import Video
from app.models.event import Event
from app.models.embedding import Embedding, CLIP_EMBEDDING_DIM
from app.services.embedding_service import embedding_service
from app.services.search_service import search_engine
from tests.conftest import SharedTestingSessionLocal

settings = get_settings()


@pytest.fixture(autouse=True)
def force_mock_embeddings(monkeypatch):
    """Ensure fast, deterministic test execution with zero external model download."""
    monkeypatch.setenv("MOCK_EMBEDDINGS", "1")
    embedding_service._model = None


@pytest.fixture
def db():
    """Local SQLAlchemy session using shared test DB."""
    session = SharedTestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_embedding_dimension_and_normalization():
    """Verify that CLIP vectors are strictly 512 dimensions and unit-normalized."""
    vec = embedding_service.embed_text("person in dark coat")
    assert len(vec) == CLIP_EMBEDDING_DIM
    arr = np.array(vec, dtype=np.float32)
    norm = np.linalg.norm(arr)
    assert pytest.approx(norm, 0.01) == 1.0


def test_crop_extraction_valid_and_degenerate(tmp_path):
    """Verify crop extraction logic, bounding-box conversion, and degenerate box rejection."""
    img_path = tmp_path / "test_frame.jpg"
    test_img = np.zeros((200, 200, 3), dtype=np.uint8)
    test_img[40:160, 40:160] = (0, 255, 0)
    cv2.imwrite(str(img_path), test_img)

    valid_bbox = {"x_min": 0.2, "y_min": 0.2, "x_max": 0.8, "y_max": 0.8}
    out_crop = tmp_path / "crop.jpg"
    crop = embedding_service.extract_crop(img_path, valid_bbox, output_path=out_crop)
    assert crop is not None
    assert crop.shape[0] > 10
    assert crop.shape[1] > 10
    assert out_crop.exists()

    degenerate_bbox = {"x_min": 0.5, "y_min": 0.5, "x_max": 0.51, "y_max": 0.51}
    bad_crop = embedding_service.extract_crop(img_path, degenerate_bbox)
    assert bad_crop is None


def test_idempotent_visual_indexing(db, tmp_path):
    """Verify that visual indexing creates embeddings and is 100% idempotent across runs."""
    video = Video(
        filename="test_surveillance.mp4",
        original_filename="test_surveillance.mp4",
        file_path="/storage/videos/test_surveillance.mp4",
        file_size=1000,
        status="completed",
    )
    db.add(video)
    db.commit()

    f_path = tmp_path / "frame_000001.jpg"
    cv2.imwrite(str(f_path), np.full((100, 100, 3), 128, dtype=np.uint8))

    event = Event(
        video_id=video.id,
        timestamp=1.0,
        event_type="object_detection",
        description="Person detected",
        confidence=0.92,
        bounding_box={"x_min": 0.1, "y_min": 0.1, "x_max": 0.9, "y_max": 0.9},
        frame_path=str(f_path),
    )
    db.add(event)
    db.commit()

    frame_records = [{"frame_path": str(f_path), "timestamp_seconds": 1.0}]

    stats1 = embedding_service.index_video_visuals(
        db=db,
        video_id=video.id,
        frame_records=frame_records,
        detections=[event],
    )
    assert stats1["indexed_keyframes"] == 1
    assert stats1["indexed_crops"] == 1

    count1 = db.scalar(select(Embedding).where(Embedding.video_id == video.id))
    assert count1 is not None

    stats2 = embedding_service.index_video_visuals(
        db=db,
        video_id=video.id,
        frame_records=frame_records,
        detections=[event],
    )
    assert stats2["skipped"] >= 2
    assert stats2["indexed_keyframes"] == 0
    assert stats2["indexed_crops"] == 0


def test_visual_similarity_search_endpoint(db, tmp_path, client):
    """Test full search flow with visual similarity descriptors."""

    video = Video(
        filename="lobby_cam.mp4",
        original_filename="lobby_cam.mp4",
        file_path="/storage/videos/lobby_cam.mp4",
        file_size=5000,
        status="completed",
    )
    db.add(video)
    db.commit()

    f_path = tmp_path / "lobby_frame.jpg"
    cv2.imwrite(str(f_path), np.full((120, 120, 3), 200, dtype=np.uint8))

    event = Event(
        video_id=video.id,
        timestamp=3.5,
        event_type="object_detection",
        description="person",
        confidence=0.95,
        bounding_box={"x_min": 0.1, "y_min": 0.1, "x_max": 0.8, "y_max": 0.8},
        frame_path=str(f_path),
        attributes={"class_name": "person"},
    )
    db.add(event)
    db.commit()

    embedding_service.index_video_visuals(
        db=db,
        video_id=video.id,
        frame_records=[{"frame_path": str(f_path), "timestamp_seconds": 3.5}],
        detections=[event],
    )

    resp = client.post(
        "/api/v1/search/query",
        json={
            "query": "Person wearing a dark jacket",
            "video_id": str(video.id),
            "visual_search": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matches"] >= 1
    assert data["parsed_facets"]["is_visual_search"] is True
    assert len(data["parsed_facets"]["visual_descriptors"]) > 0

    det = data["detections"][0]
    assert det["crop_image_url"] is not None
    assert "/crops/" in det["crop_image_url"]
    assert "visual_similarity_score" in det


def test_crops_endpoint_security(db, tmp_path, client):
    """Verify safe crop retrieval and rejection of path traversal."""

    video = Video(
        filename="corridor.mp4",
        original_filename="corridor.mp4",
        file_path="/storage/videos/corridor.mp4",
        file_size=1000,
        status="completed",
    )
    db.add(video)
    db.commit()

    resp_traversal = client.get(f"/api/v1/videos/{video.id}/crops/../../etc/passwd")
    assert resp_traversal.status_code in (400, 404)

    random_uuid = uuid.uuid4()
    resp_404 = client.get(f"/api/v1/videos/{video.id}/crops/{random_uuid}.jpg")
    assert resp_404.status_code == 404
