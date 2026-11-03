"""
Camera model for CCTV feeds and recorded video sources.
"""
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.video import Video
    from app.models.event import Event


class Camera(Base, UUIDMixin, TimestampMixin):
    """
    Physical or logical surveillance camera stream/location.
    """
    __tablename__ = "cameras"

    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rtsp_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    videos: Mapped[List["Video"]] = relationship("Video", back_populates="camera")
    events: Mapped[List["Event"]] = relationship("Event", back_populates="camera")

    def __repr__(self) -> str:
        return f"<Camera {self.name} ({self.status})>"
