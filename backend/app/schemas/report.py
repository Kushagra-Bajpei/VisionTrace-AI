"""
Pydantic schemas for Incident Reports and PDF Generation.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class ReportBase(BaseModel):
    title: str
    executive_summary: str
    investigation_id: Optional[uuid.UUID] = None
    findings: Optional[Dict[str, Any]] = None
    evidence_timeline: Optional[Dict[str, Any]] = None
    generated_by_ai: bool = True
    status: str = "draft"


class ReportCreate(ReportBase):
    pass


class ReportGenerateRequest(BaseModel):
    title: Optional[str] = None
    executive_summary: Optional[str] = None
    include_evidence_thumbnails: bool = True
    custom_notes: Optional[str] = None


class ReportUpdate(BaseModel):
    title: Optional[str] = None
    executive_summary: Optional[str] = None
    findings: Optional[Dict[str, Any]] = None
    evidence_timeline: Optional[Dict[str, Any]] = None
    pdf_path: Optional[str] = None
    status: Optional[str] = None


class ReportResponse(ReportBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    case_title: Optional[str] = None
    pdf_path: Optional[str] = None
    download_url: Optional[str] = None
    pdf_hash: Optional[str] = None
    hash_algorithm: Optional[str] = None
    hashed_at: Optional[datetime] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
