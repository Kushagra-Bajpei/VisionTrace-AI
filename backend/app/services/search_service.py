"""
Search service – Natural Language & Visual Similarity CCTV Search.
Translates conversational surveillance queries into structured database queries over
videos, tracks, and detection events, with CLIP vision-language visual similarity ranking.
Guarantees that all returned results are grounded strictly in persisted database records.
"""
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.event import Event
from app.models.track import Track
from app.models.video import Video
from app.services.embedding_service import embedding_service
from app.services.video_service import video_service

logger = logging.getLogger(__name__)
settings = get_settings()

# Standard surveillance target vocabulary (COCO classes supported by YOLOv8)
SURVEILLANCE_CLASSES: Dict[str, str] = {
    # Person & clothing / accessories
    "person": "person",
    "people": "person",
    "pedestrian": "person",
    "pedestrians": "person",
    "human": "person",
    "humans": "person",
    "man": "person",
    "woman": "person",
    "individual": "person",
    "crowd": "person",
    # Vehicles
    "car": "car",
    "cars": "car",
    "vehicle": "car",
    "vehicles": "car",
    "automobile": "car",
    "truck": "truck",
    "trucks": "truck",
    "bus": "bus",
    "buses": "bus",
    "motorcycle": "motorcycle",
    "motorcycles": "motorcycle",
    "motorbike": "motorcycle",
    "bike": "bicycle",
    "bicycle": "bicycle",
    "bicycles": "bicycle",
    "airplane": "airplane",
    "plane": "airplane",
    "boat": "boat",
    # Objects & Electronics
    "backpack": "backpack",
    "bag": "backpack",
    "handbag": "handbag",
    "suitcase": "suitcase",
    "luggage": "suitcase",
    "laptop": "laptop",
    "computer": "laptop",
    "cell phone": "cell phone",
    "phone": "cell phone",
    "mobile": "cell phone",
    "book": "book",
    "bottle": "bottle",
    "cup": "cup",
    # Animals
    "dog": "dog",
    "cat": "cat",
    "bird": "bird",
    "horse": "horse",
}

VISUAL_COLOR_TOKENS = {
    "red", "blue", "green", "yellow", "black", "white", "gray", "grey",
    "orange", "purple", "pink", "brown", "dark", "light", "bright", "silver"
}

VISUAL_CLOTHING_TOKENS = {
    "shirt", "t-shirt", "jacket", "coat", "hoodie", "sweater", "pants",
    "jeans", "shorts", "dress", "skirt", "suit", "uniform", "hat", "cap",
    "helmet", "shoes", "boots", "vest", "glasses", "sunglasses"
}

VISUAL_ATTRIBUTE_TOKENS = {
    "carrying", "holding", "wearing", "standing", "walking", "running",
    "sitting", "near", "beside", "entering", "leaving", "riding", "bag", "backpack"
}


@dataclass
class ParsedQuery:
    """Structured representation parsed from a natural language CCTV query."""
    raw_query: str
    target_classes: List[str] = field(default_factory=list)
    time_min: Optional[float] = None
    time_max: Optional[float] = None
    min_confidence: Optional[float] = None
    track_number: Optional[int] = None
    temporal_intent: str = "all"  # 'all', 'first_seen', 'last_seen', 'count_summary'
    video_id: Optional[uuid.UUID] = None
    visual_descriptors: List[str] = field(default_factory=list)
    is_visual_search: bool = False
    keywords: List[str] = field(default_factory=list)
    unsupported_facets: List[str] = field(default_factory=list)


def parse_timestamp_str(time_str: str) -> Optional[float]:
    """
    Parses MM:SS, M:SS, or seconds string into float seconds.
    Examples: '00:04' -> 4.0, '01:23' -> 83.0, '5s' -> 5.0, '12.5' -> 12.5
    """
    time_str = time_str.strip().lower().rstrip("s")
    if ":" in time_str:
        parts = time_str.split(":")
        try:
            if len(parts) == 2:
                mins = int(parts[0])
                secs = float(parts[1])
                return round(mins * 60 + secs, 2)
            elif len(parts) == 3:
                hrs = int(parts[0])
                mins = int(parts[1])
                secs = float(parts[2])
                return round(hrs * 3600 + mins * 60 + secs, 2)
        except ValueError:
            return None
    try:
        return round(float(time_str), 2)
    except ValueError:
        return None


class NaturalLanguageSearchEngine:
    """
    Deterministic rule-based query parsing & hybrid database + visual similarity search engine.
    Ensures 100% evidence-grounded search results with distinct visual ranking signals.
    """

    def parse_query(
        self,
        query: str,
        video_id: Optional[uuid.UUID] = None,
        override_class: Optional[str] = None,
        override_min_conf: Optional[float] = None,
        override_time_min: Optional[float] = None,
        override_time_max: Optional[float] = None,
        enable_visual_search: bool = True,
    ) -> ParsedQuery:
        """
        Parses natural language queries into structured search facets.
        Extracts:
        - Target object classes (person, car, truck, etc.)
        - Temporal bounds ('between 00:02 and 00:08', 'after 5s', 'before 10s')
        - Confidence thresholds ('above 80%', 'confidence > 0.7')
        - Specific track references ('track #2', 'track 1')
        - Temporal intent ('first seen', 'last seen', 'how many')
        - Visual descriptors ('red shirt', 'white car', 'carrying a bag')
        """
        q = query.strip()
        q_lower = q.lower()

        parsed = ParsedQuery(raw_query=q, video_id=video_id)

        # 1. Target Classes extraction
        found_classes: Set[str] = set()
        words = re.findall(r"\b[a-z-]+\b", q_lower)
        for w in words:
            if w in SURVEILLANCE_CLASSES:
                found_classes.add(SURVEILLANCE_CLASSES[w])

        # Multi-word classes check (e.g. 'cell phone')
        for phrase, canonical in SURVEILLANCE_CLASSES.items():
            if " " in phrase and phrase in q_lower:
                found_classes.add(canonical)

        if override_class:
            found_classes.add(override_class.lower().strip())

        parsed.target_classes = sorted(list(found_classes))

        # 2. Track Number extraction (e.g. 'track #2', 'track 1', 'id 5')
        track_match = re.search(r"\b(?:track|target|id)\s*#?\s*(\d+)\b", q_lower)
        if track_match:
            try:
                parsed.track_number = int(track_match.group(1))
            except ValueError:
                pass

        # 3. Confidence Threshold extraction (e.g. 'above 80%', '> 75%', 'conf 0.8')
        conf_match = re.search(r"(?:above|over|greater than|>=?|>)\s*(\d+(?:\.\d+)?)\s*(%|percent)?", q_lower)
        if conf_match:
            val = float(conf_match.group(1))
            is_pct = bool(conf_match.group(2)) or val > 1.0
            parsed.min_confidence = round(val / 100.0 if is_pct else val, 2)
        elif "confidence" in q_lower:
            conf_val_match = re.search(r"confidence\s*(?:of|above|>=?|>)?\s*(\d+(?:\.\d+)?)", q_lower)
            if conf_val_match:
                val = float(conf_val_match.group(1))
                parsed.min_confidence = round(val / 100.0 if val > 1.0 else val, 2)

        if override_min_conf is not None:
            parsed.min_confidence = override_min_conf

        # 4. Time Range extraction
        between_match = re.search(
            r"between\s+([\d:.]+s?)\s+and\s+([\d:.]+s?)",
            q_lower,
        )
        if between_match:
            t1 = parse_timestamp_str(between_match.group(1))
            t2 = parse_timestamp_str(between_match.group(2))
            if t1 is not None and t2 is not None:
                parsed.time_min = min(t1, t2)
                parsed.time_max = max(t1, t2)

        if parsed.time_min is None:
            from_to_match = re.search(r"from\s+([\d:.]+s?)\s+to\s+([\d:.]+s?)", q_lower)
            if from_to_match:
                t1 = parse_timestamp_str(from_to_match.group(1))
                t2 = parse_timestamp_str(from_to_match.group(2))
                if t1 is not None and t2 is not None:
                    parsed.time_min = min(t1, t2)
                    parsed.time_max = max(t1, t2)

        after_match = re.search(r"(?:after|since|from)\s+([\d:.]+s?)", q_lower)
        if after_match and parsed.time_min is None:
            t = parse_timestamp_str(after_match.group(1))
            if t is not None:
                parsed.time_min = t

        before_match = re.search(r"(?:before|until|prior to)\s+([\d:.]+s?)", q_lower)
        if before_match and parsed.time_max is None:
            t = parse_timestamp_str(before_match.group(1))
            if t is not None:
                parsed.time_max = t

        if override_time_min is not None:
            parsed.time_min = override_time_min
        if override_time_max is not None:
            parsed.time_max = override_time_max

        # 5. Temporal Intent
        if any(term in q_lower for term in ["last seen", "latest", "most recent", "when did .* leave", "end of"]):
            parsed.temporal_intent = "last_seen"
        elif any(term in q_lower for term in ["first seen", "earliest", "initial", "when did .* enter", "start of"]):
            parsed.temporal_intent = "first_seen"
        elif any(term in q_lower for term in ["how many", "count", "total number"]):
            parsed.temporal_intent = "count_summary"
        else:
            parsed.temporal_intent = "all"

        # 6. Visual Similarity Descriptors extraction
        visual_descriptors = []
        for word in words:
            if word in VISUAL_COLOR_TOKENS:
                visual_descriptors.append(f"color:{word}")
            elif word in VISUAL_CLOTHING_TOKENS:
                visual_descriptors.append(f"clothing:{word}")
            elif word in VISUAL_ATTRIBUTE_TOKENS:
                visual_descriptors.append(f"attribute:{word}")

        # Check multi-word visual phrases
        color_object_pattern = re.findall(
            r"\b(red|blue|green|yellow|black|white|dark|bright)\s+([a-z]+)\b",
            q_lower,
        )
        for color, item in color_object_pattern:
            visual_descriptors.append(f"{color} {item}")

        parsed.visual_descriptors = visual_descriptors
        if enable_visual_search and (len(visual_descriptors) > 0 or len(q.split()) >= 3):
            parsed.is_visual_search = True

        # 7. Unsupported Facets (Biometrics, Speed Radar, ALPR, verified attributes)
        unsupported_keywords = [
            ("red|blue|black|white|yellow|green|color", "color-based visual filtering (ranking signal only)"),
            ("face|facial identity|identity verification|john|sarah|name", "facial recognition"),
            ("license plate|number plate|alpr", "automated license plate recognition (ALPR)"),
            ("speed|fast|running|velocity", "velocity/speed estimation"),
            ("weapon|gun|firearm|knife|pistol", "specialized weapon detection"),
        ]
        for pattern, facet_name in unsupported_keywords:
            if re.search(rf"\b(?:{pattern})\b", q_lower):
                parsed.unsupported_facets.append(facet_name)

        return parsed

    def search(
        self,
        db: Session,
        parsed: ParsedQuery,
        visual_search: bool = True,
        min_visual_similarity: Optional[float] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Executes a multi-tier database query against tracks, events, and videos
        using structured facets, enhanced with CLIP visual similarity ranking.
        """
        # Tier 1: Query matching Tracks
        track_stmt = select(Track)
        if parsed.video_id:
            track_stmt = track_stmt.where(Track.video_id == parsed.video_id)

        if parsed.target_classes:
            track_stmt = track_stmt.where(Track.object_class.in_(parsed.target_classes))

        if parsed.track_number is not None:
            track_stmt = track_stmt.where(Track.track_id == parsed.track_number)

        if parsed.min_confidence is not None:
            track_stmt = track_stmt.where(Track.confidence_avg >= parsed.min_confidence)

        if parsed.time_min is not None:
            track_stmt = track_stmt.where(Track.end_time >= parsed.time_min)

        if parsed.time_max is not None:
            track_stmt = track_stmt.where(Track.start_time <= parsed.time_max)

        track_stmt = track_stmt.order_by(Track.start_time.asc())
        matched_tracks: List[Track] = db.scalars(track_stmt).all()

        # Tier 2: Query matching Detections (Events)
        event_stmt = select(Event).where(Event.event_type == "object_detection")
        if parsed.video_id:
            event_stmt = event_stmt.where(Event.video_id == parsed.video_id)

        if parsed.track_number is not None and matched_tracks:
            track_ids = [t.id for t in matched_tracks]
            event_stmt = event_stmt.where(Event.track_id.in_(track_ids))

        if parsed.min_confidence is not None:
            event_stmt = event_stmt.where(Event.confidence >= parsed.min_confidence)

        if parsed.time_min is not None:
            event_stmt = event_stmt.where(Event.timestamp >= parsed.time_min)

        if parsed.time_max is not None:
            event_stmt = event_stmt.where(Event.timestamp <= parsed.time_max)

        event_stmt = event_stmt.order_by(Event.timestamp.asc())
        raw_events: List[Event] = db.scalars(event_stmt).all()

        # Filter events by target class (from attributes or description)
        matched_events: List[Event] = []
        if parsed.target_classes:
            target_set = set(parsed.target_classes)
            for ev in raw_events:
                ev_class = (ev.attributes or {}).get("class_name", "").lower()
                if not ev_class:
                    for c in target_set:
                        if c in ev.description.lower():
                            ev_class = c
                            break
                if ev_class in target_set:
                    matched_events.append(ev)
        else:
            matched_events = raw_events

        # ── Visual Similarity Ranking (Phase 6) ──────────────────────────────
        sim_scores_map: Dict[uuid.UUID, float] = {}
        crop_paths_map: Dict[uuid.UUID, Optional[str]] = {}
        is_visual_ranked = False

        threshold = min_visual_similarity if min_visual_similarity is not None else 0.15

        if visual_search and (parsed.is_visual_search or parsed.visual_descriptors):
            try:
                candidate_ids = [e.id for e in matched_events]
                ranked_items = embedding_service.rank_events_by_similarity(
                    db=db,
                    query_text=parsed.raw_query,
                    video_id=parsed.video_id,
                    candidate_event_ids=candidate_ids if candidate_ids else None,
                    min_similarity=threshold,
                    limit=limit * 2,
                )
                if ranked_items:
                    for ev_id, score, c_path in ranked_items:
                        sim_scores_map[ev_id] = score
                        crop_paths_map[ev_id] = c_path
                    is_visual_ranked = True

                    # Sort detections primarily by visual similarity descending
                    matched_events.sort(
                        key=lambda e: (sim_scores_map.get(e.id, 0.0), e.confidence),
                        reverse=True,
                    )
            except Exception as rank_exc:
                logger.warning("Visual similarity ranking failed: %s", rank_exc)

        # Handle temporal intents if visual ranking was not active
        if not is_visual_ranked:
            if parsed.temporal_intent == "last_seen" and matched_events:
                matched_events = sorted(matched_events, key=lambda e: e.timestamp, reverse=True)
                matched_tracks = sorted(matched_tracks, key=lambda t: t.end_time, reverse=True)
            elif parsed.temporal_intent == "first_seen" and matched_events:
                matched_events = sorted(matched_events, key=lambda e: e.timestamp, reverse=False)
                matched_tracks = sorted(matched_tracks, key=lambda t: t.start_time, reverse=False)

        # Tier 3: Fetch referenced Videos
        video_ids_set = set()
        for t in matched_tracks:
            video_ids_set.add(t.video_id)
        for e in matched_events:
            video_ids_set.add(e.video_id)

        videos_map: Dict[uuid.UUID, Video] = {}
        if video_ids_set:
            videos_stmt = select(Video).where(Video.id.in_(list(video_ids_set)))
            vids = db.scalars(videos_stmt).all()
            videos_map = {v.id: v for v in vids}

        # Apply pagination to detections
        total_detections = len(matched_events)
        paginated_events = matched_events[offset : offset + limit]

        # Tier 4: Construct Grounded Evidence Summary
        summary = self._generate_evidence_summary(
            parsed=parsed,
            tracks=matched_tracks,
            detections=matched_events,
            videos=videos_map,
            is_visual_ranked=is_visual_ranked,
        )

        # Build serialized matches
        serialized_tracks = [
            {
                "id": str(t.id),
                "video_id": str(t.video_id),
                "video_name": videos_map.get(t.video_id).original_filename if videos_map.get(t.video_id) else "Unknown Video",
                "track_id": t.track_id,
                "object_class": t.object_class,
                "start_time": t.start_time,
                "end_time": t.end_time,
                "start_frame": t.start_frame,
                "end_frame": t.end_frame,
                "confidence_avg": round(t.confidence_avg, 3),
                "detection_count": (t.attributes or {}).get("detection_count") or 1,
                "trajectory": (t.attributes or {}).get("trajectory", []),
            }
            for t in matched_tracks
        ]

        serialized_detections = []
        for e in paginated_events:
            frame_filename = Path(e.frame_path).name if e.frame_path else None
            annotated_url = f"/api/v1/videos/{e.video_id}/frames/{frame_filename}/annotated" if frame_filename else None
            crop_url = f"/api/v1/videos/{e.video_id}/crops/{e.id}.jpg"
            sim_score = sim_scores_map.get(e.id)

            # Sanitize internal filesystem paths - only expose relative safe paths
            safe_frame_path = f"frames/{e.video_id}/{frame_filename}" if frame_filename else None

            serialized_detections.append(
                {
                    "id": str(e.id),
                    "video_id": str(e.video_id),
                    "video_name": videos_map.get(e.video_id).original_filename if videos_map.get(e.video_id) else "Unknown Video",
                    "track_id": str(e.track_id) if e.track_id else None,
                    "track_number": (e.attributes or {}).get("track_number"),
                    "timestamp": e.timestamp,
                    "object_class": (e.attributes or {}).get("class_name") or e.description,
                    "confidence": round(e.confidence, 3),
                    "visual_similarity_score": sim_score,
                    "bounding_box": e.bounding_box,
                    "frame_path": safe_frame_path,
                    "annotated_frame_url": annotated_url,
                    "crop_image_url": crop_url,
                    "is_visual_match": sim_score is not None,
                }
            )

        serialized_videos = [
            {
                "id": str(v.id),
                "original_filename": v.original_filename,
                "duration": v.duration,
                "fps": v.fps,
                "resolution": f"{v.width}x{v.height}" if v.width and v.height else None,
                "thumbnail_url": f"/api/v1/videos/{v.id}/thumbnail" if v.thumbnail_path else None,
                "matching_tracks_count": len([t for t in matched_tracks if t.video_id == v.id]),
                "matching_detections_count": len([e for e in matched_events if e.video_id == v.id]),
            }
            for v in videos_map.values()
        ]

        search_mode = "hybrid" if is_visual_ranked else "deterministic_facets"

        return {
            "query": parsed.raw_query,
            "search_mode": search_mode,
            "parsed_facets": {
                "target_classes": parsed.target_classes,
                "min_confidence": parsed.min_confidence,
                "time_min": parsed.time_min,
                "time_max": parsed.time_max,
                "track_number": parsed.track_number,
                "temporal_intent": parsed.temporal_intent,
                "visual_descriptors": parsed.visual_descriptors,
                "is_visual_search": parsed.is_visual_search,
                "unsupported_facets": parsed.unsupported_facets,
            },
            "total_matches": total_detections,
            "total_tracks": len(matched_tracks),
            "evidence_summary": summary,
            "videos": serialized_videos,
            "tracks": serialized_tracks,
            "detections": serialized_detections,
            "offset": offset,
            "limit": limit,
        }

    def _generate_evidence_summary(
        self,
        parsed: ParsedQuery,
        tracks: List[Track],
        detections: List[Event],
        videos: Dict[uuid.UUID, Video],
        is_visual_ranked: bool = False,
    ) -> str:
        """
        Synthesizes a strictly factual summary grounded solely in retrieved database records.
        Distinguishes visual similarity ranking signals from detector confidence.
        """
        if not tracks and not detections:
            classes_str = ", ".join(f"'{c}'" for c in parsed.target_classes) if parsed.target_classes else "specified targets"
            bounds = []
            if parsed.time_min is not None or parsed.time_max is not None:
                bounds.append(f"in time window [{parsed.time_min or 0.0}s - {parsed.time_max or 'end'}s]")
            if parsed.min_confidence is not None:
                bounds.append(f"with confidence >= {int(parsed.min_confidence * 100)}%")
            bounds_str = f" ({', '.join(bounds)})" if bounds else ""
            return f"No verified detection records found for {classes_str}{bounds_str} in the ingested surveillance footage."

        parts = []

        classes_str = ", ".join(f"'{c}'" for c in parsed.target_classes) if parsed.target_classes else "target objects"

        if is_visual_ranked:
            parts.append(
                f"Visual similarity search matched {len(detections)} detection event(s) and {len(tracks)} track(s) for query '{parsed.raw_query}', ranked by CLIP visual cosine similarity. (Visual Similarity is a ranking score, not a verified attribute or facial identification)."
            )
        elif parsed.temporal_intent == "last_seen" and detections:
            latest = detections[0]
            v_name = videos.get(latest.video_id).original_filename if videos.get(latest.video_id) else "footage"
            trk_num = (latest.attributes or {}).get("track_number")
            trk_str = f" (Track #{trk_num})" if trk_num else ""
            c_name = (latest.attributes or {}).get("class_name") or classes_str
            parts.append(
                f"{c_name.capitalize()}{trk_str} was last observed at timestamp {latest.timestamp:.1f}s with {int(latest.confidence * 100)}% detector confidence in '{v_name}'."
            )
        elif parsed.temporal_intent == "first_seen" and detections:
            earliest = detections[0]
            v_name = videos.get(earliest.video_id).original_filename if videos.get(earliest.video_id) else "footage"
            trk_num = (earliest.attributes or {}).get("track_number")
            trk_str = f" (Track #{trk_num})" if trk_num else ""
            c_name = (earliest.attributes or {}).get("class_name") or classes_str
            parts.append(
                f"{c_name.capitalize()}{trk_str} was first observed at timestamp {earliest.timestamp:.1f}s with {int(earliest.confidence * 100)}% detector confidence in '{v_name}'."
            )
        else:
            parts.append(
                f"Identified {len(tracks)} continuous object tracks and {len(detections)} detection events for {classes_str} across {len(videos)} video asset(s)."
            )

        if tracks:
            top_tracks = sorted(
                tracks,
                key=lambda t: (len(t.attributes.get("trajectory", []) if t.attributes else []), t.confidence_avg),
                reverse=True,
            )[:3]
            track_descs = [
                f"Track #{t.track_id} ({t.object_class}) visible {t.start_time:.1f}s-{t.end_time:.1f}s (detector conf: {int(t.confidence_avg * 100)}%)"
                for t in top_tracks
            ]
            parts.append("Key tracks: " + "; ".join(track_descs) + ".")

        if parsed.unsupported_facets:
            facets_str = ", ".join(parsed.unsupported_facets)
            parts.append(f"Note: Query contained {facets_str}, which is outside surveillance computer vision models and was filtered out.")

        return " ".join(parts)


search_engine = NaturalLanguageSearchEngine()
