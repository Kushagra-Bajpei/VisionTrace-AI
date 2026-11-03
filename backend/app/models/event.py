"""
Event model representing structured detection and behavioral events extracted from footage.
"""
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import Float, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONType, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.video import Video
    from app.models.camera import Camera
    from app.models.track import Track
    from app.models.embedding import Embedding


class Event(Base, UUIDMixin, TimestampMixin):
    """
    Structured computer vision event detected in a video stream.
    Contains precise timestamps, bounding boxes, frame snapshots, and metadata.
    """
    __tablename__ = "events"

    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    camera_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    track_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("tracks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    timestamp: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    bounding_box: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    frame_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    clip_start_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clip_end_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    clip_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    # Relationships
    video: Mapped["Video"] = relationship("Video", back_populates="events")
    camera: Mapped[Optional["Camera"]] = relationship("Camera", back_populates="events")
    track: Mapped[Optional["Track"]] = relationship("Track", back_populates="events")
    embeddings: Mapped[List["Embedding"]] = relationship(
        "Embedding",
        back_populates="event",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Composite index for time-range filtering within a video
        Index("ix_events_video_timestamp", "video_id", "timestamp"),
        Index("ix_events_type_timestamp", "event_type", "timestamp"),
    )

    def __repr__(self) -> str:
        return f"<Event {self.event_type} at {self.timestamp:.1f}s in Video {self.video_id}>"
