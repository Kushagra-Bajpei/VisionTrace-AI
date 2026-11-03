"""
VisionTrace AI – Security Audit Trail API Router.
Provides read-only audit log inspection for authorized administrators and reviewers.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.audit import AuditLogResponse
from app.services.audit_service import AuditService

router = APIRouter()


@router.get(
    "",
    response_model=List[AuditLogResponse],
    summary="List security audit logs (Admin and Reviewer only)",
)
def get_audit_logs(
    action: Optional[str] = Query(None, description="Filter by action name"),
    target_type: Optional[str] = Query(None, description="Filter by target type"),
    outcome: Optional[str] = Query(None, description="Filter by outcome: success, denied, failure"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_role(["admin", "reviewer"])),
    db: Session = Depends(get_db),
):
    return AuditService.list_logs(
        db=db,
        action=action,
        target_type=target_type,
        outcome=outcome,
        skip=skip,
        limit=limit,
    )
