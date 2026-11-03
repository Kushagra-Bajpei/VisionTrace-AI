"""
Pydantic schemas for Camera streams and metadata.
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CameraBase(BaseModel):
    name: str
    location: Optional[str] = None
    rtsp_url: Optional[str] = None
    status: str = "active"
    description: Optional[str] = None


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    rtsp_url: Optional[str] = None
    status: Optional[str] = None
    description: Optional[str] = None


class CameraResponse(CameraBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
