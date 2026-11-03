"""
Natural Language & Visual Similarity CCTV Search Router.
Provides structured natural language query processing over surveillance footage,
backed by verified database tracks and detection events, with CLIP visual similarity ranking.
"""
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.search import (
    SearchQueryRequest,
    SearchQueryResponse,
    SearchSuggestion,
)
from app.services.search_service import search_engine

router = APIRouter()


@router.post(
    "/query",
    response_model=SearchQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute natural language surveillance search",
)
def execute_natural_language_search(
    payload: SearchQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Parses a natural language query into structured facets (target class, time window,
    confidence threshold, track number, and visual descriptors), executes an evidence query
    across videos, tracks, and detection events, and returns a verified factual summary
    with exact bounding boxes, timestamps, and CLIP visual similarity ranking.
    """
    parsed = search_engine.parse_query(
        query=payload.query,
        video_id=payload.video_id,
        override_class=payload.object_class,
        override_min_conf=payload.min_confidence,
        override_time_min=payload.time_min,
        override_time_max=payload.time_max,
        enable_visual_search=payload.visual_search,
    )

    result = search_engine.search(
        db=db,
        parsed=parsed,
        visual_search=payload.visual_search,
        min_visual_similarity=payload.min_visual_similarity,
        limit=payload.limit,
        offset=payload.offset,
    )

    return result


@router.get(
    "/quick",
    response_model=SearchQueryResponse,
    summary="Fast GET endpoint for natural language queries",
)
def quick_search(
    q: str = Query(..., min_length=1, max_length=500, description="Natural language search query"),
    video_id: Optional[uuid.UUID] = Query(None, description="Optional video asset UUID"),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    time_min: Optional[float] = Query(None, ge=0.0),
    time_max: Optional[float] = Query(None, ge=0.0),
    visual_search: bool = Query(True, description="Enable CLIP visual similarity ranking"),
    min_visual_similarity: Optional[float] = Query(None, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lightweight GET version of the natural language search endpoint."""
    parsed = search_engine.parse_query(
        query=q,
        video_id=video_id,
        override_min_conf=min_confidence,
        override_time_min=time_min,
        override_time_max=time_max,
        enable_visual_search=visual_search,
    )

    result = search_engine.search(
        db=db,
        parsed=parsed,
        visual_search=visual_search,
        min_visual_similarity=min_visual_similarity,
        limit=limit,
        offset=offset,
    )

    return result


@router.get(
    "/suggestions",
    response_model=List[SearchSuggestion],
    summary="Retrieve standard surveillance investigation query templates",
)
def get_search_suggestions(
    current_user: User = Depends(get_current_user),
):
    """Returns curated operator query templates categorized by investigation goal."""
    return [
        SearchSuggestion(
            query="Find all people detected in this video",
            description="Locates all pedestrian tracks across footage",
            category="Target Discovery",
        ),
        SearchSuggestion(
            query="Person wearing a dark jacket",
            description="CLIP visual similarity search for specific clothing appearance",
            category="Visual Description",
        ),
        SearchSuggestion(
            query="White vehicle near the entrance",
            description="Visual color and object correlation across surveillance tracks",
            category="Visual Description",
        ),
        SearchSuggestion(
            query="Someone carrying a bag or backpack",
            description="Visual search for pedestrians carrying luggage or accessories",
            category="Visual Description",
        ),
        SearchSuggestion(
            query="Show me cars visible between 00:00 and 00:05",
            description="Filters vehicular targets within an exact time window",
            category="Temporal Window",
        ),
        SearchSuggestion(
            query="When was a person last seen?",
            description="Determines the final confirmed detection timestamp of a human target",
            category="Forensic Timeline",
        ),
        SearchSuggestion(
            query="Show tracks with confidence above 80%",
            description="Filters high-confidence confirmed identities",
            category="Quality Assurance",
        ),
        SearchSuggestion(
            query="Find all objects for Track #2",
            description="Inspects the full chronological trajectory for a specific ByteTrack ID",
            category="Track Inspection",
        ),
        SearchSuggestion(
            query="Find videos containing a person",
            description="Cross-video asset search for specific object presence",
            category="Asset Search",
        ),
    ]
