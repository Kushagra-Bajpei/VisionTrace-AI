"""
Pydantic schemas for detected events.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class EventBase(BaseModel):
    video_id: uuid.UUID
    camera_id: Optional[uuid.UUID] = None
    track_id: Optional[uuid.UUID] = None
    timestamp: float
    event_type: str
    description: str
    confidence: float = 1.0
    bounding_box: Optional[Dict[str, Any]] = None
    frame_path: Optional[str] = None
    clip_start_time: Optional[float] = None
    clip_end_time: Optional[float] = None
    clip_path: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None


class EventCreate(EventBase):
    pass


class EventResponse(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
