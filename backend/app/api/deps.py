"""
VisionTrace AI – Centralized Authentication & Authorization Dependencies (Phase 8).
Enforces role-based access control, active-user checks, case-level ownership isolation,
and scoped media token validation.
"""
import logging
import uuid
from typing import Callable, List, Optional

from fastapi import Depends, Header, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token, is_token_revoked
from app.models.investigation import Investigation
from app.models.user import User
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)


def get_token_from_header_or_query(
    request: Request,
    authorization: Optional[str] = Header(None),
    media_token: Optional[str] = Query(None),
    token: Optional[str] = Query(None),
) -> str:
    """
    Extracts authentication token.
    Prioritizes Authorization: Bearer <token>.
    Falls back to media_token / token query parameters for HTML5 media and downloads.
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization.split("Bearer ", 1)[1].strip()
    if media_token:
        return media_token.strip()
    if token:
        return token.strip()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    request: Request,
    token_str: str = Depends(get_token_from_header_or_query),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates token signature, expiration, persistent revocation, and active user status.
    """
    try:
        payload = decode_token(token_str)
    except ValueError as e:
        AuditService.log_request(
            db=db,
            request=request,
            action="auth.token_invalid",
            target_type="auth",
            outcome="denied",
            details={"error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti")
    if is_token_revoked(db, jti):
        AuditService.log_request(
            db=db,
            request=request,
            action="auth.token_revoked",
            target_type="auth",
            outcome="denied",
            details={"jti": jti},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # General API routes only accept token_type='access'
    # Media endpoints have their own validator that accepts 'media'
    if payload.get("token_type") == "media" and not request.url.path.endswith(
        ("stream", "download", "thumbnail")
    ) and "/frames/" not in request.url.path and "/crops/" not in request.url.path:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Media tokens cannot be used for general API operations.",
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload: missing subject.",
        )

    try:
        user_uuid = uuid.UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user ID format in token.",
        )

    user = db.query(User).filter(User.id == user_uuid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )

    if not user.is_active:
        AuditService.log_request(
            db=db,
            request=request,
            action="auth.user_inactive",
            target_type="user",
            target_id=str(user.id),
            actor_id=user.id,
            actor_email=user.email,
            outcome="denied",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account has been deactivated.",
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Convenience dependency returning active user."""
    return current_user


def require_role(allowed_roles: List[str]) -> Callable[[User, Session, Request], User]:
    """
    Role-based authorization dependency factory.
    Enforces minimum role privilege and records access-denied audit entries.
    """
    normalized_allowed = [r.lower().strip() for r in allowed_roles]

    def _role_checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        user_role = (current_user.role or "").lower().strip()
        if user_role not in normalized_allowed:
            AuditService.log_request(
                db=db,
                request=request,
                action="rbac.access_denied",
                target_type="endpoint",
                target_id=request.url.path,
                actor_id=current_user.id,
                actor_email=current_user.email,
                outcome="denied",
                details={
                    "user_role": user_role,
                    "required_roles": normalized_allowed,
                    "path": request.url.path,
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: role '{user_role}' lacks permission for this action.",
            )
        return current_user

    return _role_checker


require_admin = require_role(["admin"])
require_investigator_or_admin = require_role(["admin", "investigator"])
require_reviewer_or_admin = require_role(["admin", "reviewer"])


# ── Case Scoping & Ownership Validation ──────────────────────────────────────

def check_case_access(
    case: Investigation,
    user: User,
    action: str = "read",  # 'read', 'write', 'review', 'report'
    db: Optional[Session] = None,
    request: Optional[Request] = None,
) -> bool:
    """
    Validates case ownership and assignment.
    Prevents cross-user case/evidence access and UUID-guessing exploits.
    """
    user_role = (user.role or "viewer").lower().strip()

    # 1. Admins have access according to administrative policy
    if user_role == "admin":
        return True

    # 2. Investigators: Must be owner or lead investigator
    if user_role == "investigator":
        is_owner = case.owner_id == user.id
        is_lead = case.lead_investigator_id == user.id

        if is_owner or is_lead:
            return True

        if db and request:
            AuditService.log_request(
                db=db,
                request=request,
                action="case.unauthorized_access",
                target_type="case",
                target_id=str(case.id),
                actor_id=user.id,
                actor_email=user.email,
                outcome="denied",
                details={"action": action, "reason": "Not case owner or lead investigator"},
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: You are not authorized to access this investigation case.",
        )

    # 3. Reviewers: Only access cases explicitly assigned to them
    if user_role == "reviewer":
        is_assigned_reviewer = case.reviewer_id == user.id
        if not is_assigned_reviewer:
            if db and request:
                AuditService.log_request(
                    db=db,
                    request=request,
                    action="case.reviewer_unassigned",
                    target_type="case",
                    target_id=str(case.id),
                    actor_id=user.id,
                    actor_email=user.email,
                    outcome="denied",
                    details={"action": action, "reason": "Reviewer not assigned to this case"},
                )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: You are not assigned to review this case.",
            )

        if action in ("write", "create_evidence", "delete_evidence"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Reviewers have read and audit permissions only; cannot mutate evidence.",
            )
        return True

    # 4. Viewers: Read-only access
    if user_role == "viewer":
        if action != "read" and action != "download":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Viewers have read-only privileges.",
            )
        return True

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Forbidden: Unknown role.",
    )


# ── Media Token Validation Dependency ────────────────────────────────────────

def validate_media_request(
    resource_type: str,
    resource_id: str,
    request: Request,
    authorization: Optional[str] = Header(None),
    media_token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates that the incoming request has either:
    1. A valid Bearer access token, OR
    2. A tightly scoped media token matching the exact requested resource.
    """
    token_str = None
    is_media_token = False

    if authorization and authorization.startswith("Bearer "):
        token_str = authorization.split("Bearer ", 1)[1].strip()
    elif media_token:
        token_str = media_token.strip()
        is_media_token = True
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Media access requires authorization or a scoped media token.",
        )

    try:
        payload = decode_token(token_str)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))

    jti = payload.get("jti")
    if is_token_revoked(db, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked.")

    if is_media_token:
        if payload.get("token_type") != "media":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Expected a media token in query parameter.",
            )
        # Verify resource scoping
        tok_type = payload.get("resource_type")
        tok_id = payload.get("resource_id")
        if tok_type != resource_type.lower() or tok_id != str(resource_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Media token is not authorized for this specific resource.",
            )

    user_id_str = payload.get("sub")
    user = db.query(User).filter(User.id == uuid.UUID(user_id_str)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized user.")

    return user
