"""
VisionTrace AI – Audit Logging Service.
Guarantees synchronous persistence of security, authentication, and investigation actions.
"""
import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import Request
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

# Keys that must never be persisted in audit logs
SENSITIVE_KEYS = {
    "password",
    "plain_password",
    "hashed_password",
    "token",
    "access_token",
    "media_token",
    "authorization",
    "secret",
    "app_secret_key",
}


def sanitize_details(details: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Recursively removes sensitive keys from audit log metadata."""
    if not details:
        return None
    clean = {}
    for k, v in details.items():
        if k.lower() in SENSITIVE_KEYS:
            clean[k] = "[REDACTED]"
        elif isinstance(v, dict):
            clean[k] = sanitize_details(v)
        elif isinstance(v, str) and ("bearer" in v.lower() or len(v) > 500):
            clean[k] = "[REDACTED_OR_TRUNCATED]"
        else:
            clean[k] = v
    return clean


class AuditService:
    """Synchronous, reliable audit logger for security-critical actions."""

    @classmethod
    def log(
        cls,
        db: Session,
        action: str = "unknown",
        target_type: str = "system",
        outcome: str = "success",  # 'success', 'denied', 'failure'
        target_id: Optional[Any] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        client_ip: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        actor: Optional[Any] = None,
        **kwargs: Any,
    ) -> AuditLog:
        """Persists a new immutable audit record to the database."""
        if actor is not None:
            if hasattr(actor, "id") and actor_id is None:
                actor_id = actor.id
            if hasattr(actor, "email") and actor_email is None:
                actor_email = actor.email

        clean_meta = sanitize_details(details)
        record = AuditLog(
            id=uuid.uuid4(),
            actor_id=actor_id,
            actor_email=actor_email,
            action=action.strip().lower(),
            target_type=target_type.strip().lower(),
            target_id=str(target_id) if target_id is not None else None,
            outcome=outcome.strip().lower(),
            client_ip=client_ip,
            details=clean_meta,
        )
        try:
            db.add(record)
            db.commit()
            db.refresh(record)
            return record
        except Exception as e:
            db.rollback()
            logger.error("Failed to commit audit log record: %s", e)
            raise

    @classmethod
    def log_request(
        cls,
        db: Session,
        request: Request,
        action: str,
        target_type: str,
        outcome: str = "success",
        target_id: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_email: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """Extracts client IP from FastAPI Request and records an audit log entry."""
        client_ip = request.client.host if request.client else "unknown"
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()

        return cls.log(
            db=db,
            action=action,
            target_type=target_type,
            outcome=outcome,
            target_id=target_id,
            actor_id=actor_id,
            actor_email=actor_email,
            client_ip=client_ip,
            details=details,
        )

    @classmethod
    def list_logs(
        cls,
        db: Session,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        outcome: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AuditLog]:
        """Lists audit logs with optional filtering. Accessible only by authorized admins and reviewers."""
        query = db.query(AuditLog)
        if action:
            query = query.filter(AuditLog.action == action.lower().strip())
        if target_type:
            query = query.filter(AuditLog.target_type == target_type.lower().strip())
        if actor_id:
            query = query.filter(AuditLog.actor_id == actor_id)
        if outcome:
            query = query.filter(AuditLog.outcome == outcome.lower().strip())

        return query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit).all()
