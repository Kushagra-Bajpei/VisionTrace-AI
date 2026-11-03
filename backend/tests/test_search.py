"""
Phase 5 Tests: Natural Language CCTV Search.
Tests query parsing, structured facet extraction, evidence retrieval, and API endpoints.
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.models.event import Event
from app.models.track import Track
from app.models.video import Video
from app.services.search_service import search_engine


def test_query_parser_facets():
    """Verify parsing of classes, temporal bounds, confidences, and track numbers."""
    # 1. Target classes
    p1 = search_engine.parse_query("Find all people and cars detected in this footage")
    assert "person" in p1.target_classes
    assert "car" in p1.target_classes

    # 2. Time range: between MM:SS and MM:SS
    p2 = search_engine.parse_query("Show me cars visible between 00:02 and 00:08")
    assert "car" in p2.target_classes
    assert p2.time_min == 2.0
    assert p2.time_max == 8.0

    # 3. Confidence threshold
    p3 = search_engine.parse_query("Show tracks with confidence above 80%")
    assert p3.min_confidence == 0.80

    # 4. Track ID lookup
    p4 = search_engine.parse_query("Locate Track #42 in camera footage")
    assert p4.track_number == 42

    # 5. Temporal intent
    p5 = search_engine.parse_query("When was a person last seen?")
    assert "person" in p5.target_classes
    assert p5.temporal_intent == "last_seen"

    p6 = search_engine.parse_query("When was a bicycle first seen?")
    assert "bicycle" in p6.target_classes
    assert p6.temporal_intent == "first_seen"

    # 6. Unsupported facets flagging
    p7 = search_engine.parse_query("Find the person wearing a red shirt running fast")
    assert "person" in p7.target_classes
    assert any("color" in f for f in p7.unsupported_facets)
    assert any("speed" in f for f in p7.unsupported_facets)


@pytest.fixture
def seeded_search_data(db_tables):
    """Seed test video, tracks, and detection events into test database."""
    from tests.conftest import SharedTestingSessionLocal

    db = SharedTestingSessionLocal()
    try:
        vid_id = uuid.uuid4()
        video = Video(
            id=vid_id,
            filename="cctv_lobby_test.mp4",
            original_filename="LOBBY_NORTH_CAM.MP4",
            file_path="videos/cctv_lobby_test.mp4",
            file_size=5 * 1024 * 1024,
            duration=10.0,
            width=1920,
            height=1080,
            fps=25.0,
            status="completed",
            processing_progress=100.0,
            video_metadata={"frame_count": 250},
        )
        db.add(video)

        # Track 1: Person visible 1.0s to 4.0s
        trk1 = Track(
            video_id=vid_id,
            track_id=1,
            object_class="person",
            start_time=1.0,
            end_time=4.0,
            start_frame=1,
            end_frame=4,
            confidence_avg=0.88,
            attributes={
                "detection_count": 2,
                "trajectory": [
                    {"timestamp": 1.0, "frame_index": 1, "bbox": [0.1, 0.2, 0.3, 0.8], "confidence": 0.86},
                    {"timestamp": 4.0, "frame_index": 4, "bbox": [0.4, 0.2, 0.6, 0.8], "confidence": 0.90},
                ],
            },
        )
        db.add(trk1)
        db.flush()

        # Detections for Track 1
        ev1 = Event(
            video_id=vid_id,
            track_id=trk1.id,
            timestamp=1.0,
            event_type="object_detection",
            description="Detected person (conf: 0.86)",
            confidence=0.86,
            bounding_box={"x_min": 0.1, "y_min": 0.2, "x_max": 0.3, "y_max": 0.8, "box_format": "xyxyn"},
            frame_path=f"frames/{vid_id}/frame_000001.jpg",
            attributes={"class_name": "person", "track_number": 1, "frame_index": 1},
        )
        ev2 = Event(
            video_id=vid_id,
            track_id=trk1.id,
            timestamp=4.0,
            event_type="object_detection",
            description="Detected person (conf: 0.90)",
            confidence=0.90,
            bounding_box={"x_min": 0.4, "y_min": 0.2, "x_max": 0.6, "y_max": 0.8, "box_format": "xyxyn"},
            frame_path=f"frames/{vid_id}/frame_000004.jpg",
            attributes={"class_name": "person", "track_number": 1, "frame_index": 4},
        )
        db.add_all([ev1, ev2])

        # Track 2: Car visible 6.0s to 8.0s
        trk2 = Track(
            video_id=vid_id,
            track_id=2,
            object_class="car",
            start_time=6.0,
            end_time=8.0,
            start_frame=6,
            end_frame=8,
            confidence_avg=0.72,
            attributes={"detection_count": 1, "trajectory": []},
        )
        db.add(trk2)
        db.flush()

        ev3 = Event(
            video_id=vid_id,
            track_id=trk2.id,
            timestamp=7.0,
            event_type="object_detection",
            description="Detected car (conf: 0.72)",
            confidence=0.72,
            bounding_box={"x_min": 0.5, "y_min": 0.4, "x_max": 0.8, "y_max": 0.9, "box_format": "xyxyn"},
            frame_path=f"frames/{vid_id}/frame_000007.jpg",
            attributes={"class_name": "car", "track_number": 2, "frame_index": 7},
        )
        db.add(ev3)
        db.commit()

        return {"video_id": vid_id, "track1": trk1, "track2": trk2}
    finally:
        db.close()


def test_search_class_and_time_filtering(client: TestClient, seeded_search_data):
    """Test POST /api/v1/search/query with object class and time window."""
    # 1. Search for people
    res = client.post(
        "/api/v1/search/query",
        json={"query": "Find all people detected in this video"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_matches"] == 2
    assert data["total_tracks"] == 1
    assert data["tracks"][0]["object_class"] == "person"
    assert data["tracks"][0]["track_id"] == 1
    assert "person" in data["evidence_summary"].lower()

    # 2. Search for cars between 00:05 and 00:09
    res_car = client.post(
        "/api/v1/search/query",
        json={"query": "Show me cars visible between 00:05 and 00:09"},
    )
    assert res_car.status_code == 200
    car_data = res_car.json()
    assert car_data["total_matches"] == 1
    assert car_data["detections"][0]["object_class"] == "car"
    assert car_data["detections"][0]["timestamp"] == 7.0

    # 3. Search for cars outside their visible window -> Expect 0 matches
    res_car_empty = client.post(
        "/api/v1/search/query",
        json={"query": "Show me cars visible between 00:00 and 00:04"},
    )
    assert res_car_empty.status_code == 200
    empty_data = res_car_empty.json()
    assert empty_data["total_matches"] == 0
    assert "no verified detection records found" in empty_data["evidence_summary"].lower()


def test_search_confidence_and_temporal_intent(client: TestClient, seeded_search_data):
    """Test confidence thresholding and 'last seen' temporal queries."""
    # 1. Confidence filter above 80%
    # Person has conf 0.88; Car has conf 0.72. Car should be excluded.
    res_conf = client.post(
        "/api/v1/search/query",
        json={"query": "Show tracks with confidence above 80%"},
    )
    assert res_conf.status_code == 200
    data = res_conf.json()
    assert len(data["tracks"]) == 1
    assert data["tracks"][0]["object_class"] == "person"

    # 2. 'Last seen' query
    res_last = client.post(
        "/api/v1/search/query",
        json={"query": "When was a person last seen?"},
    )
    assert res_last.status_code == 200
    last_data = res_last.json()
    assert last_data["total_matches"] == 2
    assert "last observed at timestamp 4.0s" in last_data["evidence_summary"]
    # In 'last seen', latest detection at 4.0s comes first
    assert last_data["detections"][0]["timestamp"] == 4.0


def test_search_track_number_and_pagination(client: TestClient, seeded_search_data):
    """Test searching by specific Track ID and pagination parameters."""
    res_track = client.post(
        "/api/v1/search/query",
        json={"query": "Locate Track #2"},
    )
    assert res_track.status_code == 200
    track_data = res_track.json()
    assert len(track_data["tracks"]) == 1
    assert track_data["tracks"][0]["track_id"] == 2
    assert track_data["tracks"][0]["object_class"] == "car"

    # Pagination: limit=1
    res_paged = client.post(
        "/api/v1/search/query",
        json={"query": "Find people", "limit": 1, "offset": 0},
    )
    assert res_paged.status_code == 200
    paged_data = res_paged.json()
    assert paged_data["total_matches"] == 2  # Total available
    assert len(paged_data["detections"]) == 1  # Returned in this page


def test_search_suggestions_endpoint(client: TestClient):
    """Test GET /api/v1/search/suggestions."""
    res = client.get("/api/v1/search/suggestions")
    assert res.status_code == 200
    suggestions = res.json()
    assert len(suggestions) >= 4
    queries = [s["query"] for s in suggestions]
    assert any("people" in q for q in queries)
    assert any("cars" in q for q in queries)
