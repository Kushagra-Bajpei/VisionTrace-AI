"""
Investigation Cases and Evidence API Router.
Supports case management, evidentiary item linking, investigator notes, forensic PDF generation,
and cryptographic evidence integrity verification with strict RBAC.
"""
import logging
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.responses import FileResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import (
    check_case_access,
    get_current_user,
    require_investigator_or_admin,
    validate_media_request,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.models.investigation import Investigation, InvestigationEvidence, InvestigationMessage
from app.models.report import Report
from app.models.user import User
from app.models.video import Video
from app.schemas.investigation import (
    CaseCreateRequest,
    CaseDetailResponse,
    CaseNoteCreateRequest,
    CaseResponse,
    CaseUpdateRequest,
    EvidenceAddRequest,
    EvidenceResponse,
    EvidenceUpdateRequest,
    InvestigationMessageResponse,
)
from app.schemas.report import ReportGenerateRequest, ReportResponse
from app.services.audit_service import AuditService
from app.services.integrity_service import IntegrityService
from app.services.report_service import InvestigationReportService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()


def _format_evidence_response(item: InvestigationEvidence) -> EvidenceResponse:
    """Format an InvestigationEvidence model into EvidenceResponse with secure URLs."""
    frame_url = None
    if item.frame_path:
        frame_filename = Path(item.frame_path).name
        frame_url = f"/api/v1/videos/{item.video_id}/frames/{frame_filename}"

    crop_url = None
    if item.crop_path:
        crop_filename = Path(item.crop_path).name
        crop_url = f"/api/v1/videos/{item.video_id}/crops/{crop_filename}"

    video_filename = item.video.filename if item.video else None
    video_title = (item.video.original_filename or item.video.filename) if item.video else None

    return EvidenceResponse(
        id=item.id,
        investigation_id=item.investigation_id,
        video_id=item.video_id,
        timestamp=item.timestamp,
        event_id=item.event_id,
        track_id=item.track_id,
        evidence_type=item.evidence_type,
        frame_path=item.frame_path,
        crop_path=item.crop_path,
        frame_url=frame_url,
        crop_url=crop_url,
        object_class=item.object_class,
        confidence=item.confidence,
        visual_similarity_score=item.visual_similarity_score,
        notes=item.notes,
        sequence_number=item.sequence_number,
        custom_metadata=item.custom_metadata,
        evidence_hash=item.evidence_hash,
        hash_algorithm=item.hash_algorithm,
        hashed_at=item.hashed_at,
        created_at=item.created_at,
        updated_at=item.updated_at,
        video_filename=video_filename,
        video_title=video_title,
    )


# ── Cases CRUD ──────────────────────────────────────────────────────────────

@router.get("", response_model=List[CaseResponse], summary="List investigation cases")
def list_cases(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: open, in_progress, under_review, closed"),
    priority: Optional[str] = Query(None, description="Filter by priority: low, medium, high, critical"),
    search: Optional[str] = Query(None, description="Search by title or description keyword"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Investigation)

    # Multi-tenant / Case Scoping:
    # Admin sees all cases.
    # Investigator sees cases they own or are lead investigator on.
    # Reviewer sees cases where reviewer_id == user.id.
    # Viewer sees cases they own, are assigned to, or are assigned as reviewer.
    if current_user.role != "admin":
        if current_user.role == "investigator":
            query = query.filter(
                or_(
                    Investigation.owner_id == current_user.id,
                    Investigation.lead_investigator_id == current_user.id,
                )
            )
        elif current_user.role == "reviewer":
            query = query.filter(Investigation.reviewer_id == current_user.id)
        else:  # viewer
            query = query.filter(
                or_(
                    Investigation.owner_id == current_user.id,
                    Investigation.lead_investigator_id == current_user.id,
                    Investigation.reviewer_id == current_user.id,
                )
            )

    if status_filter:
        query = query.filter(Investigation.status == status_filter.lower())
    if priority:
        query = query.filter(Investigation.priority == priority.lower())
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Investigation.title.ilike(s),
                Investigation.description.ilike(s),
            )
        )

    investigations = query.order_by(Investigation.updated_at.desc()).offset(skip).limit(limit).all()

    # Calculate evidence counts
    case_ids = [c.id for c in investigations]
    counts_map = {}
    if case_ids:
        counts = (
            db.query(InvestigationEvidence.investigation_id, func.count(InvestigationEvidence.id))
            .filter(InvestigationEvidence.investigation_id.in_(case_ids))
            .group_by(InvestigationEvidence.investigation_id)
            .all()
        )
        counts_map = {row[0]: row[1] for row in counts}

    results = []
    for inv in investigations:
        resp = CaseResponse.model_validate(inv)
        resp.evidence_count = counts_map.get(inv.id, 0)
        results.append(resp)

    return results


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED, summary="Create a new case")
def create_case(
    payload: CaseCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_investigator_or_admin),
):
    valid_statuses = {"open", "in_progress", "under_review", "closed"}
    valid_priorities = {"low", "medium", "high", "critical"}

    case_status = payload.status.lower() if payload.status else "open"
    if case_status not in valid_statuses:
        case_status = "open"

    case_priority = payload.priority.lower() if payload.priority else "medium"
    if case_priority not in valid_priorities:
        case_priority = "medium"

    new_case = Investigation(
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        status=case_status,
        priority=case_priority,
        tags=payload.tags or [],
        owner_id=current_user.id,
        lead_investigator_id=payload.lead_investigator_id or current_user.id,
        reviewer_id=payload.reviewer_id,
    )
    db.add(new_case)
    db.commit()
    db.refresh(new_case)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="case_create",
        target_type="investigation",
        target_id=new_case.id,
        outcome="success",
        client_ip=client_ip,
        details={"title": new_case.title, "priority": new_case.priority, "status": new_case.status},
    )

    resp = CaseResponse.model_validate(new_case)
    resp.evidence_count = 0
    return resp


@router.get("/reports/archive", response_model=List[ReportResponse], summary="List all forensic reports accessible to user")
def list_all_case_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all forensic incident reports generated across all cases accessible to the user.
    Enforces RBAC / case scoping: Admin sees all, Investigators see reports for their cases.
    """
    query = db.query(Report).join(Investigation, Report.investigation_id == Investigation.id)
    if current_user.role != "admin":
        if current_user.role == "investigator":
            query = query.filter(
                or_(
                    Investigation.owner_id == current_user.id,
                    Investigation.lead_investigator_id == current_user.id,
                )
            )
        elif current_user.role == "reviewer":
            query = query.filter(Investigation.reviewer_id == current_user.id)
        else:
            query = query.filter(
                or_(
                    Investigation.owner_id == current_user.id,
                    Investigation.lead_investigator_id == current_user.id,
                    Investigation.reviewer_id == current_user.id,
                )
            )

    reports = query.order_by(Report.created_at.desc()).all()
    results = []
    for r in reports:
        resp = ReportResponse.model_validate(r)
        resp.download_url = f"/api/v1/cases/{r.investigation_id}/reports/{r.id}/download"
        if r.investigation:
            resp.case_title = r.investigation.title
        results.append(resp)
    return results


@router.get("/{case_id}", response_model=CaseDetailResponse, summary="Get case details with evidence and messages")
def get_case(
    case_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "read", db, request)

    evidence_items = (
        db.query(InvestigationEvidence)
        .filter(InvestigationEvidence.investigation_id == case_id)
        .order_by(InvestigationEvidence.sequence_number.asc(), InvestigationEvidence.timestamp.asc())
        .all()
    )

    formatted_evidence = [_format_evidence_response(item) for item in evidence_items]

    messages = (
        db.query(InvestigationMessage)
        .filter(InvestigationMessage.investigation_id == case_id)
        .order_by(InvestigationMessage.created_at.asc())
        .all()
    )
    formatted_messages = [InvestigationMessageResponse.model_validate(m) for m in messages]

    resp = CaseDetailResponse(
        id=investigation.id,
        title=investigation.title,
        description=investigation.description,
        status=investigation.status,
        priority=investigation.priority,
        tags=investigation.tags or [],
        owner_id=investigation.owner_id,
        reviewer_id=investigation.reviewer_id,
        lead_investigator_id=investigation.lead_investigator_id,
        evidence_count=len(formatted_evidence),
        created_at=investigation.created_at,
        updated_at=investigation.updated_at,
        evidence_items=formatted_evidence,
        messages=formatted_messages,
    )
    return resp


@router.patch("/{case_id}", response_model=CaseResponse, summary="Update case metadata")
def update_case(
    case_id: uuid.UUID,
    payload: CaseUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "update", db, request)

    changes = {}
    if payload.title is not None:
        investigation.title = payload.title.strip()
        changes["title"] = investigation.title
    if payload.description is not None:
        investigation.description = payload.description.strip()
        changes["description"] = "updated"
    if payload.status is not None:
        st = payload.status.lower()
        if st in {"open", "in_progress", "under_review", "closed"}:
            investigation.status = st
            changes["status"] = st
    if payload.priority is not None:
        pr = payload.priority.lower()
        if pr in {"low", "medium", "high", "critical"}:
            investigation.priority = pr
            changes["priority"] = pr
    if payload.tags is not None:
        investigation.tags = payload.tags
        changes["tags"] = payload.tags
    if payload.lead_investigator_id is not None:
        investigation.lead_investigator_id = payload.lead_investigator_id
        changes["lead_investigator_id"] = str(payload.lead_investigator_id)
    if payload.reviewer_id is not None:
        investigation.reviewer_id = payload.reviewer_id
        changes["reviewer_id"] = str(payload.reviewer_id)
    if payload.owner_id is not None and current_user.role == "admin":
        investigation.owner_id = payload.owner_id
        changes["owner_id"] = str(payload.owner_id)

    db.commit()
    db.refresh(investigation)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="case_update",
        target_type="investigation",
        target_id=investigation.id,
        outcome="success",
        client_ip=client_ip,
        details=changes,
    )

    ev_count = (
        db.query(func.count(InvestigationEvidence.id))
        .filter(InvestigationEvidence.investigation_id == case_id)
        .scalar()
        or 0
    )

    resp = CaseResponse.model_validate(investigation)
    resp.evidence_count = ev_count
    return resp


@router.delete("/{case_id}", summary="Delete an investigation case")
def delete_case(
    case_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "delete", db, request)

    case_title = investigation.title
    db.delete(investigation)
    db.commit()

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="case_delete",
        target_type="investigation",
        target_id=case_id,
        outcome="success",
        client_ip=client_ip,
        details={"title": case_title},
    )

    return {"success": True, "message": f"Case {case_id} successfully deleted"}


# ── Evidence Management ─────────────────────────────────────────────────────

@router.get("/{case_id}/evidence", response_model=List[EvidenceResponse], summary="List evidence for case")
def get_case_evidence(
    case_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "read", db, request)

    evidence_items = (
        db.query(InvestigationEvidence)
        .filter(InvestigationEvidence.investigation_id == case_id)
        .order_by(InvestigationEvidence.sequence_number.asc(), InvestigationEvidence.timestamp.asc())
        .all()
    )
    return [_format_evidence_response(item) for item in evidence_items]


@router.post(
    "/{case_id}/evidence",
    response_model=EvidenceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add evidence item to case",
)
def add_case_evidence(
    case_id: uuid.UUID,
    payload: EvidenceAddRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "evidence_add", db, request)

    video = db.query(Video).filter(Video.id == payload.video_id).first()
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source video {payload.video_id} not found",
        )

    # Duplicate check: check if same event_id is already linked, or exact match on (video_id, timestamp)
    dup_query = db.query(InvestigationEvidence).filter(
        InvestigationEvidence.investigation_id == case_id,
        InvestigationEvidence.video_id == payload.video_id,
    )
    if payload.event_id:
        existing = dup_query.filter(InvestigationEvidence.event_id == payload.event_id).first()
        if existing:
            if payload.notes:
                existing.notes = (
                    f"{existing.notes}\n[Update]: {payload.notes}" if existing.notes else payload.notes
                )
                db.commit()
                db.refresh(existing)
            return _format_evidence_response(existing)
    else:
        existing = (
            dup_query.filter(
                func.abs(InvestigationEvidence.timestamp - payload.timestamp) < 0.1,
                InvestigationEvidence.evidence_type == payload.evidence_type,
            )
            .first()
        )
        if existing:
            if payload.notes:
                existing.notes = (
                    f"{existing.notes}\n[Update]: {payload.notes}" if existing.notes else payload.notes
                )
                db.commit()
                db.refresh(existing)
            return _format_evidence_response(existing)

    # Assign sequence number
    if payload.sequence_number is not None:
        seq = payload.sequence_number
    else:
        max_seq = (
            db.query(func.max(InvestigationEvidence.sequence_number))
            .filter(InvestigationEvidence.investigation_id == case_id)
            .scalar()
        )
        seq = (max_seq or 0) + 1

    # Sanitize paths to relative filenames if full paths provided
    clean_frame = payload.frame_path
    if clean_frame and ("\\" in clean_frame or "/" in clean_frame):
        clean_frame = f"frames/{payload.video_id}/{Path(clean_frame).name}"

    clean_crop = payload.crop_path
    if clean_crop and ("\\" in clean_crop or "/" in clean_crop):
        clean_crop = f"crops/{payload.video_id}/{Path(clean_crop).name}"

    evidence = InvestigationEvidence(
        investigation_id=case_id,
        video_id=payload.video_id,
        timestamp=payload.timestamp,
        event_id=payload.event_id,
        track_id=payload.track_id,
        evidence_type=payload.evidence_type,
        frame_path=clean_frame,
        crop_path=clean_crop,
        object_class=payload.object_class,
        confidence=payload.confidence,
        visual_similarity_score=payload.visual_similarity_score,
        notes=payload.notes,
        sequence_number=seq,
        custom_metadata=payload.custom_metadata,
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    # Compute SHA-256 integrity hash for evidence
    IntegrityService.record_evidence_hash(db, evidence)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="evidence_add",
        target_type="investigation_evidence",
        target_id=evidence.id,
        outcome="success",
        client_ip=client_ip,
        details={
            "case_id": str(case_id),
            "video_id": str(payload.video_id),
            "evidence_type": evidence.evidence_type,
            "timestamp": evidence.timestamp,
            "evidence_hash": evidence.evidence_hash,
        },
    )

    return _format_evidence_response(evidence)


@router.patch("/{case_id}/evidence/{evidence_id}", response_model=EvidenceResponse, summary="Update evidence notes or order")
def update_case_evidence(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    payload: EvidenceUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "evidence_update", db, request)

    evidence = (
        db.query(InvestigationEvidence)
        .filter(
            InvestigationEvidence.id == evidence_id,
            InvestigationEvidence.investigation_id == case_id,
        )
        .first()
    )
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item {evidence_id} not found in case {case_id}",
        )

    if payload.notes is not None:
        evidence.notes = payload.notes
    if payload.sequence_number is not None:
        evidence.sequence_number = payload.sequence_number
    if payload.custom_metadata is not None:
        evidence.custom_metadata = payload.custom_metadata

    db.commit()
    db.refresh(evidence)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="evidence_update",
        target_type="investigation_evidence",
        target_id=evidence.id,
        outcome="success",
        client_ip=client_ip,
        details={"case_id": str(case_id)},
    )

    return _format_evidence_response(evidence)


@router.delete("/{case_id}/evidence/{evidence_id}", summary="Remove evidence from case")
def delete_case_evidence(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "evidence_delete", db, request)

    evidence = (
        db.query(InvestigationEvidence)
        .filter(
            InvestigationEvidence.id == evidence_id,
            InvestigationEvidence.investigation_id == case_id,
        )
        .first()
    )
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item {evidence_id} not found in case {case_id}",
        )

    db.delete(evidence)
    db.commit()

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="evidence_delete",
        target_type="investigation_evidence",
        target_id=evidence_id,
        outcome="success",
        client_ip=client_ip,
        details={"case_id": str(case_id)},
    )

    return {"success": True, "message": f"Evidence {evidence_id} removed from case {case_id}"}


# ── Case Notes / Messages ───────────────────────────────────────────────────

@router.post(
    "/{case_id}/notes",
    response_model=InvestigationMessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an investigator log note or copilot message",
)
def add_case_note(
    case_id: uuid.UUID,
    payload: CaseNoteCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "note_add", db, request)

    msg = InvestigationMessage(
        investigation_id=case_id,
        user_id=current_user.id,
        sender_type=payload.sender_type or "investigator",
        message=payload.message.strip(),
        references=payload.references,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="note_add",
        target_type="investigation_message",
        target_id=msg.id,
        outcome="success",
        client_ip=client_ip,
        details={"case_id": str(case_id), "sender_type": msg.sender_type},
    )

    return InvestigationMessageResponse.model_validate(msg)


# ── Forensic Report Generation & Download ───────────────────────────────────

@router.post(
    "/{case_id}/report",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate forensic PDF report for case",
)
def generate_case_report(
    case_id: uuid.UUID,
    request: Request,
    payload: Optional[ReportGenerateRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "report_generate", db, request)

    if payload is None:
        payload = ReportGenerateRequest()

    try:
        report = InvestigationReportService.generate_report(
            db=db,
            investigation_id=case_id,
            title=payload.title,
            executive_summary=payload.executive_summary,
            include_evidence_thumbnails=payload.include_evidence_thumbnails,
            custom_notes=payload.custom_notes,
        )
        report.created_by = current_user.id
        db.commit()
        db.refresh(report)

        # Compute SHA-256 integrity hash for generated PDF report
        IntegrityService.record_report_hash(db, report)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Failed to generate forensic report")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation error: {str(e)}",
        )

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="report_generate",
        target_type="report",
        target_id=report.id,
        outcome="success",
        client_ip=client_ip,
        details={
            "case_id": str(case_id),
            "report_title": report.title,
            "pdf_hash": report.pdf_hash,
        },
    )

    download_url = f"/api/v1/cases/{case_id}/reports/{report.id}/download"
    resp = ReportResponse.model_validate(report)
    resp.download_url = download_url
    return resp


@router.get("/{case_id}/reports", response_model=List[ReportResponse], summary="List reports generated for case")
def list_case_reports(
    case_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "read", db, request)

    reports = (
        db.query(Report)
        .filter(Report.investigation_id == case_id)
        .order_by(Report.created_at.desc())
        .all()
    )
    results = []
    for r in reports:
        resp = ReportResponse.model_validate(r)
        resp.download_url = f"/api/v1/cases/{case_id}/reports/{r.id}/download"
        results.append(resp)
    return results


@router.get("/{case_id}/reports/{report_id}/download", summary="Download generated PDF report")
def download_report(
    case_id: uuid.UUID,
    report_id: uuid.UUID,
    request: Request,
    media_token: Optional[str] = Query(None, description="Short-lived scoped media token"),
    authorization: Optional[str] = Header(None, description="Standard Bearer token"),
    db: Session = Depends(get_db),
):
    # Dual auth: validate either media token or bearer token
    current_user = validate_media_request(
        resource_type="report",
        resource_id=report_id,
        request=request,
        media_token=media_token,
        authorization=authorization,
        db=db,
    )

    report = (
        db.query(Report)
        .filter(Report.id == report_id, Report.investigation_id == case_id)
        .first()
    )
    if not report or not report.pdf_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found or no PDF has been generated",
        )

    # Check case access for user
    check_case_access(report.investigation, current_user, "read", db, request)

    file_path = settings.storage_base / report.pdf_path
    if not file_path.is_file():
        file_path = settings.reports_dir / str(case_id) / f"report_{report_id}.pdf"

    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested report PDF file is missing on server storage",
        )

    # Sanitize and ensure path is strictly inside reports directory or storage base
    try:
        resolved_file = file_path.resolve()
        resolved_reports = settings.reports_dir.resolve()
        resolved_storage = settings.storage_base.resolve()
        if not (str(resolved_file).startswith(str(resolved_reports)) or str(resolved_file).startswith(str(resolved_storage))):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid report path")

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="report_download",
        target_type="report",
        target_id=report_id,
        outcome="success",
        client_ip=client_ip,
        details={"case_id": str(case_id)},
    )

    safe_filename = f"visiontrace_case_{str(case_id)[:8]}_report_{str(report_id)[:8]}.pdf"
    response = FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=safe_filename,
    )
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


# ── Integrity Verification Endpoints ────────────────────────────────────────

@router.post(
    "/{case_id}/evidence/{evidence_id}/verify-integrity",
    summary="Cryptographically verify SHA-256 integrity of evidence item",
)
def verify_evidence_integrity(
    case_id: uuid.UUID,
    evidence_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "read", db, request)

    evidence = (
        db.query(InvestigationEvidence)
        .filter(
            InvestigationEvidence.id == evidence_id,
            InvestigationEvidence.investigation_id == case_id,
        )
        .first()
    )
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence item {evidence_id} not found in case {case_id}",
        )

    result = IntegrityService.verify_evidence_integrity(db, evidence_id)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="evidence_integrity_verify",
        target_type="investigation_evidence",
        target_id=evidence_id,
        outcome="success" if result["status"] == "verified" else "warning",
        client_ip=client_ip,
        details={
            "case_id": str(case_id),
            "integrity_status": result["status"],
            "hash_algorithm": result.get("hash_algorithm"),
        },
    )

    return result


@router.post(
    "/{case_id}/reports/{report_id}/verify-integrity",
    summary="Cryptographically verify SHA-256 integrity of PDF report",
)
def verify_report_integrity(
    case_id: uuid.UUID,
    report_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    investigation = db.query(Investigation).filter(Investigation.id == case_id).first()
    if not investigation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation case {case_id} not found",
        )

    check_case_access(investigation, current_user, "read", db, request)

    report = (
        db.query(Report)
        .filter(Report.id == report_id, Report.investigation_id == case_id)
        .first()
    )
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report {report_id} not found in case {case_id}",
        )

    result = IntegrityService.verify_report_integrity(db, report_id)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="report_integrity_verify",
        target_type="report",
        target_id=report_id,
        outcome="success" if result["status"] == "verified" else "warning",
        client_ip=client_ip,
        details={
            "case_id": str(case_id),
            "integrity_status": result["status"],
            "hash_algorithm": result.get("hash_algorithm"),
        },
    )

    return result
