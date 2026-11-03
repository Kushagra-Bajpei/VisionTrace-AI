"""
Pydantic schemas for Investigations, Evidence, and Investigation Messages.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ── Investigation Messages / Notes ──────────────────────────────────────────
class InvestigationMessageBase(BaseModel):
    sender_type: str = "investigator"  # "investigator", "system", "ai_copilot"
    message: str
    references: Optional[Dict[str, Any]] = None


class InvestigationMessageCreate(InvestigationMessageBase):
    pass


class CaseNoteCreateRequest(BaseModel):
    message: str
    sender_type: str = "investigator"
    references: Optional[Dict[str, Any]] = None


class InvestigationMessageResponse(InvestigationMessageBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    user_id: Optional[uuid.UUID] = None
    created_at: datetime


# ── Investigation Evidence ──────────────────────────────────────────────────
class EvidenceAddRequest(BaseModel):
    video_id: uuid.UUID
    timestamp: float
    event_id: Optional[uuid.UUID] = None
    track_id: Optional[uuid.UUID] = None
    evidence_type: str = "detection"  # 'detection', 'tracked_object', 'keyframe', 'visual_similarity', 'note'
    frame_path: Optional[str] = None
    crop_path: Optional[str] = None
    object_class: Optional[str] = None
    confidence: Optional[float] = None
    visual_similarity_score: Optional[float] = None
    notes: Optional[str] = None
    sequence_number: Optional[int] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class EvidenceUpdateRequest(BaseModel):
    notes: Optional[str] = None
    sequence_number: Optional[int] = None
    custom_metadata: Optional[Dict[str, Any]] = None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    investigation_id: uuid.UUID
    video_id: uuid.UUID
    timestamp: float
    event_id: Optional[uuid.UUID] = None
    track_id: Optional[uuid.UUID] = None
    evidence_type: str
    frame_path: Optional[str] = None
    crop_path: Optional[str] = None
    frame_url: Optional[str] = None
    crop_url: Optional[str] = None
    object_class: Optional[str] = None
    confidence: Optional[float] = None
    visual_similarity_score: Optional[float] = None
    notes: Optional[str] = None
    sequence_number: int
    custom_metadata: Optional[Dict[str, Any]] = None
    evidence_hash: Optional[str] = None
    hash_algorithm: Optional[str] = None
    hashed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    video_filename: Optional[str] = None
    video_title: Optional[str] = None


# ── Investigations / Cases ──────────────────────────────────────────────────
class InvestigationBase(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "open"  # 'open', 'in_progress', 'under_review', 'closed'
    priority: str = "medium"  # 'low', 'medium', 'high', 'critical'
    tags: Optional[List[str]] = Field(default_factory=list)
    lead_investigator_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    reviewer_id: Optional[uuid.UUID] = None


class InvestigationCreate(InvestigationBase):
    pass


class CaseCreateRequest(InvestigationCreate):
    pass


class InvestigationUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    tags: Optional[List[str]] = None
    lead_investigator_id: Optional[uuid.UUID] = None
    owner_id: Optional[uuid.UUID] = None
    reviewer_id: Optional[uuid.UUID] = None


class CaseUpdateRequest(InvestigationUpdate):
    pass


class InvestigationResponse(InvestigationBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    evidence_count: int = 0
    created_at: datetime
    updated_at: datetime
    messages: List[InvestigationMessageResponse] = []


class CaseResponse(InvestigationResponse):
    pass


class CaseDetailResponse(CaseResponse):
    evidence_items: List[EvidenceResponse] = []
