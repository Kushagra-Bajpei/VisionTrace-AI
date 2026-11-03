"""
Video model representing uploaded CCTV footage files and their processing state.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONType, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.camera import Camera
    from app.models.user import User
    from app.models.track import Track
    from app.models.event import Event
    from app.models.embedding import Embedding


class Video(Base, UUIDMixin, TimestampMixin):
    """
    Uploaded CCTV video files and their extraction metadata.
    """
    __tablename__ = "videos"

    camera_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("cameras.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    fps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="uploaded",
        nullable=False,
        index=True,
    )
    processing_progress: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    thumbnail_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    video_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    file_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hash_algorithm: Mapped[Optional[str]] = mapped_column(String(32), default="sha256", nullable=True)
    hashed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    camera: Mapped[Optional["Camera"]] = relationship("Camera", back_populates="videos")
    uploader: Mapped[Optional["User"]] = relationship("User", back_populates="videos")
    tracks: Mapped[List["Track"]] = relationship(
        "Track",
        back_populates="video",
        cascade="all, delete-orphan",
    )
    events: Mapped[List["Event"]] = relationship(
        "Event",
        back_populates="video",
        cascade="all, delete-orphan",
    )
    embeddings: Mapped[List["Embedding"]] = relationship(
        "Embedding",
        back_populates="video",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Video {self.original_filename} ({self.status})>"
