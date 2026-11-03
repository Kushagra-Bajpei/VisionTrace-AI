"""
Pydantic schemas for multimodal embeddings.
"""
import uuid
from datetime import datetime
from typing import List
from pydantic import BaseModel, ConfigDict


class EmbeddingBase(BaseModel):
    event_id: uuid.UUID
    video_id: uuid.UUID
    embedding_type: str = "clip_visual"
    model_name: str = "openai/clip-vit-base-patch32"


class EmbeddingCreate(EmbeddingBase):
    embedding: List[float]


class EmbeddingResponse(EmbeddingBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
