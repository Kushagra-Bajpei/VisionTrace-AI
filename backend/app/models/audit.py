"""
AuditLog and RevokedToken models for security auditing, compliance, and token revocation.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import JSONType, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuditLog(Base, UUIDMixin):
    """
    Immutable security and operational audit trail.
    Records authentication events, authorization denials, case mutations,
    evidence alterations, report generations, and integrity verification outcomes.
    """
    __tablename__ = "audit_logs"

    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    outcome: Mapped[str] = mapped_column(String(50), default="success", nullable=False, index=True)  # 'success', 'denied', 'failure'
    client_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONType, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationship
    actor: Mapped[Optional["User"]] = relationship("User", foreign_keys=[actor_id])

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} on {self.target_type}:{self.target_id} by {self.actor_email} ({self.outcome})>"


class RevokedToken(Base, UUIDMixin):
    """
    Persistent revoked JWT identifiers (JTI).
    Ensures immediate, cluster-wide token invalidation upon logout or administrative revocation.
    """
    __tablename__ = "revoked_tokens"

    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<RevokedToken {self.jti[:8]}... (User: {self.user_id})>"
