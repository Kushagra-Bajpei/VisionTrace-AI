"""
Pydantic schemas for Natural Language & Visual Similarity CCTV Search.
"""
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class SearchQueryRequest(BaseModel):
    """Investigation natural language search request."""
    query: str = Field(..., min_length=1, max_length=500, description="Conversational or keyword search query")
    video_id: Optional[uuid.UUID] = Field(None, description="Optional filter to a specific video asset")
    object_class: Optional[str] = Field(None, description="Explicit override filter for target class")
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum detector confidence threshold")
    time_min: Optional[float] = Field(None, ge=0.0, description="Earliest timestamp in seconds")
    time_max: Optional[float] = Field(None, ge=0.0, description="Latest timestamp in seconds")
    visual_search: bool = Field(True, description="Enable CLIP visual similarity ranking for visual descriptions")
    min_visual_similarity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum visual similarity ranking score (0.0 - 1.0)")
    limit: int = Field(50, ge=1, le=200, description="Maximum number of detection events to return")
    offset: int = Field(0, ge=0, description="Pagination offset")


class ParsedFacetsResponse(BaseModel):
    """Structured facets parsed from natural language query."""
    target_classes: List[str] = []
    min_confidence: Optional[float] = None
    time_min: Optional[float] = None
    time_max: Optional[float] = None
    track_number: Optional[int] = None
    temporal_intent: str = "all"
    visual_descriptors: List[str] = []
    is_visual_search: bool = False
    unsupported_facets: List[str] = []


class SearchTrackMatch(BaseModel):
    """Matching continuous object track."""
    id: str
    video_id: str
    video_name: str
    track_id: int
    object_class: str
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    confidence_avg: float
    detection_count: int
    trajectory: List[Dict[str, Any]] = []


class SearchDetectionMatch(BaseModel):
    """Matching verified detection event with optional visual similarity score."""
    id: str
    video_id: str
    video_name: str
    track_id: Optional[str] = None
    track_number: Optional[int] = None
    timestamp: float
    object_class: str
    confidence: float
    visual_similarity_score: Optional[float] = None
    bounding_box: Optional[Dict[str, Any]] = None
    frame_path: Optional[str] = None
    annotated_frame_url: Optional[str] = None
    crop_image_url: Optional[str] = None
    is_visual_match: bool = False


class SearchVideoMatch(BaseModel):
    """Video asset containing matched targets."""
    id: str
    original_filename: str
    duration: Optional[float] = None
    fps: Optional[float] = None
    resolution: Optional[str] = None
    thumbnail_url: Optional[str] = None
    matching_tracks_count: int
    matching_detections_count: int


class SearchQueryResponse(BaseModel):
    """Comprehensive natural language search response with evidence grounding."""
    query: str
    search_mode: str = "hybrid"
    parsed_facets: ParsedFacetsResponse
    total_matches: int
    total_tracks: int
    evidence_summary: str
    videos: List[SearchVideoMatch] = []
    tracks: List[SearchTrackMatch] = []
    detections: List[SearchDetectionMatch] = []
    offset: int = 0
    limit: int = 50


class SearchSuggestion(BaseModel):
    """Pre-built surveillance search suggestion for quick investigator discovery."""
    query: str
    description: str
    category: str
