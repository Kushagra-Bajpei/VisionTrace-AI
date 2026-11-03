"""
Phase 4B Tests: YOLO Object Detection, ByteTrack Tracking, and Tracking Endpoints.
Verifies real detection extraction, track persistence, and API delivery.
"""
import uuid
from pathlib import Path
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.models.event import Event
from app.models.track import Track
from app.models.video import Video
from app.services.tracking_service import DetectionItem, TrackSummary, tracking_service
from app.tasks.video_tasks import process_video_task


@pytest.fixture
def sample_video_record(db_tables):
    """Creates a sample Video record in the test database."""
    from tests.conftest import SharedTestingSessionLocal

    db = SharedTestingSessionLocal()
    try:
        video = Video(
            id=uuid.uuid4(),
            filename="test_surveillance_cctv.mp4",
            original_filename="cctv_gate.mp4",
            file_path="videos/test_surveillance_cctv.mp4",
            file_size=1024 * 1024,
            duration=5.0,
            width=1920,
            height=1080,
            fps=25.0,
            status="uploaded",
            processing_progress=0.0,
            video_metadata={"frame_count": 125},
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video
    finally:
        db.close()


def test_yolo_model_lazy_loading():
    """Verify YOLO model loads properly from configured path."""
    model = tracking_service.get_model()
    assert model is not None
    assert hasattr(model, "names")
    assert 0 in model.names
    assert model.names[0] == "person"


def test_persist_tracking_results_integrity(sample_video_record):
    """
    Test that tracking results properly persist into the 'tracks' and 'events' tables
    with valid foreign keys and metadata updates.
    """
    from tests.conftest import SharedTestingSessionLocal

    db = SharedTestingSessionLocal()
    try:
        vid_id = sample_video_record.id

        # Create dummy detection items and track summary
        detections = [
            DetectionItem(
                frame_index=0,
                timestamp=0.0,
                frame_path=f"frames/{vid_id}/frame_000000.jpg",
                class_id=0,
                class_name="person",
                confidence=0.92,
                x_min=0.1,
                y_min=0.1,
                x_max=0.3,
                y_max=0.7,
                track_number=1,
            ),
            DetectionItem(
                frame_index=1,
                timestamp=1.0,
                frame_path=f"frames/{vid_id}/frame_000001.jpg",
                class_id=0,
                class_name="person",
                confidence=0.88,
                x_min=0.12,
                y_min=0.11,
                x_max=0.32,
                y_max=0.71,
                track_number=1,
            ),
            DetectionItem(
                frame_index=1,
                timestamp=1.0,
                frame_path=f"frames/{vid_id}/frame_000001.jpg",
                class_id=2,
                class_name="car",
                confidence=0.85,
                x_min=0.5,
                y_min=0.4,
                x_max=0.8,
                y_max=0.9,
                track_number=2,
            ),
        ]

        tracks = [
            TrackSummary(
                track_number=1,
                object_class="person",
                start_time=0.0,
                end_time=1.0,
                start_frame=0,
                end_frame=1,
                confidences=[0.92, 0.88],
                trajectory=[
                    {"timestamp": 0.0, "frame_index": 0, "bbox": [0.1, 0.1, 0.3, 0.7]},
                    {"timestamp": 1.0, "frame_index": 1, "bbox": [0.12, 0.11, 0.32, 0.71]},
                ],
            ),
            TrackSummary(
                track_number=2,
                object_class="car",
                start_time=1.0,
                end_time=1.0,
                start_frame=1,
                end_frame=1,
                confidences=[0.85],
                trajectory=[
                    {"timestamp": 1.0, "frame_index": 1, "bbox": [0.5, 0.4, 0.8, 0.9]},
                ],
            ),
        ]

        stats = tracking_service.persist_tracking_results(
            db=db,
            video_id=vid_id,
            detections=detections,
            tracks=tracks,
        )

        assert stats["detections_count"] == 3
        assert stats["tracks_count"] == 2
        assert "person" in stats["detected_classes"]
        assert "car" in stats["detected_classes"]

        # Check DB records
        persisted_tracks = db.scalars(select(Track).where(Track.video_id == vid_id)).all()
        assert len(persisted_tracks) == 2

        person_track = next(t for t in persisted_tracks if t.object_class == "person")
        assert person_track.track_id == 1
        assert person_track.start_time == 0.0
        assert person_track.end_time == 1.0
        assert round(person_track.confidence_avg, 2) == 0.90

        persisted_events = db.scalars(select(Event).where(Event.video_id == vid_id)).all()
        assert len(persisted_events) == 3

        # Check Event -> Track foreign key link
        person_events = [e for e in persisted_events if e.track_id == person_track.id]
        assert len(person_events) == 2
        for ev in person_events:
            assert ev.bounding_box is not None
            assert ev.bounding_box["box_format"] == "xyxyn"

        # Check Video metadata
        updated_vid = db.scalar(select(Video).where(Video.id == vid_id))
        assert updated_vid.video_metadata["detections_count"] == 3
        assert updated_vid.video_metadata["tracks_count"] == 2

    finally:
        db.close()


def test_api_video_detections_and_tracks(client: TestClient, sample_video_record):
    """Test REST API endpoints for detections and tracks."""
    from tests.conftest import SharedTestingSessionLocal

    db = SharedTestingSessionLocal()
    try:
        vid_id = sample_video_record.id

        # Seed tracks and events
        trk = Track(
            video_id=vid_id,
            track_id=1,
            object_class="person",
            start_time=0.0,
            end_time=2.0,
            start_frame=0,
            end_frame=2,
            confidence_avg=0.91,
            attributes={"trajectory": []},
        )
        db.add(trk)
        db.flush()

        ev = Event(
            video_id=vid_id,
            track_id=trk.id,
            timestamp=1.0,
            event_type="object_detection",
            description="Detected person (0.91)",
            confidence=0.91,
            bounding_box={"x_min": 0.2, "y_min": 0.2, "x_max": 0.4, "y_max": 0.8},
            frame_path=f"frames/{vid_id}/frame_000001.jpg",
            attributes={"class_name": "person", "track_number": 1},
        )
        db.add(ev)
        db.commit()

        # 1. GET /api/v1/videos/{video_id}/detections
        res = client.get(f"/api/v1/videos/{vid_id}/detections")
        assert res.status_code == 200
        data = res.json()
        assert len(data) == 1
        assert data[0]["event_type"] == "object_detection"
        assert data[0]["confidence"] == 0.91
        assert data[0]["bounding_box"]["x_min"] == 0.2

        # Filter by class_name
        res_filtered = client.get(f"/api/v1/videos/{vid_id}/detections?class_name=person")
        assert res_filtered.status_code == 200
        assert len(res_filtered.json()) == 1

        res_none = client.get(f"/api/v1/videos/{vid_id}/detections?class_name=airplane")
        assert res_none.status_code == 200
        assert len(res_none.json()) == 0

        # 2. GET /api/v1/videos/{video_id}/tracks
        res_tracks = client.get(f"/api/v1/videos/{vid_id}/tracks")
        assert res_tracks.status_code == 200
        tracks_data = res_tracks.json()
        assert len(tracks_data) == 1
        assert tracks_data[0]["object_class"] == "person"
        assert tracks_data[0]["track_id"] == 1

        # 3. GET /api/v1/videos/{video_id}/tracks/{track_id}
        track_id_str = str(trk.id)
        res_detail = client.get(f"/api/v1/videos/{vid_id}/tracks/{track_id_str}")
        assert res_detail.status_code == 200
        detail_data = res_detail.json()
        assert detail_data["id"] == track_id_str
        assert len(detail_data["events"]) == 1
        assert detail_data["events"][0]["confidence"] == 0.91

    finally:
        db.close()


def test_annotated_frame_rendering(client: TestClient, sample_video_record, tmp_path, monkeypatch):
    """Test generating annotated frame preview with OpenCV bounding box overlays."""
    from tests.conftest import SharedTestingSessionLocal
    from app.services.video_service import video_service

    # Create synthetic frame JPEG
    frame_dir = tmp_path / "frames" / str(sample_video_record.id)
    frame_dir.mkdir(parents=True, exist_ok=True)
    frame_file = frame_dir / "frame_000000.jpg"

    canvas = np.zeros((200, 300, 3), dtype=np.uint8)
    cv2.imwrite(str(frame_file), canvas)

    monkeypatch.setattr(video_service, "frames_dir", tmp_path / "frames")

    db = SharedTestingSessionLocal()
    try:
        vid_id = sample_video_record.id
        ev = Event(
            video_id=vid_id,
            timestamp=0.0,
            event_type="object_detection",
            description="Detected person (0.95)",
            confidence=0.95,
            bounding_box={"x_min": 0.2, "y_min": 0.2, "x_max": 0.6, "y_max": 0.8},
            frame_path=f"frames/{vid_id}/frame_000000.jpg",
            attributes={"class_name": "person", "track_number": 42},
        )
        db.add(ev)
        db.commit()

        # Request annotated frame
        res = client.get(f"/api/v1/videos/{vid_id}/frames/frame_000000.jpg/annotated")
        assert res.status_code == 200
        assert res.headers["content-type"] == "image/jpeg"
        assert len(res.content) > 100
    finally:
        db.close()
