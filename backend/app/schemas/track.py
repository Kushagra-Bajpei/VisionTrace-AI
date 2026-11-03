"""
Pydantic schemas for ByteTrack tracks.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict

from app.schemas.event import EventResponse


class TrackBase(BaseModel):
    video_id: uuid.UUID
    track_id: int
    object_class: str
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    confidence_avg: float
    attributes: Optional[Dict[str, Any]] = None


class TrackCreate(TrackBase):
    pass


class TrackResponse(TrackBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TrackDetailResponse(TrackResponse):
    """Detailed track with associated detection events."""
    events: List[EventResponse] = []
