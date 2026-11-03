"""
Video Library API router.
Provides endpoints for video upload, metadata inspection, streaming, thumbnail delivery,
and cryptographic integrity verification with RBAC and scoped media delivery.
"""
import uuid
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import (
    get_current_user,
    require_investigator_or_admin,
    validate_media_request,
)
from app.core.config import get_settings
from app.core.database import get_db
from app.models.event import Event
from app.models.track import Track
from app.models.user import User
from app.models.video import Video
from app.schemas.event import EventResponse
from app.schemas.track import TrackDetailResponse, TrackResponse
from app.schemas.video import ExtractedFrameInfo, VideoResponse
from app.services.audit_service import AuditService
from app.services.integrity_service import IntegrityService
from app.services.tracking_service import tracking_service
from app.services.video_service import video_service
from app.tasks.video_tasks import enqueue_video_processing

settings = get_settings()
router = APIRouter()


@router.post(
    "/upload",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload CCTV video footage",
)
async def upload_video(
    request: Request,
    file: UploadFile = File(..., description="CCTV video file (MP4, MOV, or AVI up to 500MB)"),
    camera_id: Optional[uuid.UUID] = Form(None, description="Optional associated camera UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_investigator_or_admin),
):
    """
    Upload CCTV surveillance video:
    1. Validates extension, MIME type, file size, and decodable video header.
    2. Streams chunked upload to storage with safe UUID-based filename.
    3. Extracts technical metadata (resolution, fps, duration, frame count, codec).
    4. Generates representative JPEG thumbnail.
    5. Computes byte-level SHA-256 evidence integrity hash.
    6. Logs security audit entry.
    """
    # 1. Stream file to disk & validate content
    unique_name, file_path, relative_file_path, file_size = await video_service.save_upload(file)

    # 2. Extract technical metadata via OpenCV
    meta = video_service.extract_metadata(file_path)

    # 3. Generate thumbnail
    thumb_name = f"thumb_{Path(unique_name).stem}.jpg"
    thumb_path, relative_thumb_path = video_service.generate_thumbnail(
        file_path, thumb_name, target_time_sec=1.0
    )

    # 4. Create database record with status='uploaded'
    video = Video(
        camera_id=camera_id,
        filename=unique_name,
        original_filename=file.filename or unique_name,
        file_path=relative_file_path,
        file_size=file_size,
        duration=meta.get("duration"),
        width=meta.get("width"),
        height=meta.get("height"),
        fps=meta.get("fps"),
        status="uploaded",
        thumbnail_path=relative_thumb_path,
        uploaded_by=current_user.id,
        video_metadata={
            "frame_count": meta.get("frame_count"),
            "codec": meta.get("codec"),
            "format": Path(file.filename or "").suffix.lstrip(".").lower(),
        },
    )

    try:
        db.add(video)
        db.commit()
        db.refresh(video)
    except Exception as exc:
        db.rollback()
        video_service.delete_files(unique_name, relative_thumb_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database transaction failed: {str(exc)}",
        )

    # 5. Record SHA-256 cryptographic integrity hash
    IntegrityService.record_video_hash(db, video)

    # 6. Audit logging
    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="video_upload",
        target_type="video",
        target_id=video.id,
        outcome="success",
        client_ip=client_ip,
        details={
            "filename": video.filename,
            "original_filename": video.original_filename,
            "file_size": file_size,
            "file_hash": video.file_hash,
        },
    )

    # 7. Enqueue background processing with Redis/Celery (non-blocking)
    enqueue_video_processing(video.id, db)
    db.refresh(video)

    return video


@router.get(
    "",
    response_model=List[VideoResponse],
    summary="List all uploaded videos with filtering, search, and pagination",
)
def list_videos(
    search: Optional[str] = Query(None, description="Search by original filename"),
    status: Optional[str] = Query(None, description="Filter by status (uploaded, processing, completed, failed)"),
    camera_id: Optional[uuid.UUID] = Query(None, description="Filter by camera ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    sort_by: str = Query("created_at_desc", description="Sort order: created_at_desc, created_at_asc, duration_desc"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve paginated CCTV videos matching query filters."""
    query = select(Video)

    if search:
        query = query.where(Video.original_filename.ilike(f"%{search.strip()}%"))

    if status and status.lower() != "all":
        query = query.where(Video.status == status.lower())

    if camera_id:
        query = query.where(Video.camera_id == camera_id)

    if sort_by == "created_at_asc":
        query = query.order_by(Video.created_at.asc())
    elif sort_by == "duration_desc":
        query = query.order_by(Video.duration.desc().nullslast())
    else:
        query = query.order_by(Video.created_at.desc())

    query = query.offset(skip).limit(limit)
    return db.execute(query).scalars().all()


@router.get(
    "/stats/summary",
    summary="Get aggregated video repository metrics",
)
def get_video_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return total count, total duration, processing count, and total storage size."""
    total_videos = db.scalar(select(func.count(Video.id))) or 0
    total_duration = db.scalar(select(func.sum(Video.duration))) or 0.0
    total_size_bytes = db.scalar(select(func.sum(Video.file_size))) or 0
    uploaded_count = db.scalar(
        select(func.count(Video.id)).where(Video.status == "uploaded")
    ) or 0
    processing_count = db.scalar(
        select(func.count(Video.id)).where(Video.status.in_(["processing", "queued"]))
    ) or 0
    completed_count = db.scalar(
        select(func.count(Video.id)).where(Video.status == "completed")
    ) or 0

    return {
        "total_videos": total_videos,
        "total_duration_seconds": round(float(total_duration), 2),
        "total_size_bytes": total_size_bytes,
        "uploaded_count": uploaded_count,
        "processing_count": processing_count,
        "completed_count": completed_count,
    }


@router.get(
    "/{video_id}",
    response_model=VideoResponse,
    summary="Get detailed video record by ID",
)
def get_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full video metadata."""
    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )
    return video


@router.get(
    "/{video_id}/stream",
    summary="Stream video footage with HTTP Range 206 support",
)
def stream_video(
    video_id: uuid.UUID,
    request: Request,
    range: Optional[str] = Header(None),
    media_token: Optional[str] = Query(None, description="Short-lived scoped media token"),
    authorization: Optional[str] = Header(None, description="Standard Bearer token"),
    db: Session = Depends(get_db),
):
    """
    Streams video footage directly to HTML5 video players.
    Supports HTTP Range requests for seeking and fast scrubbing.
    Guarded by dual authentication (Bearer or scoped media token).
    """
    validate_media_request(
        resource_type="video",
        resource_id=video_id,
        request=request,
        media_token=media_token,
        authorization=authorization,
        db=db,
    )

    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    response = video_service.get_stream_response(video.file_path, range)
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@router.get(
    "/{video_id}/thumbnail",
    summary="Retrieve video frame thumbnail image",
)
def get_video_thumbnail(
    video_id: uuid.UUID,
    request: Request,
    media_token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Serve the generated thumbnail image with path traversal guards and optional media validation."""
    if authorization or media_token:
        validate_media_request(
            resource_type="video",
            resource_id=video_id,
            request=request,
            media_token=media_token,
            authorization=authorization,
            db=db,
        )

    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video or not video.thumbnail_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thumbnail not available for this video",
        )

    thumb_name = Path(video.thumbnail_path).name
    thumb_file = video_service.resolve_safe_path(video_service.thumbnails_dir, thumb_name)

    if not thumb_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thumbnail image file not found on disk",
        )

    return FileResponse(
        thumb_file,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400", "Referrer-Policy": "no-referrer"},
    )


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete video file, thumbnails, and associated records",
)
def delete_video(
    video_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_investigator_or_admin),
):
    """
    Safely delete video record and remove associated files from storage.
    Enforces ownership: Admins can delete any video; Investigators can delete their own uploads.
    """
    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    if current_user.role != "admin" and video.uploaded_by is not None and video.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to delete this video asset",
        )

    video_name = video.filename
    video_service.delete_files(video.filename, video.thumbnail_path, video_id=str(video.id))
    db.delete(video)
    db.commit()

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="video_delete",
        target_type="video",
        target_id=video_id,
        outcome="success",
        client_ip=client_ip,
        details={"filename": video_name},
    )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{video_id}/process",
    response_model=VideoResponse,
    summary="Enqueue or retry background video processing",
)
def process_video_endpoint(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_investigator_or_admin),
):
    """
    Manually enqueue or retry frame extraction processing for a video.
    Safe against concurrent duplicate execution.
    """
    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    success, err_msg = enqueue_video_processing(video.id, db)
    db.refresh(video)

    if not success and video.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=err_msg or "Failed to enqueue video processing task",
        )

    return video


@router.get(
    "/{video_id}/frames",
    response_model=List[ExtractedFrameInfo],
    summary="List extracted video frames with timestamps and preview URLs",
)
def list_video_frames(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns the list of all extracted frames for the given video ID.
    Frames are sampled deterministically at frame_extraction_fps (default 1/sec).
    """
    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    frames = video_service.get_extracted_frames(str(video.id))
    return frames


@router.get(
    "/{video_id}/frames/{frame_filename}",
    summary="Serve an extracted keyframe JPEG image",
)
def get_extracted_frame_file(
    video_id: uuid.UUID,
    frame_filename: str,
    request: Request,
    media_token: Optional[str] = Query(None, description="Short-lived scoped media token"),
    authorization: Optional[str] = Header(None, description="Standard Bearer token"),
    db: Session = Depends(get_db),
):
    """
    Serves a specific extracted frame image file.
    Validates that the file exists and is strictly confined to the video's frames directory.
    Guarded by dual authentication.
    """
    validate_media_request(
        resource_type="frame",
        resource_id=video_id,
        request=request,
        media_token=media_token,
        authorization=authorization,
        db=db,
    )

    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    video_frames_dir = video_service.resolve_safe_path(
        video_service.frames_dir, str(video.id)
    )
    frame_path = video_service.resolve_safe_path(video_frames_dir, frame_filename)

    if not frame_path.exists() or not frame_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame '{frame_filename}' not found for video '{video_id}'",
        )

    return FileResponse(
        frame_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400", "Referrer-Policy": "no-referrer"},
    )


@router.get(
    "/{video_id}/crops/{crop_filename}",
    summary="Serve a high-resolution cropped detection JPEG image",
)
def get_cropped_detection_image(
    video_id: uuid.UUID,
    crop_filename: str,
    request: Request,
    media_token: Optional[str] = Query(None, description="Short-lived scoped media token"),
    authorization: Optional[str] = Header(None, description="Standard Bearer token"),
    db: Session = Depends(get_db),
):
    """
    Serves a cropped detection thumbnail for visual similarity review.
    Guarded by dual authentication and path confinement.
    """
    validate_media_request(
        resource_type="crop",
        resource_id=video_id,
        request=request,
        media_token=media_token,
        authorization=authorization,
        db=db,
    )

    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    clean_name = Path(crop_filename).name
    video_crops_dir = video_service.resolve_safe_path(settings.crops_dir, str(video.id))
    crop_path = video_service.resolve_safe_path(video_crops_dir, clean_name)

    if crop_path.exists() and crop_path.is_file():
        return FileResponse(
            crop_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400", "Referrer-Policy": "no-referrer"},
        )

    # On-demand extraction using event ID if filename is <event_id>.jpg
    event_id_str = clean_name.replace(".jpg", "").replace(".jpeg", "")
    try:
        ev_uuid = uuid.UUID(event_id_str)
        event = db.scalar(select(Event).where(Event.id == ev_uuid, Event.video_id == video_id))
        if event and event.frame_path and event.bounding_box:
            f_path = Path(event.frame_path)
            if not f_path.exists():
                f_path = (settings.storage_base / event.frame_path.replace("storage/", "")).resolve()
            if f_path.exists():
                from app.services.embedding_service import embedding_service
                crop_arr = embedding_service.extract_crop(f_path, event.bounding_box, output_path=crop_path)
                if crop_arr is not None and crop_path.exists():
                    return FileResponse(
                        crop_path,
                        media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=86400", "Referrer-Policy": "no-referrer"},
                    )
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Crop '{crop_filename}' not found for video '{video_id}'",
    )


# ── Detection & Multi-Object Tracking Endpoints (Phase 4B) ───────────────────


@router.get(
    "/{video_id}/detections",
    response_model=List[EventResponse],
    summary="List all YOLO object detection events for a video",
)
def get_video_detections(
    video_id: uuid.UUID,
    class_name: Optional[str] = Query(None, description="Filter by detected class name"),
    min_confidence: Optional[float] = Query(None, description="Minimum detection confidence (0.0 - 1.0)"),
    track_id: Optional[uuid.UUID] = Query(None, description="Filter by continuous track UUID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all surveillance object detection events with bounding boxes,
    confidences, timestamps, and associated track references.
    """
    video = db.scalar(select(Video.id).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    stmt = select(Event).where(
        Event.video_id == video_id,
        Event.event_type == "object_detection",
    )

    if track_id:
        stmt = stmt.where(Event.track_id == track_id)
    if min_confidence is not None:
        stmt = stmt.where(Event.confidence >= min_confidence)

    stmt = stmt.order_by(Event.timestamp.asc())
    events = db.scalars(stmt).all()

    if class_name:
        target = class_name.lower().strip()
        events = [
            e for e in events
            if (e.attributes and e.attributes.get("class_name", "").lower() == target)
            or target in e.description.lower()
        ]

    return events


@router.get(
    "/{video_id}/tracks",
    response_model=List[TrackResponse],
    summary="List continuous ByteTrack object tracks for a video",
)
def get_video_tracks(
    video_id: uuid.UUID,
    object_class: Optional[str] = Query(None, description="Filter tracks by object class"),
    min_confidence: Optional[float] = Query(None, description="Filter tracks by minimum average confidence"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns all continuous object tracks identified by ByteTrack across video frames.
    Includes first/last seen timestamps, total detections count, and average confidence.
    """
    video = db.scalar(select(Video.id).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    stmt = select(Track).where(Track.video_id == video_id)

    if object_class:
        stmt = stmt.where(Track.object_class == object_class.lower().strip())
    if min_confidence is not None:
        stmt = stmt.where(Track.confidence_avg >= min_confidence)

    stmt = stmt.order_by(Track.start_time.asc(), Track.track_id.asc())
    tracks = db.scalars(stmt).all()
    return tracks


@router.get(
    "/{video_id}/tracks/{track_id}",
    response_model=TrackDetailResponse,
    summary="Get single object track details with chronological detections",
)
def get_track_detail(
    video_id: uuid.UUID,
    track_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves full track metadata and all chronological detection events belonging to this track.
    """
    track = db.scalar(
        select(Track).where(Track.id == track_id, Track.video_id == video_id)
    )
    if not track:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Track '{track_id}' not found for video '{video_id}'",
        )

    events = db.scalars(
        select(Event)
        .where(Event.track_id == track.id)
        .order_by(Event.timestamp.asc())
    ).all()

    return TrackDetailResponse(
        id=track.id,
        video_id=track.video_id,
        track_id=track.track_id,
        object_class=track.object_class,
        start_time=track.start_time,
        end_time=track.end_time,
        start_frame=track.start_frame,
        end_frame=track.end_frame,
        confidence_avg=track.confidence_avg,
        attributes=track.attributes,
        created_at=track.created_at,
        updated_at=track.updated_at,
        events=events,
    )


@router.get(
    "/{video_id}/frames/{frame_filename}/annotated",
    summary="Serve frame JPEG with rendered tactical surveillance bounding boxes",
)
def get_annotated_frame_image(
    video_id: uuid.UUID,
    frame_filename: str,
    request: Request,
    media_token: Optional[str] = Query(None, description="Short-lived scoped media token"),
    authorization: Optional[str] = Header(None, description="Standard Bearer token"),
    db: Session = Depends(get_db),
):
    """
    Renders bounding boxes, track labels, and confidence metrics on an extracted keyframe.
    Guarded by dual authentication.
    """
    validate_media_request(
        resource_type="frame",
        resource_id=video_id,
        request=request,
        media_token=media_token,
        authorization=authorization,
        db=db,
    )

    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    video_frames_dir = video_service.resolve_safe_path(
        video_service.frames_dir, str(video.id)
    )
    frame_path = video_service.resolve_safe_path(video_frames_dir, frame_filename)

    if not frame_path.exists() or not frame_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frame '{frame_filename}' not found for video '{video_id}'",
        )

    rel_path = f"frames/{video.id}/{frame_filename}"
    events = db.scalars(
        select(Event).where(
            Event.video_id == video.id,
            (Event.frame_path == rel_path) | (Event.frame_path.like(f"%{frame_filename}")),
        )
    ).all()

    detections_data = [
        {
            "bounding_box": ev.bounding_box,
            "confidence": ev.confidence,
            "class_name": (ev.attributes or {}).get("class_name") or ev.description,
            "attributes": ev.attributes or {},
        }
        for ev in events
    ]

    annotated_bytes = tracking_service.render_annotated_frame(frame_path, detections_data)
    if annotated_bytes is None:
        return FileResponse(
            frame_path,
            media_type="image/jpeg",
            headers={"Referrer-Policy": "no-referrer"},
        )

    return Response(
        content=annotated_bytes,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=3600", "Referrer-Policy": "no-referrer"},
    )


# ── Video Integrity Verification Endpoint ───────────────────────────────────


@router.post(
    "/{video_id}/verify-integrity",
    summary="Cryptographically verify SHA-256 integrity of source video file",
)
def verify_video_integrity(
    video_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Verifies stored byte-level SHA-256 hash of the video against actual disk storage.
    Logs audit event and returns verification status.
    """
    video = db.scalar(select(Video).where(Video.id == video_id))
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video '{video_id}' not found",
        )

    result = IntegrityService.verify_video_integrity(db, video_id)

    client_ip = request.client.host if request.client else None
    AuditService.log(
        db,
        actor=current_user,
        action="video_integrity_verify",
        target_type="video",
        target_id=video_id,
        outcome="success" if result["status"] == "verified" else "warning",
        client_ip=client_ip,
        details={
            "integrity_status": result["status"],
            "hash_algorithm": result.get("hash_algorithm"),
        },
    )

    return result
