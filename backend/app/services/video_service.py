"""
Video storage and metadata extraction service using OpenCV.
Handles chunked streaming uploads, content validation, metadata extraction,
thumbnail generation, path traversal prevention, and HTTP Range streaming.
"""
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

import cv2
from fastapi import HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.core.config import get_settings

settings = get_settings()

ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi"}
ALLOWED_MIME_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/avi",
    "application/octet-stream",  # Fallback for generic binary uploads
}


class VideoService:
    def __init__(self):
        self.videos_dir = settings.videos_dir
        self.thumbnails_dir = settings.thumbnails_dir
        self.temp_dir = settings.temp_dir
        self.frames_dir = settings.frames_dir

        # Ensure all storage directories exist
        for d in (self.videos_dir, self.thumbnails_dir, self.temp_dir, self.frames_dir):
            d.mkdir(parents=True, exist_ok=True)

    def resolve_safe_path(self, base_dir: Path, target: str) -> Path:
        """
        Prevents path traversal attacks by resolving and verifying that
        the target path strictly resides within the expected base directory.
        """
        # Strip leading slashes to prevent root-relative override
        clean_target = target.lstrip("/\\")
        candidate = (base_dir / clean_target).resolve()
        base_resolved = base_dir.resolve()

        try:
            candidate.relative_to(base_resolved)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Security violation: Path traversal detected.",
            )
        return candidate

    def validate_file(self, filename: Optional[str], content_type: Optional[str] = None):
        """Validate filename, extension, and content type."""
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename must not be empty.",
            )

        # Basic path traversal guard on the original filename
        if ".." in filename or "/" in filename or "\\" in filename:
            # Clean basename is accepted for metadata, but extension check must be strict
            filename = Path(filename).name

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported video format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
            )

        if content_type and content_type.lower() not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported MIME type '{content_type}'.",
            )

    def validate_video_content(self, video_path: Path):
        """
        Inspects actual video file header using OpenCV.
        Rejects corrupted or non-video files early.
        """
        cap = cv2.VideoCapture(str(video_path))
        try:
            if not cap.isOpened():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupted or unreadable video file header.",
                )
            # Verify at least one frame is readable
            ret, frame = cap.read()
            if not ret or frame is None or frame.size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Corrupted video stream: No decodable video frames found.",
                )
        finally:
            cap.release()

    async def save_upload(self, file: UploadFile) -> Tuple[str, Path, str, int]:
        """
        Stream uploaded file in 1MB chunks to disk while verifying size limits.
        Returns (unique_filename, absolute_path, relative_path, total_bytes).
        """
        self.validate_file(file.filename, file.content_type)

        ext = Path(file.filename or "").suffix.lower()
        unique_name = f"{uuid.uuid4().hex}{ext}"
        destination = self.resolve_safe_path(self.videos_dir, unique_name)
        relative_path = f"videos/{unique_name}"

        total_bytes = 0
        chunk_size = 1024 * 1024  # 1 MB

        try:
            with open(destination, "wb") as out_file:
                while content := await file.read(chunk_size):
                    total_bytes += len(content)
                    if total_bytes > settings.max_upload_bytes:
                        out_file.close()
                        if destination.exists():
                            destination.unlink()
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"File exceeds maximum allowed size of {settings.max_upload_size_mb} MB",
                        )
                    out_file.write(content)
        except Exception as exc:
            if destination.exists():
                destination.unlink()
            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to write uploaded video file: {str(exc)}",
            )

        # Validate actual content
        try:
            self.validate_video_content(destination)
        except Exception as exc:
            if destination.exists():
                destination.unlink()
            raise exc

        return unique_name, destination, relative_path, total_bytes

    def extract_metadata(self, video_path: Path) -> Dict[str, Optional[float]]:
        """
        Uses OpenCV VideoCapture to read technical properties:
        width, height, fps, frame_count, duration, and codec.
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return {
                "width": None,
                "height": None,
                "fps": None,
                "duration": None,
                "frame_count": None,
                "codec": None,
            }

        try:
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = float(cap.get(cv2.CAP_PROP_FPS))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
            codec = None
            if fourcc_int > 0:
                try:
                    codec = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)]).strip()
                except Exception:
                    codec = None

            duration = None
            if fps and fps > 0 and frame_count and frame_count > 0:
                duration = round(frame_count / fps, 2)

            return {
                "width": width if width > 0 else None,
                "height": height if height > 0 else None,
                "fps": round(fps, 2) if (fps and fps > 0) else None,
                "duration": duration,
                "frame_count": frame_count if (frame_count and frame_count > 0) else None,
                "codec": codec,
            }
        finally:
            cap.release()

    def generate_thumbnail(
        self, video_path: Path, thumbnail_filename: str, target_time_sec: float = 1.0
    ) -> Tuple[Optional[Path], Optional[str]]:
        """
        Extracts a clean video frame around target_time_sec and saves as JPEG thumbnail.
        Returns (thumbnail_absolute_path, thumbnail_relative_path).
        """
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None, None

        thumb_dest = self.resolve_safe_path(self.thumbnails_dir, thumbnail_filename)
        rel_path = f"thumbnails/{thumbnail_filename}"

        try:
            fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            target_frame = int(fps * target_time_sec)
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

            success, frame = cap.read()
            if not success or frame is None:
                # Fallback to the first available frame
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = cap.read()

            if success and frame is not None:
                cv2.imwrite(str(thumb_dest), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                return thumb_dest, rel_path
            return None, None
        except Exception:
            return None, None
        finally:
            cap.release()

    def delete_files(
        self,
        filename: str,
        thumbnail_path: Optional[str] = None,
        video_id: Optional[str] = None,
    ):
        """Safely delete video, thumbnail, and extracted frames directory from disk."""
        try:
            video_path = self.resolve_safe_path(self.videos_dir, filename)
            if video_path.exists():
                video_path.unlink()
        except Exception:
            pass

        if thumbnail_path:
            try:
                thumb_name = Path(thumbnail_path).name
                thumb_file = self.resolve_safe_path(self.thumbnails_dir, thumb_name)
                if thumb_file.exists():
                    thumb_file.unlink()
            except Exception:
                pass

        if video_id:
            try:
                frames_dir = self.resolve_safe_path(self.frames_dir, str(video_id))
                if frames_dir.exists():
                    shutil.rmtree(frames_dir)
            except Exception:
                pass

    def extract_frames(
        self,
        video_path: Path,
        video_id: str,
        target_fps: float = 1.0,
        progress_callback: Optional[Callable[[float], None]] = None,
        should_cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Extracts sampled video frames at target_fps (default 1.0 frame per second)
        and saves them under storage/frames/{video_id}/frame_{index:06d}.jpg.
        Does not load the whole video into memory.
        Returns (extracted_count, list of frame_dicts).
        """
        dest_dir = self.resolve_safe_path(self.frames_dir, str(video_id))
        dest_dir.mkdir(parents=True, exist_ok=True)

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise RuntimeError(f"Cannot open video file: {video_path}")

        extracted_frames: List[Dict[str, Any]] = []
        try:
            native_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            duration_sec = (
                total_frames / native_fps if (native_fps > 0 and total_frames > 0) else 0.0
            )

            # Target interval: sample 1 frame every interval_sec seconds
            interval_sec = 1.0 / target_fps if target_fps > 0 else 1.0

            # Pre-compute target sample timestamps: t = 0.0, 1.0, 2.0, ... up to duration_sec
            timestamps: List[float] = []
            curr_t = 0.0
            max_t = duration_sec if duration_sec > 0 else 1.0
            while curr_t <= max_t:
                timestamps.append(round(curr_t, 3))
                curr_t += interval_sec

            total_samples = max(1, len(timestamps))

            for idx, t_sec in enumerate(timestamps):
                # Check cancellation / deletion during processing
                if should_cancel_callback and should_cancel_callback():
                    return idx, extracted_frames

                target_frame_num = int(round(t_sec * native_fps))
                cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame_num)
                success, frame = cap.read()
                if not success or frame is None:
                    break

                frame_name = f"frame_{idx:06d}.jpg"
                frame_path = dest_dir / frame_name
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])

                rel_path = f"frames/{video_id}/{frame_name}"
                extracted_frames.append(
                    {
                        "index": idx,
                        "timestamp_seconds": t_sec,
                        "filename": frame_name,
                        "path": rel_path,
                    }
                )

                if progress_callback:
                    # Allocate 0% -> 95% for frame extraction; remaining 5% for metadata commit
                    pct = round(min(95.0, ((idx + 1) / total_samples) * 95.0), 1)
                    progress_callback(pct)

            return len(extracted_frames), extracted_frames
        finally:
            cap.release()

    def get_extracted_frames(self, video_id: str) -> List[Dict[str, Any]]:
        """List all extracted keyframes for a video sorted deterministically."""
        dest_dir = self.resolve_safe_path(self.frames_dir, str(video_id))
        if not dest_dir.exists():
            return []

        frames: List[Dict[str, Any]] = []
        for p in sorted(dest_dir.glob("frame_*.jpg")):
            try:
                idx = int(p.stem.split("_")[1])
                t_sec = float(idx) * (1.0 / settings.frame_extraction_fps)
                frames.append(
                    {
                        "index": idx,
                        "timestamp_seconds": round(t_sec, 2),
                        "filename": p.name,
                        "preview_url": f"/api/v1/videos/{video_id}/frames/{p.name}",
                    }
                )
            except Exception:
                continue
        return frames

    def get_stream_response(self, file_path_str: str, range_header: Optional[str]) -> Response:
        """
        Handles HTTP 206 Partial Content video streaming for smooth playback and seeking.
        Prevents path traversal and checks file existence.
        """
        # Resolve path safely inside videos directory
        filename = Path(file_path_str).name
        video_path = self.resolve_safe_path(self.videos_dir, filename)

        if not video_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video file not found on storage server",
            )

        file_size = video_path.stat().st_size
        ext = video_path.suffix.lower()
        content_type = "video/mp4"
        if ext == ".mov":
            content_type = "video/quicktime"
        elif ext == ".avi":
            content_type = "video/x-msvideo"

        # Determine start and end byte positions
        start = 0
        end = file_size - 1

        if range_header:
            range_str = range_header.replace("bytes=", "").strip()
            parts = range_str.split("-")
            if parts[0]:
                start = int(parts[0])
            if len(parts) > 1 and parts[1]:
                end = int(parts[1])

        # Clamp boundaries
        start = max(0, min(start, file_size - 1))
        end = max(start, min(end, file_size - 1))
        content_length = (end - start) + 1

        def chunk_generator() -> Generator[bytes, None, None]:
            chunk_size = 512 * 1024  # 512 KB
            bytes_left = content_length
            with open(video_path, "rb") as f:
                f.seek(start)
                while bytes_left > 0:
                    read_len = min(chunk_size, bytes_left)
                    data = f.read(read_len)
                    if not data:
                        break
                    bytes_left -= len(data)
                    yield data

        headers = {
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(content_length),
            "Content-Type": content_type,
        }

        status_code = status.HTTP_206_PARTIAL_CONTENT if range_header else status.HTTP_200_OK
        return StreamingResponse(
            chunk_generator(),
            status_code=status_code,
            headers=headers,
            media_type=content_type,
        )


video_service = VideoService()
