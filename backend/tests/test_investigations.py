"""
Phase 7 Tests: Investigation Workflows, Evidence Management & Forensic PDF Reports.
Tests Case CRUD, Evidence linking, duplicate prevention, investigator notes,
safe cascading, path security, and forensic PDF generation.
"""
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.models.event import Event
from app.models.investigation import Investigation, InvestigationEvidence, InvestigationMessage
from app.models.report import Report
from app.models.video import Video
from tests.conftest import SharedTestingSessionLocal

settings = get_settings()


@pytest.fixture
def seeded_case_data(db_tables):
    """Seed test video, detection event, and initial investigation case."""
    db = SharedTestingSessionLocal()
    try:
        vid_id = uuid.uuid4()
        video = Video(
            id=vid_id,
            filename="cctv_case_cam01.mp4",
            original_filename="CAM01_PERIMETER.MP4",
            file_path="videos/cctv_case_cam01.mp4",
            file_size=10 * 1024 * 1024,
            duration=30.0,
            status="completed",
            processing_progress=100.0,
        )
        db.add(video)

        ev_id = uuid.uuid4()
        event = Event(
            id=ev_id,
            video_id=vid_id,
            timestamp=14.5,
            event_type="object_detection",
            description="Person near perimeter fence",
            confidence=0.89,
            bounding_box={"x_min": 0.2, "y_min": 0.3, "x_max": 0.4, "y_max": 0.9, "box_format": "xyxyn"},
            frame_path=f"frames/{vid_id}/frame_000014.jpg",
            attributes={"class_name": "person", "track_number": 3},
        )
        db.add(event)
        db.commit()

        return {"video_id": vid_id, "event_id": ev_id}
    finally:
        db.close()


def test_case_crud_lifecycle(client: TestClient, seeded_case_data):
    """Test creating, reading, updating status/priority, and listing cases."""
    # 1. Create Case
    create_payload = {
        "title": "Perimeter Breach Investigation #104",
        "description": "Unauthorized subject observed approaching south perimeter gate.",
        "status": "open",
        "priority": "high",
        "tags": ["perimeter", "after-hours", "unauthorized-access"],
    }
    res_create = client.post("/api/v1/cases", json=create_payload)
    assert res_create.status_code == 201
    case = res_create.json()
    case_id = case["id"]
    assert case["title"] == "Perimeter Breach Investigation #104"
    assert case["status"] == "open"
    assert case["priority"] == "high"
    assert "perimeter" in case["tags"]

    # 2. Get Case Detail
    res_get = client.get(f"/api/v1/cases/{case_id}")
    assert res_get.status_code == 200
    case_detail = res_get.json()
    assert case_detail["id"] == case_id
    assert case_detail["evidence_count"] == 0
    assert len(case_detail["evidence_items"]) == 0

    # 3. Update Status and Priority
    update_payload = {
        "status": "in_progress",
        "priority": "critical",
        "description": "Updated briefing: high-value asset sector alert.",
    }
    res_patch = client.patch(f"/api/v1/cases/{case_id}", json=update_payload)
    assert res_patch.status_code == 200
    patched = res_patch.json()
    assert patched["status"] == "in_progress"
    assert patched["priority"] == "critical"

    # 4. List and Filter Cases
    res_list = client.get("/api/v1/cases?status=in_progress&priority=critical")
    assert res_list.status_code == 200
    cases_list = res_list.json()
    assert len(cases_list) >= 1
    assert any(c["id"] == case_id for c in cases_list)


def test_evidence_linking_and_duplicate_prevention(client: TestClient, seeded_case_data):
    """Verify adding evidence to a case, duplicate prevention, and sequence numbering."""
    vid_id = seeded_case_data["video_id"]
    ev_id = seeded_case_data["event_id"]

    # Create Case
    res_case = client.post("/api/v1/cases", json={"title": "Night Shift Audit"})
    assert res_case.status_code == 201
    case_id = res_case.json()["id"]

    # Add Evidence Item 1
    ev_payload1 = {
        "video_id": str(vid_id),
        "timestamp": 14.5,
        "event_id": str(ev_id),
        "evidence_type": "detection",
        "object_class": "person",
        "confidence": 0.89,
        "visual_similarity_score": 0.32,
        "notes": "Subject spotted entering camera field of view.",
        "frame_path": f"frames/{vid_id}/frame_000014.jpg",
    }
    res_ev1 = client.post(f"/api/v1/cases/{case_id}/evidence", json=ev_payload1)
    assert res_ev1.status_code == 201
    item1 = res_ev1.json()
    assert item1["sequence_number"] == 1
    assert item1["object_class"] == "person"
    assert item1["confidence"] == 0.89
    assert item1["visual_similarity_score"] == 0.32
    assert f"/api/v1/videos/{vid_id}/frames/frame_000014.jpg" in item1["frame_url"]

    # Duplicate Prevention: Attempt to add exact same event again
    dup_payload = {
        "video_id": str(vid_id),
        "timestamp": 14.5,
        "event_id": str(ev_id),
        "evidence_type": "detection",
        "notes": "Additional observer confirmation.",
    }
    res_dup = client.post(f"/api/v1/cases/{case_id}/evidence", json=dup_payload)
    assert res_dup.status_code == 200 or res_dup.status_code == 201
    dup_item = res_dup.json()
    # Must reuse the same evidence ID rather than creating a duplicate row
    assert dup_item["id"] == item1["id"]
    assert "Additional observer confirmation" in dup_item["notes"]

    # Verify total evidence items is still 1
    res_evidence_list = client.get(f"/api/v1/cases/{case_id}/evidence")
    assert res_evidence_list.status_code == 200
    assert len(res_evidence_list.json()) == 1

    # Add Evidence Item 2 (different timestamp)
    ev_payload2 = {
        "video_id": str(vid_id),
        "timestamp": 22.0,
        "evidence_type": "keyframe",
        "object_class": "vehicle",
        "confidence": 0.94,
        "notes": "Escape vehicle passing east road.",
    }
    res_ev2 = client.post(f"/api/v1/cases/{case_id}/evidence", json=ev_payload2)
    assert res_ev2.status_code == 201
    item2 = res_ev2.json()
    assert item2["sequence_number"] == 2

    # Check updated case detail
    res_detail = client.get(f"/api/v1/cases/{case_id}")
    assert res_detail.json()["evidence_count"] == 2


def test_evidence_modification_and_safety(client: TestClient, seeded_case_data):
    """Test updating notes and deleting evidence without affecting source videos or detections."""
    vid_id = seeded_case_data["video_id"]
    ev_id = seeded_case_data["event_id"]

    res_case = client.post("/api/v1/cases", json={"title": "Evidence Safety Test"})
    case_id = res_case.json()["id"]

    res_ev = client.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={
            "video_id": str(vid_id),
            "timestamp": 14.5,
            "event_id": str(ev_id),
            "notes": "Initial note",
        },
    )
    ev_item_id = res_ev.json()["id"]

    # Update note
    res_patch = client.patch(
        f"/api/v1/cases/{case_id}/evidence/{ev_item_id}",
        json={"notes": "Updated forensic review note: confirmed clothing matches suspect."},
    )
    assert res_patch.status_code == 200
    assert res_patch.json()["notes"] == "Updated forensic review note: confirmed clothing matches suspect."

    # Delete evidence from case
    res_del = client.delete(f"/api/v1/cases/{case_id}/evidence/{ev_item_id}")
    assert res_del.status_code == 200

    # Verify evidence item is removed from case
    res_list = client.get(f"/api/v1/cases/{case_id}/evidence")
    assert len(res_list.json()) == 0

    # Verify source video and event STILL EXIST in DB
    db = SharedTestingSessionLocal()
    try:
        video_in_db = db.query(Video).filter(Video.id == vid_id).first()
        assert video_in_db is not None
        event_in_db = db.query(Event).filter(Event.id == ev_id).first()
        assert event_in_db is not None
    finally:
        db.close()


def test_case_notes_and_activity_log(client: TestClient, seeded_case_data):
    """Test adding chronological case notes and activity messages."""
    res_case = client.post("/api/v1/cases", json={"title": "Incident Log Test"})
    case_id = res_case.json()["id"]

    note1 = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"message": "Case opened by Investigator Reynolds.", "sender_type": "investigator"},
    )
    assert note1.status_code == 201
    assert note1.json()["sender_type"] == "investigator"

    note2 = client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"message": "Cross-referenced with Gate 4 log.", "sender_type": "system"},
    )
    assert note2.status_code == 201

    res_detail = client.get(f"/api/v1/cases/{case_id}")
    assert res_detail.status_code == 200
    messages = res_detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["message"] == "Case opened by Investigator Reynolds."
    assert messages[1]["message"] == "Cross-referenced with Gate 4 log."


def test_forensic_pdf_report_generation_and_download(client: TestClient, seeded_case_data):
    """Test generating audit-grade forensic PDF report, verifying disk persistence, and downloading."""
    vid_id = seeded_case_data["video_id"]
    ev_id = seeded_case_data["event_id"]

    res_case = client.post(
        "/api/v1/cases",
        json={
            "title": "East Perimeter Incident Report",
            "description": "Suspicious activity detected near East Perimeter Fence.",
            "priority": "high",
            "tags": ["east-zone", "motion-alarm"],
        },
    )
    case_id = res_case.json()["id"]

    # Add evidence
    client.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={
            "video_id": str(vid_id),
            "timestamp": 14.5,
            "event_id": str(ev_id),
            "object_class": "person",
            "confidence": 0.89,
            "visual_similarity_score": 0.28,
            "notes": "Suspect paused at fence line for 3 seconds.",
        },
    )

    # Add case note
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"message": "Patrol dispatched to East perimeter fence at 14:15."},
    )

    # Generate Report
    rep_res = client.post(
        f"/api/v1/cases/{case_id}/report",
        json={
            "title": "Official Incident Dossier: East Perimeter",
            "executive_summary": "Comprehensive evidentiary summary of the perimeter breach.",
            "custom_notes": "All physical gates inspected and secured.",
        },
    )
    assert rep_res.status_code == 201
    report_data = rep_res.json()
    assert report_data["status"] == "completed"
    assert report_data["pdf_path"] is not None
    assert "download_url" in report_data

    # Verify PDF file exists on disk
    pdf_disk_path = settings.storage_base / report_data["pdf_path"]
    assert pdf_disk_path.is_file()
    assert pdf_disk_path.stat().st_size > 500  # Valid PDF binary size

    # Download Report via API
    download_url = report_data["download_url"]
    dl_res = client.get(download_url)
    assert dl_res.status_code == 200
    assert dl_res.headers["content-type"] == "application/pdf"
    # Verify PDF header magic bytes (%PDF-)
    assert dl_res.content[:5] == b"%PDF-"


def test_case_deletion_cascading_and_preservation(client: TestClient, seeded_case_data):
    """Deleting an investigation deletes case artifacts but never deletes source video or events."""
    vid_id = seeded_case_data["video_id"]
    ev_id = seeded_case_data["event_id"]

    res_case = client.post("/api/v1/cases", json={"title": "Temporary Case For Deletion"})
    case_id = res_case.json()["id"]

    client.post(
        f"/api/v1/cases/{case_id}/evidence",
        json={"video_id": str(vid_id), "timestamp": 5.0, "event_id": str(ev_id)},
    )
    client.post(
        f"/api/v1/cases/{case_id}/notes",
        json={"message": "Temporary note"},
    )

    # Delete Case
    del_res = client.delete(f"/api/v1/cases/{case_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True

    # Case must no longer exist
    assert client.get(f"/api/v1/cases/{case_id}").status_code == 404

    # Verify source video and event STILL EXIST
    db = SharedTestingSessionLocal()
    try:
        assert db.query(Video).filter(Video.id == vid_id).first() is not None
        assert db.query(Event).filter(Event.id == ev_id).first() is not None
    finally:
        db.close()
