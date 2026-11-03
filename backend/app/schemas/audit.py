"""
Pydantic schemas for AuditLog responses and filtering.
"""
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_id: Optional[uuid.UUID] = None
    actor_email: Optional[str] = None
    action: str
    target_type: str
    target_id: Optional[str] = None
    outcome: str
    client_ip: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime
