"""
VisionTrace AI – Authentication, User Profiles, RBAC & Media Token Router.
"""
import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.core.security import (
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_MEDIA_TOKEN_EXPIRE_SECONDS,
    create_access_token,
    create_media_token,
    decode_token,
    hash_password,
    revoke_token,
    verify_password,
)
from app.models.investigation import Investigation
from app.models.report import Report
from app.models.user import User
from app.models.video import Video
from app.schemas.user import (
    BootstrapAdminRequest,
    MediaTokenRequest,
    MediaTokenResponse,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    UserRoleUpdateRequest,
)
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)

router = APIRouter()

VALID_ROLES = {"admin", "investigator", "reviewer", "viewer"}


# ── Bootstrap Admin ──────────────────────────────────────────────────────────

@router.post(
    "/bootstrap-admin",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Bootstrap initial administrator account (Allowed only when 0 users exist)",
)
def bootstrap_admin(
    payload: BootstrapAdminRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    user_count = db.query(User).count()
    if user_count > 0:
        AuditService.log_request(
            db=db,
            request=request,
            action="auth.bootstrap_denied",
            target_type="auth",
            outcome="denied",
            details={"reason": "System is already bootstrapped with existing users."},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System is already bootstrapped. An administrator account already exists.",
        )

    admin_user = User(
        id=uuid.uuid4(),
        email=payload.email.lower().strip(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role="admin",
        is_active=True,
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    token = create_access_token(admin_user.id, admin_user.email, admin_user.role)

    AuditService.log_request(
        db=db,
        request=request,
        action="auth.bootstrap_admin",
        target_type="user",
        target_id=str(admin_user.id),
        actor_id=admin_user.id,
        actor_email=admin_user.email,
        outcome="success",
        details={"email": admin_user.email, "role": "admin"},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(admin_user),
    )


# ── Registration & Login ────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
def register(
    payload: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    clean_email = payload.email.lower().strip()
    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        AuditService.log_request(
            db=db,
            request=request,
            action="auth.register_duplicate",
            target_type="auth",
            outcome="denied",
            details={"email": clean_email},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    # First user becomes admin; subsequent users default to investigator
    user_count = db.query(User).count()
    assigned_role = "admin" if user_count == 0 else "investigator"

    new_user = User(
        id=uuid.uuid4(),
        email=clean_email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=assigned_role,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token(new_user.id, new_user.email, new_user.role)

    AuditService.log_request(
        db=db,
        request=request,
        action="auth.register",
        target_type="user",
        target_id=str(new_user.id),
        actor_id=new_user.id,
        actor_email=new_user.email,
        outcome="success",
        details={"role": assigned_role},
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(new_user),
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and acquire JWT access token",
)
def login(
    payload: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    clean_email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == clean_email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        AuditService.log_request(
            db=db,
            request=request,
            action="auth.login_failed",
            target_type="auth",
            outcome="denied",
            details={"attempted_email": clean_email},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        AuditService.log_request(
            db=db,
            request=request,
            action="auth.login_inactive",
            target_type="user",
            target_id=str(user.id),
            actor_id=user.id,
            actor_email=user.email,
            outcome="denied",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated. Contact an administrator.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user.id, user.email, user.role)

    AuditService.log_request(
        db=db,
        request=request,
        action="auth.login_success",
        target_type="user",
        target_id=str(user.id),
        actor_id=user.id,
        actor_email=user.email,
        outcome="success",
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=UserResponse.model_validate(user),
    )


@router.post(
    "/logout",
    summary="Revoke token and terminate session",
)
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    if authorization and authorization.startswith("Bearer "):
        token_str = authorization.split("Bearer ", 1)[1].strip()
        try:
            payload = decode_token(token_str)
            jti = payload.get("jti")
            exp = payload.get("exp", 0)
            if jti:
                revoke_token(db, jti, current_user.id, exp)
        except Exception as e:
            logger.warning("Error parsing token on logout: %s", e)

    AuditService.log_request(
        db=db,
        request=request,
        action="auth.logout",
        target_type="user",
        target_id=str(current_user.id),
        actor_id=current_user.id,
        actor_email=current_user.email,
        outcome="success",
    )

    return {"success": True, "message": "Successfully logged out. Token revoked."}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


# ── Scoped Media Token Generation ───────────────────────────────────────────

@router.post(
    "/media-token",
    response_model=MediaTokenResponse,
    summary="Acquire a short-lived (120s) token tightly scoped to a specific media resource",
)
def get_media_token(
    payload: MediaTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    res_type = payload.resource_type.lower().strip()
    res_id = payload.resource_id.strip()

    if res_type not in {"video", "frame", "crop", "report"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid resource_type. Must be 'video', 'frame', 'crop', or 'report'.",
        )

    # Permission check for target resource
    user_role = (current_user.role or "viewer").lower().strip()
    if user_role != "admin":
        if res_type == "video":
            try:
                vid_uuid = uuid.UUID(res_id)
                video = db.query(Video).filter(Video.id == vid_uuid).first()
                if not video:
                    raise HTTPException(status_code=404, detail="Video not found.")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid video ID format.")

        elif res_type == "report":
            try:
                rep_uuid = uuid.UUID(res_id)
                report = db.query(Report).filter(Report.id == rep_uuid).first()
                if not report:
                    raise HTTPException(status_code=404, detail="Report not found.")
                if report.investigation_id:
                    case = db.query(Investigation).filter(Investigation.id == report.investigation_id).first()
                    if case and user_role == "reviewer" and case.reviewer_id != current_user.id:
                        raise HTTPException(status_code=403, detail="Not authorized to access this report.")
                    if case and user_role == "investigator" and case.owner_id != current_user.id and case.lead_investigator_id != current_user.id:
                        raise HTTPException(status_code=403, detail="Not authorized to access this report.")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid report ID format.")

    media_tok = create_media_token(
        user_id=current_user.id,
        resource_type=res_type,
        resource_id=res_id,
        expires_in_seconds=DEFAULT_MEDIA_TOKEN_EXPIRE_SECONDS,
    )

    return MediaTokenResponse(
        media_token=media_tok,
        token_type="media",
        expires_in=DEFAULT_MEDIA_TOKEN_EXPIRE_SECONDS,
        resource_type=res_type,
        resource_id=res_id,
    )


# ── Admin User & Role Management ─────────────────────────────────────────────

@router.get(
    "/users",
    response_model=List[UserResponse],
    summary="List all users (Admin only)",
)
def list_users(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
    summary="Update user role or active status (Admin only)",
)
def update_user_role(
    user_id: uuid.UUID,
    payload: UserRoleUpdateRequest,
    request: Request,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )

    new_role = payload.role.lower().strip()
    if new_role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}",
        )

    # Protection: Prevent deactivating or demoting the last active administrator
    if target_user.role == "admin" and (new_role != "admin" or payload.is_active is False):
        active_admins = (
            db.query(User)
            .filter(User.role == "admin", User.is_active.is_(True), User.id != user_id)
            .count()
        )
        if active_admins == 0:
            AuditService.log_request(
                db=db,
                request=request,
                action="rbac.demote_last_admin_blocked",
                target_type="user",
                target_id=str(user_id),
                actor_id=admin_user.id,
                actor_email=admin_user.email,
                outcome="denied",
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote or deactivate the last active system administrator.",
            )

    old_role = target_user.role
    old_active = target_user.is_active

    target_user.role = new_role
    if payload.is_active is not None:
        target_user.is_active = payload.is_active

    db.commit()
    db.refresh(target_user)

    AuditService.log_request(
        db=db,
        request=request,
        action="user.role_change",
        target_type="user",
        target_id=str(target_user.id),
        actor_id=admin_user.id,
        actor_email=admin_user.email,
        outcome="success",
        details={
            "target_email": target_user.email,
            "old_role": old_role,
            "new_role": new_role,
            "old_active": old_active,
            "new_active": target_user.is_active,
        },
    )

    return target_user
