"""
Embedding model storing pgvector semantic embeddings for indexed video events and frames.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import UUIDMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.video import Video

# Standard CLIP visual & text embedding dimension (ViT-B/32 is 512-dim)
CLIP_EMBEDDING_DIM = 512


class Embedding(Base, UUIDMixin):
    """
    Multimodal semantic vector embeddings stored with pgvector.
    Enables cosine similarity search over visual frames and event descriptions.
    """
    __tablename__ = "embeddings"

    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_type: Mapped[str] = mapped_column(
        String(50),
        default="clip_visual",
        nullable=False,
        index=True,
    )
    # pgvector Vector column with 512 dimensions for CLIP ViT-B/32
    embedding = mapped_column(Vector(CLIP_EMBEDDING_DIM), nullable=False)
    model_name: Mapped[str] = mapped_column(
        String(100),
        default="openai/clip-vit-base-patch32",
        nullable=False,
    )
    frame_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    timestamp: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        index=True,
    )
    crop_path: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    event: Mapped[Optional["Event"]] = relationship("Event", back_populates="embeddings")
    video: Mapped["Video"] = relationship("Video", back_populates="embeddings")

    __table_args__ = (
        Index("ix_embeddings_event_type", "event_id", "embedding_type"),
        Index("ix_embeddings_video_type", "video_id", "embedding_type"),
    )

    def __repr__(self) -> str:
        return f"<Embedding {self.embedding_type} ({self.model_name}) for Event {self.event_id}>"
