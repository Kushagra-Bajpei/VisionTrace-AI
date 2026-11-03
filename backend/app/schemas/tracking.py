"""
Pydantic schemas for YOLO object detections and ByteTrack tracks.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class BoundingBoxSchema(BaseModel):
    """Normalized bounding box coordinates in [0.0, 1.0]."""
    x_min: float = Field(..., ge=0.0, le=1.0)
    y_min: float = Field(..., ge=0.0, le=1.0)
    x_max: float = Field(..., ge=0.0, le=1.0)
    y_max: float = Field(..., ge=0.0, le=1.0)
    box_format: str = "xyxyn"


class DetectionEventResponse(BaseModel):
    """Surveillance detection event with bounding box and timestamp."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    track_id: Optional[uuid.UUID] = None
    timestamp: float
    event_type: str
    description: str
    confidence: float
    bounding_box: Optional[Dict[str, Any]] = None
    frame_path: Optional[str] = None
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime


class TrackResponse(BaseModel):
    """Continuous ByteTrack object track."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    track_id: int
    object_class: str
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    confidence_avg: float
    attributes: Optional[Dict[str, Any]] = None
    created_at: datetime


class TrackDetailResponse(TrackResponse):
    """Track record with associated detection events."""
    events: List[DetectionEventResponse] = []


class VideoTrackingSummaryResponse(BaseModel):
    """Summary of detection and tracking statistics for a video."""
    video_id: uuid.UUID
    detections_count: int
    tracks_count: int
    detected_classes: List[str]
    tracks: List[TrackResponse]
