"""
Pydantic schemas for User authentication, profiles, role updates, and token responses.
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    role: str = "investigator"
    is_active: bool = True


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Minimum 8 characters")


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class BootstrapAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    full_name: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserRoleUpdateRequest(BaseModel):
    role: str = Field(..., description="Role: admin, investigator, reviewer, or viewer")
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class MediaTokenRequest(BaseModel):
    resource_type: str = Field(..., description="video, frame, crop, or report")
    resource_id: str = Field(..., description="Target file or entity identifier")


class MediaTokenResponse(BaseModel):
    media_token: str
    token_type: str = "media"
    expires_in: int = 120
    resource_type: str
    resource_id: str
