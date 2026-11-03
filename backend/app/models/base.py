"""
Base model and shared mixins for VisionTrace AI models.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.core.database import Base

# Universal JSON column that compiles to JSONB on PostgreSQL and JSON on SQLite
JSONType = JSON().with_variant(JSONB, "postgresql")


class TimestampMixin:
    """Provides automatic created_at and updated_at timezone-aware timestamps."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UUIDMixin:
    """Provides a UUID primary key default."""
    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
