"""
Pydantic Schemas for VisionTrace AI API validation and serialisation.
"""
from app.schemas.camera import CameraBase, CameraCreate, CameraResponse, CameraUpdate
from app.schemas.embedding import EmbeddingBase, EmbeddingCreate, EmbeddingResponse
from app.schemas.event import EventBase, EventCreate, EventResponse
from app.schemas.investigation import (
    CaseCreateRequest,
    CaseDetailResponse,
    CaseNoteCreateRequest,
    CaseResponse,
    CaseUpdateRequest,
    EvidenceAddRequest,
    EvidenceResponse,
    EvidenceUpdateRequest,
    InvestigationBase,
    InvestigationCreate,
    InvestigationMessageBase,
    InvestigationMessageCreate,
    InvestigationMessageResponse,
    InvestigationResponse,
    InvestigationUpdate,
)
from app.schemas.report import (
    ReportBase,
    ReportCreate,
    ReportGenerateRequest,
    ReportResponse,
    ReportUpdate,
)
from app.schemas.track import TrackBase, TrackCreate, TrackResponse
from app.schemas.user import UserBase, UserCreate, UserResponse, UserUpdate
from app.schemas.video import VideoBase, VideoCreate, VideoResponse, VideoUpdate

__all__ = [
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "CameraBase",
    "CameraCreate",
    "CameraUpdate",
    "CameraResponse",
    "VideoBase",
    "VideoCreate",
    "VideoUpdate",
    "VideoResponse",
    "TrackBase",
    "TrackCreate",
    "TrackResponse",
    "EventBase",
    "EventCreate",
    "EventResponse",
    "EmbeddingBase",
    "EmbeddingCreate",
    "EmbeddingResponse",
    "InvestigationBase",
    "InvestigationCreate",
    "InvestigationUpdate",
    "InvestigationResponse",
    "InvestigationMessageBase",
    "InvestigationMessageCreate",
    "InvestigationMessageResponse",
    "ReportBase",
    "ReportCreate",
    "ReportUpdate",
    "ReportResponse",
]
