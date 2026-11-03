"""
SQLAlchemy ORM Models for VisionTrace AI.
Exporting all models so that Alembic and metadata discovery find all tables.
"""
from app.core.database import Base
from app.models.base import JSONType, TimestampMixin, UUIDMixin
from app.models.audit import AuditLog, RevokedToken
from app.models.camera import Camera
from app.models.embedding import CLIP_EMBEDDING_DIM, Embedding
from app.models.event import Event
from app.models.investigation import Investigation, InvestigationEvidence, InvestigationMessage
from app.models.report import Report
from app.models.track import Track
from app.models.video import Video
from app.models.user import User

__all__ = [
    "Base",
    "UUIDMixin",
    "TimestampMixin",
    "JSONType",
    "User",
    "Camera",
    "Video",
    "Track",
    "Event",
    "Embedding",
    "CLIP_EMBEDDING_DIM",
    "Investigation",
    "InvestigationEvidence",
    "InvestigationMessage",
    "Report",
    "AuditLog",
    "RevokedToken",
]
