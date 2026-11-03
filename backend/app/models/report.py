"""
Report model representing evidence-grounded incident reports and export metadata.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONType, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.investigation import Investigation
    from app.models.user import User


class Report(Base, UUIDMixin, TimestampMixin):
    """
    Structured incident report containing verified event evidence,
    chronological timelines, and exportable PDF artifacts.
    """
    __tablename__ = "reports"

    investigation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)
    findings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    evidence_timeline: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    generated_by_ai: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    pdf_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    pdf_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hash_algorithm: Mapped[Optional[str]] = mapped_column(String(32), default="sha256", nullable=True)
    hashed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="draft",
        nullable=False,
        index=True,
    )  # "draft", "final", "exported"

    # Relationships
    investigation: Mapped[Optional["Investigation"]] = relationship(
        "Investigation",
        back_populates="reports",
    )
    author: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="reports",
    )

    def __repr__(self) -> str:
        return f"<Report '{self.title}' ({self.status})>"
