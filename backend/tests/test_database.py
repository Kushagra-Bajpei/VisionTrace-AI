"""
Phase 2 Database and Model Tests.
Tests all 9 SQLAlchemy ORM models, relationships, cascading, JSON types, and Pydantic schemas.
"""
import uuid
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import (
    Camera,
    Embedding,
    Event,
    Investigation,
    InvestigationMessage,
    Report,
    Track,
    User,
    Video,
)
from app.schemas import (
    CameraResponse,
    EventResponse,
    InvestigationResponse,
    ReportResponse,
    TrackResponse,
    UserResponse,
    VideoResponse,
)


@pytest.fixture(scope="function")
def db_session():
    """
    Creates an isolated in-memory database with all 9 tables for each test.
    """
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
    Base.metadata.drop_all(engine)


def test_all_tables_created(db_session):
    """Verify that all 9 required tables are registered and created in the database."""
    expected_tables = {
        "users",
        "cameras",
        "videos",
        "tracks",
        "events",
        "embeddings",
        "investigations",
        "investigation_messages",
        "reports",
    }
    actual_tables = set(Base.metadata.tables.keys())
    assert expected_tables.issubset(actual_tables), (
        f"Missing tables: {expected_tables - actual_tables}"
    )


def test_user_creation_and_schema(db_session):
    """Test User model creation, UUID generation, and Pydantic schema serialization."""
    user = User(
        email="detective@visiontrace.ai",
        hashed_password="bcrypt_hash_placeholder",
        full_name="Lead Detective Jane Doe",
        role="investigator",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    assert isinstance(user.id, uuid.UUID)
    assert user.email == "detective@visiontrace.ai"
    assert user.created_at is not None

    # Verify Pydantic schema serialization
    schema = UserResponse.model_validate(user)
    assert schema.email == user.email
    assert schema.id == user.id


def test_camera_and_video_relationship(db_session):
    """Test Camera -> Video relationship and foreign key constraints."""
    camera = Camera(
        name="Main Entrance Cam 01",
        location="Building A, North Lobby",
        status="active",
        description="4K Wide Angle CCTV",
    )
    db_session.add(camera)
    db_session.commit()
    db_session.refresh(camera)

    video = Video(
        camera_id=camera.id,
        filename="feed_20261103_1400.mp4",
        original_filename="lobby_cam01.mp4",
        file_path="/storage/videos/feed_20261103_1400.mp4",
        file_size=104857600,
        duration=3600.0,
        width=1920,
        height=1080,
        fps=30.0,
        status="completed",
        video_metadata={"codec": "h264", "bitrate_kbps": 4500},
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)

    assert video.camera_id == camera.id
    assert len(camera.videos) == 1
    assert camera.videos[0].filename == "feed_20261103_1400.mp4"

    # Verify schema serialization
    video_schema = VideoResponse.model_validate(video)
    assert video_schema.duration == 3600.0
    assert video_schema.video_metadata["codec"] == "h264"


def test_track_and_event_creation(db_session):
    """Test Track and Event model generation with JSON attributes and bounding boxes."""
    video = Video(
        filename="corridor_feed.mp4",
        original_filename="corridor.mp4",
        file_path="/storage/videos/corridor.mp4",
        file_size=52428800,
        status="completed",
    )
    db_session.add(video)
    db_session.commit()

    track = Track(
        video_id=video.id,
        track_id=42,
        object_class="person",
        start_time=12.5,
        end_time=24.0,
        start_frame=375,
        end_frame=720,
        confidence_avg=0.94,
        attributes={"clothing_color": "dark_jacket", "carrying": "red_bag"},
    )
    db_session.add(track)
    db_session.commit()
    db_session.refresh(track)

    event = Event(
        video_id=video.id,
        track_id=track.id,
        timestamp=14.2,
        event_type="person_entering",
        description="Person carrying a red bag entered through corridor door",
        confidence=0.96,
        bounding_box={"x": 0.42, "y": 0.35, "width": 0.18, "height": 0.55},
        frame_path="/storage/frames/frame_00426.jpg",
        clip_start_time=12.0,
        clip_end_time=18.0,
        clip_path="/storage/clips/clip_00426.mp4",
        attributes={"bag_color": "red"},
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)

    assert event.track.object_class == "person"
    assert event.video.filename == "corridor_feed.mp4"
    assert event.bounding_box["x"] == 0.42

    event_schema = EventResponse.model_validate(event)
    assert event_schema.confidence == 0.96
    assert event_schema.attributes["bag_color"] == "red"


def test_embedding_creation_and_association(db_session):
    """Test Embedding model storage with 512-dim vector."""
    video = Video(
        filename="test.mp4",
        original_filename="test.mp4",
        file_path="/storage/videos/test.mp4",
        file_size=1000,
        status="completed",
    )
    db_session.add(video)
    db_session.commit()

    event = Event(
        video_id=video.id,
        timestamp=5.0,
        event_type="object_detected",
        description="Detected vehicle",
        confidence=0.89,
    )
    db_session.add(event)
    db_session.commit()

    dummy_vector = [0.01 * (i % 10) for i in range(512)]
    embedding = Embedding(
        event_id=event.id,
        video_id=video.id,
        embedding_type="clip_visual",
        embedding=dummy_vector,
        model_name="openai/clip-vit-base-patch32",
    )
    db_session.add(embedding)
    db_session.commit()
    db_session.refresh(embedding)

    assert embedding.event_id == event.id
    assert embedding.video_id == video.id
    assert len(embedding.embedding) == 512
    assert len(event.embeddings) == 1


def test_investigation_and_copilot_messages(db_session):
    """Test Investigation case management and AI copilot message thread."""
    user = User(
        email="analyst@visiontrace.ai",
        hashed_password="hash",
        full_name="Analyst Smith",
    )
    db_session.add(user)
    db_session.commit()

    investigation = Investigation(
        title="Incident Case #2026-0042: North Wing Breach",
        description="Investigation into unauthorized bag left unattended in hallway",
        status="in_progress",
        priority="high",
        lead_investigator_id=user.id,
    )
    db_session.add(investigation)
    db_session.commit()
    db_session.refresh(investigation)

    # 1. User query message
    msg_user = InvestigationMessage(
        investigation_id=investigation.id,
        sender_type="user",
        user_id=user.id,
        message="Find a person carrying a red bag who entered between 2 PM and 3 PM.",
    )
    # 2. AI Copilot response grounded in evidence
    msg_ai = InvestigationMessage(
        investigation_id=investigation.id,
        sender_type="ai_copilot",
        message="Found 1 high-confidence match: Person with a red handbag detected at 14:15:22 in Camera 02.",
        references={
            "matching_event_ids": [str(uuid.uuid4())],
            "timestamps": [14.2],
            "confidence": 0.94,
        },
    )
    db_session.add_all([msg_user, msg_ai])
    db_session.commit()

    db_session.refresh(investigation)
    assert len(investigation.messages) == 2
    assert investigation.messages[0].sender_type == "user"
    assert investigation.messages[1].sender_type == "ai_copilot"
    assert "red handbag" in investigation.messages[1].message

    inv_schema = InvestigationResponse.model_validate(investigation)
    assert len(inv_schema.messages) == 2


def test_report_generation(db_session):
    """Test Report model with structured evidence findings and timeline."""
    investigation = Investigation(
        title="Unauthorized Entry Case",
        status="closed",
    )
    db_session.add(investigation)
    db_session.commit()

    report = Report(
        investigation_id=investigation.id,
        title="Final Incident Summary: Unauthorized Entry",
        executive_summary="At 14:15 UTC, an unidentified individual entered North Door carrying a red bag.",
        findings={
            "suspect_count": 1,
            "objects_identified": ["person", "handbag"],
            "entry_point": "North Door Cam 01",
        },
        evidence_timeline={
            "events": [
                {
                    "time": "14:15:22",
                    "description": "Person enters North Lobby",
                    "confidence": 0.96,
                }
            ]
        },
        generated_by_ai=True,
        status="final",
    )
    db_session.add(report)
    db_session.commit()
    db_session.refresh(report)

    assert report.investigation.title == "Unauthorized Entry Case"
    assert report.findings["suspect_count"] == 1

    report_schema = ReportResponse.model_validate(report)
    assert report_schema.status == "final"
    assert report_schema.generated_by_ai is True
