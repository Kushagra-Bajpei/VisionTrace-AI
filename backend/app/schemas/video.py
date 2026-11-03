"""
Pydantic schemas for Video uploads, processing status, and metadata.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class VideoBase(BaseModel):
    filename: str
    original_filename: str
    file_size: int
    camera_id: Optional[uuid.UUID] = None


class VideoCreate(VideoBase):
    file_path: str


class VideoUpdate(BaseModel):
    status: Optional[str] = None
    processing_progress: Optional[float] = None
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    error_message: Optional[str] = None
    thumbnail_path: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None


class VideoResponse(VideoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_path: str
    duration: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    status: str
    processing_progress: float = 0.0
    error_message: Optional[str] = None
    thumbnail_path: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = None
    file_hash: Optional[str] = None
    hash_algorithm: Optional[str] = None
    hashed_at: Optional[datetime] = None
    uploaded_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class ExtractedFrameInfo(BaseModel):
    index: int
    timestamp_seconds: float
    filename: str
    preview_url: str
