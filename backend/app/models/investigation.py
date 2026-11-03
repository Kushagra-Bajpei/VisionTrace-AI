"""
Investigation, Evidence, and InvestigationMessage models for the Investigation Workspace.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONType, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.event import Event
    from app.models.report import Report
    from app.models.track import Track
    from app.models.user import User
    from app.models.video import Video


class Investigation(Base, UUIDMixin, TimestampMixin):
    """
    Active or archived investigation case.
    Combines evidence, timeline markers, notes, and AI reporting history.
    """
    __tablename__ = "investigations"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50),
        default="open",
        nullable=False,
        index=True,
    )  # 'open', 'in_progress', 'under_review', 'closed'
    priority: Mapped[str] = mapped_column(
        String(50),
        default="medium",
        nullable=False,
        index=True,
    )  # 'low', 'medium', 'high', 'critical'
    tags: Mapped[Optional[List[str]]] = mapped_column(JSONType, nullable=True, default=list)
    owner_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_investigator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    owner: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[owner_id],
        back_populates="owned_investigations",
    )
    lead_investigator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[lead_investigator_id],
        back_populates="investigations",
    )
    reviewer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reviewer_id],
        back_populates="reviewed_investigations",
    )
    evidence_items: Mapped[List["InvestigationEvidence"]] = relationship(
        "InvestigationEvidence",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="InvestigationEvidence.sequence_number, InvestigationEvidence.timestamp",
    )
    messages: Mapped[List["InvestigationMessage"]] = relationship(
        "InvestigationMessage",
        back_populates="investigation",
        cascade="all, delete-orphan",
        order_by="InvestigationMessage.created_at",
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report",
        back_populates="investigation",
    )

    def __repr__(self) -> str:
        return f"<Investigation {self.title} ({self.status})>"


class InvestigationEvidence(Base, UUIDMixin, TimestampMixin):
    """
    Evidence item attached to an investigation case.
    References persisted source video, keyframe, detection event, track, or visual embedding.
    Preserves exact timestamps, model metrics, and investigator observations.
    """
    __tablename__ = "investigation_evidence"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    timestamp: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    track_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("tracks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50),
        default="detection",
        nullable=False,
        index=True,
    )  # 'detection', 'tracked_object', 'keyframe', 'visual_similarity', 'note'
    frame_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    crop_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    object_class: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    visual_similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    custom_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)

    # Evidence Integrity & Tamper-Evident SHA-256 Hashes (Phase 8)
    evidence_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hash_algorithm: Mapped[Optional[str]] = mapped_column(String(32), default="sha256", nullable=True)
    hashed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="evidence_items")
    video: Mapped["Video"] = relationship("Video")
    event: Mapped[Optional["Event"]] = relationship("Event")
    track: Mapped[Optional["Track"]] = relationship("Track")

    def __repr__(self) -> str:
        return f"<InvestigationEvidence {self.evidence_type} at {self.timestamp:.1f}s for Case {self.investigation_id}>"


class InvestigationMessage(Base, UUIDMixin):
    """
    Chronological messages or investigator notes associated with an investigation case.
    """
    __tablename__ = "investigation_messages"

    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type: Mapped[str] = mapped_column(
        String(50),
        default="investigator",
        nullable=False,
        index=True,
    )  # "investigator", "system", "ai_copilot"
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    references: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    investigation: Mapped["Investigation"] = relationship(
        "Investigation",
        back_populates="messages",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        return f"<InvestigationMessage by {self.sender_type} in {self.investigation_id}>"
