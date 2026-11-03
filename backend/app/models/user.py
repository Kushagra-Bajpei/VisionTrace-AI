"""
User model for authentication, authorization, and audit logs.
"""
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.video import Video
    from app.models.investigation import Investigation, InvestigationMessage
    from app.models.report import Report


class User(Base, UUIDMixin, TimestampMixin):
    """
    Users of the VisionTrace AI platform.
    Roles: admin, investigator, analyst, viewer.
    """
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="investigator", nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="uploader")
    owned_investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation",
        foreign_keys="Investigation.owner_id",
        back_populates="owner",
    )
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation",
        foreign_keys="Investigation.lead_investigator_id",
        back_populates="lead_investigator",
    )
    reviewed_investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation",
        foreign_keys="Investigation.reviewer_id",
        back_populates="reviewer",
    )
    messages: Mapped[List["InvestigationMessage"]] = relationship("InvestigationMessage", back_populates="user")
    reports: Mapped[List["Report"]] = relationship("Report", back_populates="author")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"
