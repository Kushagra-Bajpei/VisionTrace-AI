"""
Tracking service – YOLO object detection and ByteTrack multi-object tracking.
Integrates Ultralytics YOLO with ByteTrack to detect surveillance targets,
track persistent identities across frames, and persist structured events & tracks.
"""
import logging
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.event import Event
from app.models.track import Track
from app.models.video import Video

logger = logging.getLogger(__name__)
settings = get_settings()

# Ensure Ultralytics writes temp configs safely inside the project storage directory
_ultralytics_temp = settings.storage_base / "temp" / "ultralytics"
_ultralytics_temp.mkdir(parents=True, exist_ok=True)
os.environ["YOLO_CONFIG_DIR"] = str(_ultralytics_temp)


@dataclass
class DetectionItem:
    """Single detected bounding box inside a frame."""
    frame_index: int
    timestamp: float
    frame_path: str
    class_id: int
    class_name: str
    confidence: float
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    track_number: Optional[int] = None


@dataclass
class TrackSummary:
    """Aggregated continuous object track across sequential frames."""
    track_number: int
    object_class: str
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    confidences: List[float] = field(default_factory=list)
    trajectory: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def confidence_avg(self) -> float:
        if not self.confidences:
            return 0.0
        return float(np.mean(self.confidences))


class TrackingService:
    """
    Surveillance object detection & multi-object tracking engine.
    Encapsulates YOLO inference and ByteTrack state maintenance.
    """

    def __init__(self):
        self._model = None
        self._model_path: Optional[Path] = None

    def get_model(self):
        """
        Lazily loads the YOLO model weights.
        Thread-safe within each worker process.
        """
        if self._model is not None:
            return self._model

        from ultralytics import YOLO

        model_name = settings.yolo_model_name
        local_model_path = settings.models_path / model_name

        if local_model_path.exists():
            load_target = str(local_model_path)
            logger.info("Loading YOLO model from local storage: %s", load_target)
        else:
            load_target = model_name
            logger.info("Loading YOLO model via Ultralytics identifier: %s", load_target)

        try:
            model = YOLO(load_target)
            self._model = model
            self._model_path = Path(load_target)
            return self._model
        except Exception as exc:
            logger.error("Failed to load YOLO model '%s': %s", load_target, exc)
            raise RuntimeError(f"YOLO model load failure: {exc}") from exc

    def detect_and_track_frames(
        self,
        video_id: uuid.UUID,
        frame_records: List[Dict[str, Any]],
        conf_threshold: Optional[float] = None,
        progress_callback: Optional[Callable[[float], None]] = None,
        should_cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> Tuple[List[DetectionItem], List[TrackSummary]]:
        """
        Runs YOLO object detection and ByteTrack tracking sequentially across extracted frames.
        Frames must be chronologically ordered.
        
        Returns:
            Tuple of (all_detections, aggregated_tracks)
        """
        model = self.get_model()
        threshold = conf_threshold if conf_threshold is not None else settings.yolo_confidence_threshold
        tracker_cfg = settings.yolo_tracker_config

        total_frames = len(frame_records)
        all_detections: List[DetectionItem] = []
        tracks_map: Dict[int, TrackSummary] = {}
        untracked_counter = 900000  # Fallback counter for detections without persistent track ID

        logger.info(
            "Starting YOLO + ByteTrack tracking on %d frames for video %s (conf >= %.2f)",
            total_frames,
            video_id,
            threshold,
        )

        for idx, rec in enumerate(frame_records):
            if should_cancel_callback and should_cancel_callback():
                logger.info("Tracking cancelled for video %s at frame %d", video_id, idx)
                break

            f_idx = rec["index"]
            f_time = rec.get("timestamp_seconds", rec.get("timestamp", 0.0))
            raw_p = rec.get("path") or rec.get("frame_path")
            if raw_p and not Path(raw_p).is_absolute():
                f_path = str((settings.storage_base / raw_p).resolve())
            else:
                f_path = str(raw_p)
            rel_path = rec.get("relative_path") or rec.get("path") or str(raw_p)

            # Run YOLO with ByteTrack persistence
            # persist=True retains tracks between consecutive frame calls in this sequence
            results = model.track(
                source=f_path,
                tracker=tracker_cfg,
                persist=True,
                conf=threshold,
                verbose=False,
            )

            if results and len(results) > 0:
                result = results[0]
                boxes = result.boxes

                if boxes is not None and len(boxes) > 0:
                    xyxyn = boxes.xyxyn.cpu().numpy()  # Normalized coordinates [x1, y1, x2, y2]
                    confs = boxes.conf.cpu().numpy()
                    classes = boxes.cls.cpu().numpy().astype(int)
                    track_ids = (
                        boxes.id.int().cpu().tolist()
                        if boxes.id is not None
                        else [None] * len(classes)
                    )

                    for i in range(len(classes)):
                        c_id = int(classes[i])
                        c_name = model.names.get(c_id, f"class_{c_id}")
                        conf = float(confs[i])
                        t_id = track_ids[i]
                        coords = xyxyn[i]

                        # Clamp normalized coordinates to [0.0, 1.0]
                        x1 = max(0.0, min(1.0, float(coords[0])))
                        y1 = max(0.0, min(1.0, float(coords[1])))
                        x2 = max(0.0, min(1.0, float(coords[2])))
                        y2 = max(0.0, min(1.0, float(coords[3])))

                        assigned_track_id = t_id
                        if assigned_track_id is None:
                            untracked_counter += 1
                            assigned_track_id = untracked_counter

                        det_item = DetectionItem(
                            frame_index=f_idx,
                            timestamp=f_time,
                            frame_path=rel_path,
                            class_id=c_id,
                            class_name=c_name,
                            confidence=round(conf, 4),
                            x_min=round(x1, 4),
                            y_min=round(y1, 4),
                            x_max=round(x2, 4),
                            y_max=round(y2, 4),
                            track_number=assigned_track_id,
                        )
                        all_detections.append(det_item)

                        # Maintain track aggregate
                        if assigned_track_id not in tracks_map:
                            tracks_map[assigned_track_id] = TrackSummary(
                                track_number=assigned_track_id,
                                object_class=c_name,
                                start_time=f_time,
                                end_time=f_time,
                                start_frame=f_idx,
                                end_frame=f_idx,
                                confidences=[conf],
                                trajectory=[
                                    {
                                        "timestamp": f_time,
                                        "frame_index": f_idx,
                                        "bbox": [x1, y1, x2, y2],
                                        "confidence": round(conf, 4),
                                    }
                                ],
                            )
                        else:
                            trk = tracks_map[assigned_track_id]
                            trk.end_time = max(trk.end_time, f_time)
                            trk.end_frame = max(trk.end_frame, f_idx)
                            trk.confidences.append(conf)
                            trk.trajectory.append(
                                {
                                    "timestamp": f_time,
                                    "frame_index": f_idx,
                                    "bbox": [x1, y1, x2, y2],
                                    "confidence": round(conf, 4),
                                }
                            )

            if progress_callback and total_frames > 0:
                pct = ((idx + 1) / total_frames) * 100.0
                progress_callback(pct)

        # Filter out tracks that only have 1 single detection if untracked counter was used,
        # but keep all ByteTrack-confirmed tracks.
        sorted_tracks = sorted(tracks_map.values(), key=lambda t: (t.start_time, t.track_number))
        return all_detections, sorted_tracks

    def persist_tracking_results(
        self,
        db: Session,
        video_id: uuid.UUID,
        detections: List[DetectionItem],
        tracks: List[TrackSummary],
    ) -> Dict[str, Any]:
        """
        Persists detection events and continuous tracks into the existing
        'events' and 'tracks' database tables with proper foreign key relationships.
        Updates video metadata with detection and track counts.
        """
        # Clean any prior tracks/events for this video if reprocessing
        db.execute(delete(Event).where(Event.video_id == video_id))
        db.execute(delete(Track).where(Track.video_id == video_id))

        # 1. Create Track entities
        track_orm_map: Dict[int, Track] = {}
        for trk_summary in tracks:
            track_orm = Track(
                video_id=video_id,
                track_id=trk_summary.track_number,
                object_class=trk_summary.object_class,
                start_time=round(trk_summary.start_time, 2),
                end_time=round(trk_summary.end_time, 2),
                start_frame=trk_summary.start_frame,
                end_frame=trk_summary.end_frame,
                confidence_avg=round(trk_summary.confidence_avg, 4),
                attributes={
                    "detection_count": len(trk_summary.confidences),
                    "trajectory": trk_summary.trajectory,
                },
            )
            db.add(track_orm)
            track_orm_map[trk_summary.track_number] = track_orm

        db.flush()  # Flush to generate UUIDs for tracks

        # 2. Create Event entities linked to Track UUIDs
        unique_classes = set()
        for det in detections:
            unique_classes.add(det.class_name)
            linked_track = track_orm_map.get(det.track_number) if det.track_number else None
            track_db_id = linked_track.id if linked_track else None

            event_orm = Event(
                video_id=video_id,
                track_id=track_db_id,
                timestamp=round(det.timestamp, 2),
                event_type="object_detection",
                description=f"Detected {det.class_name} (conf: {det.confidence:.2f})",
                confidence=det.confidence,
                bounding_box={
                    "x_min": det.x_min,
                    "y_min": det.y_min,
                    "x_max": det.x_max,
                    "y_max": det.y_max,
                    "box_format": "xyxyn",
                },
                frame_path=det.frame_path,
                attributes={
                    "class_name": det.class_name,
                    "class_id": det.class_id,
                    "frame_index": det.frame_index,
                    "track_number": det.track_number,
                },
            )
            db.add(event_orm)

        # 3. Update video metadata summary
        video = db.scalar(select(Video).where(Video.id == video_id))
        if video:
            meta = dict(video.video_metadata or {})
            meta.update({
                "detections_count": len(detections),
                "tracks_count": len(tracks),
                "detected_classes": sorted(list(unique_classes)),
                "yolo_model": settings.yolo_model_name,
                "tracker": settings.yolo_tracker_config,
            })
            video.video_metadata = meta

        db.commit()

        logger.info(
            "Persisted %d detections and %d tracks for video %s. Classes: %s",
            len(detections),
            len(tracks),
            video_id,
            sorted(list(unique_classes)),
        )

        return {
            "detections_count": len(detections),
            "tracks_count": len(tracks),
            "detected_classes": sorted(list(unique_classes)),
        }

    def render_annotated_frame(
        self,
        image_path: Path,
        detections: List[Dict[str, Any]],
    ) -> Optional[bytes]:
        """
        Renders tactical surveillance bounding boxes and label badges onto a keyframe image.
        Returns JPEG encoded bytes.
        """
        if not image_path.exists():
            return None

        img = cv2.imread(str(image_path))
        if img is None:
            return None

        h, w, _ = img.shape

        # Distinct palette for tactical surveillance
        # Primary Cyan BGR: (255, 229, 0), Accent Emerald BGR: (80, 230, 100), Amber: (50, 180, 255)
        color_map = {
            "person": (255, 229, 0),      # Cyan
            "car": (80, 230, 100),        # Emerald
            "truck": (50, 180, 255),      # Amber
            "bus": (255, 120, 50),        # Blue/Indigo
            "motorcycle": (200, 100, 255),# Violet
            "bicycle": (100, 220, 255),   # Light Orange
            "laptop": (255, 200, 100),    # Teal
        }
        default_color = (255, 229, 0)

        for det in detections:
            bbox = det.get("bounding_box") or {}
            x_min = int(bbox.get("x_min", 0.0) * w)
            y_min = int(bbox.get("y_min", 0.0) * h)
            x_max = int(bbox.get("x_max", 0.0) * w)
            y_max = int(bbox.get("y_max", 0.0) * h)

            class_name = det.get("attributes", {}).get("class_name") or det.get("class_name") or "object"
            conf = det.get("confidence", 0.0)
            track_num = det.get("attributes", {}).get("track_number")
            color = color_map.get(class_name.lower(), default_color)

            # Draw outer corner bounding box
            cv2.rectangle(img, (x_min, y_min), (x_max, y_max), color, 2)

            # Draw tactical corner accents
            corner_len = min(15, (x_max - x_min) // 4, (y_max - y_min) // 4)
            if corner_len > 3:
                cv2.line(img, (x_min, y_min), (x_min + corner_len, y_min), (255, 255, 255), 2)
                cv2.line(img, (x_min, y_min), (x_min, y_min + corner_len), (255, 255, 255), 2)
                cv2.line(img, (x_max, y_max), (x_max - corner_len, y_max), (255, 255, 255), 2)
                cv2.line(img, (x_max, y_max), (x_max, y_max - corner_len), (255, 255, 255), 2)

            # Label badge
            label = f"{class_name.upper()}"
            if track_num is not None and track_num < 900000:
                label += f" #{track_num}"
            label += f" {int(conf * 100)}%"

            (lw, lh), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            badge_y1 = max(0, y_min - lh - 8)
            badge_y2 = y_min

            # Dark translucent backing for the label
            cv2.rectangle(
                img,
                (x_min, badge_y1),
                (x_min + lw + 8, badge_y2),
                (12, 16, 24),
                cv2.FILLED,
            )
            cv2.rectangle(
                img,
                (x_min, badge_y1),
                (x_min + lw + 8, badge_y2),
                color,
                1,
            )
            cv2.putText(
                img,
                label,
                (x_min + 4, y_min - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.45,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        success, encoded = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])
        if not success:
            return None
        return encoded.tobytes()


tracking_service = TrackingService()
