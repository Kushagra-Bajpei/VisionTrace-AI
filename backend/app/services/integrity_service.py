"""
VisionTrace AI – Evidence Integrity Service (Phase 8).
Computes and verifies cryptographic SHA-256 hashes of video files,
extracted frames, detection crops, and finalized PDF reports.
"""
import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.investigation import InvestigationEvidence
from app.models.report import Report
from app.models.video import Video

logger = logging.getLogger(__name__)
settings = get_settings()

CHUNK_SIZE = 64 * 1024  # 64KB chunks for memory-safe streaming hashing


def compute_file_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash from raw file bytes in 64KB chunks."""
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            hasher.update(chunk)
    return hasher.hexdigest()


class IntegrityService:
    """Manages computation, recording, and verification of evidence SHA-256 hashes."""

    @classmethod
    def record_video_hash(cls, db: Session, video: Video) -> Optional[str]:
        """Computes and records SHA-256 hash for an uploaded video file."""
        video_path = Path(video.file_path)
        if not video_path.is_file():
            video_path = settings.storage_base / video.file_path
        if not video_path.is_file():
            video_path = settings.videos_dir / video.filename

        if not video_path.is_file():
            logger.warning("Cannot compute video hash; file not found on disk: %s", video.file_path)
            return None

        sha256_hash = compute_file_sha256(video_path)
        video.file_hash = sha256_hash
        video.hash_algorithm = "sha256"
        video.hashed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(video)
        return sha256_hash

    @classmethod
    def record_evidence_hash(cls, db: Session, evidence: InvestigationEvidence) -> Optional[str]:
        """Computes and records SHA-256 hash for an evidence crop or frame file."""
        target_path = None
        if evidence.crop_path:
            p = settings.storage_base / evidence.crop_path
            if p.is_file():
                target_path = p
            elif (settings.crops_dir / Path(evidence.crop_path).name).is_file():
                target_path = settings.crops_dir / Path(evidence.crop_path).name

        if not target_path and evidence.frame_path:
            p = settings.storage_base / evidence.frame_path
            if p.is_file():
                target_path = p
            elif (settings.frames_dir / str(evidence.video_id) / Path(evidence.frame_path).name).is_file():
                target_path = settings.frames_dir / str(evidence.video_id) / Path(evidence.frame_path).name

        if not target_path or not target_path.is_file():
            logger.warning("Evidence file not found on disk for evidence %s", evidence.id)
            return None

        sha256_hash = compute_file_sha256(target_path)
        evidence.evidence_hash = sha256_hash
        evidence.hash_algorithm = "sha256"
        evidence.hashed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(evidence)
        return sha256_hash

    @classmethod
    def record_report_hash(cls, db: Session, report: Report) -> Optional[str]:
        """Computes and records SHA-256 hash for a finalized PDF report."""
        if not report.pdf_path:
            return None

        p = settings.storage_base / report.pdf_path
        if not p.is_file():
            # Fallback
            p = settings.reports_dir / str(report.investigation_id) / Path(report.pdf_path).name

        if not p.is_file():
            logger.warning("Report PDF file not found on disk for report %s", report.id)
            return None

        sha256_hash = compute_file_sha256(p)
        report.pdf_hash = sha256_hash
        report.hash_algorithm = "sha256"
        report.hashed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(report)
        return sha256_hash

    @classmethod
    def verify_file(
        cls,
        file_path: Optional[Path],
        expected_hash: Optional[str],
    ) -> Dict[str, Any]:
        """
        Verifies actual file bytes against stored hash.
        Outcomes:
        - 'not_recorded': No hash recorded in database for this legacy item.
        - 'unavailable': Target file missing from disk storage.
        - 'verified': File exists and SHA-256 matches stored hash exactly.
        - 'mismatch': File exists, but SHA-256 differs (possible tampering/corruption).
        """
        if not expected_hash:
            return {
                "status": "not_recorded",
                "expected_hash": None,
                "computed_hash": None,
                "verified": False,
                "details": "No cryptographic hash was recorded for this legacy record.",
            }

        if not file_path or not file_path.is_file():
            return {
                "status": "unavailable",
                "expected_hash": expected_hash,
                "computed_hash": None,
                "verified": False,
                "details": "Referenced media file is missing from server storage.",
            }

        try:
            current_hash = compute_file_sha256(file_path)
            if current_hash.lower() == expected_hash.lower():
                return {
                    "status": "verified",
                    "expected_hash": expected_hash,
                    "computed_hash": current_hash,
                    "actual_hash": current_hash,
                    "verified": True,
                    "details": "Cryptographic SHA-256 checksum verified against stored record.",
                }
            else:
                return {
                    "status": "mismatch",
                    "expected_hash": expected_hash,
                    "computed_hash": current_hash,
                    "actual_hash": current_hash,
                    "verified": False,
                    "details": "Checksum mismatch detected! Stored hash differs from file content.",
                }
        except Exception as e:
            return {
                "status": "unavailable",
                "expected_hash": expected_hash,
                "computed_hash": None,
                "verified": False,
                "details": f"Error computing checksum: {str(e)}",
            }

    @classmethod
    def verify_evidence(cls, db: Session, evidence_id: uuid.UUID) -> Dict[str, Any]:
        """Verifies evidence item crop or frame checksum."""
        evidence = db.query(InvestigationEvidence).filter(InvestigationEvidence.id == evidence_id).first()
        if not evidence:
            raise ValueError(f"Evidence {evidence_id} not found.")

        target_path = None
        if evidence.crop_path:
            p = settings.storage_base / evidence.crop_path
            if p.is_file():
                target_path = p
            elif (settings.crops_dir / Path(evidence.crop_path).name).is_file():
                target_path = settings.crops_dir / Path(evidence.crop_path).name

        if not target_path and evidence.frame_path:
            p = settings.storage_base / evidence.frame_path
            if p.is_file():
                target_path = p
            elif (settings.frames_dir / str(evidence.video_id) / Path(evidence.frame_path).name).is_file():
                target_path = settings.frames_dir / str(evidence.video_id) / Path(evidence.frame_path).name

        result = cls.verify_file(target_path, evidence.evidence_hash)
        result["evidence_id"] = str(evidence_id)
        result["hash_algorithm"] = evidence.hash_algorithm or "sha256"
        result["hashed_at"] = evidence.hashed_at.isoformat() if evidence.hashed_at else None
        return result

    @classmethod
    def verify_report(cls, db: Session, report_id: uuid.UUID) -> Dict[str, Any]:
        """Verifies report PDF file checksum."""
        report = db.query(Report).filter(Report.id == report_id).first()
        if not report:
            raise ValueError(f"Report {report_id} not found.")

        target_path = None
        if report.pdf_path:
            p = settings.storage_base / report.pdf_path
            if p.is_file():
                target_path = p
            elif (settings.reports_dir / str(report.investigation_id) / Path(report.pdf_path).name).is_file():
                target_path = settings.reports_dir / str(report.investigation_id) / Path(report.pdf_path).name

        result = cls.verify_file(target_path, report.pdf_hash)
        result["report_id"] = str(report_id)
        result["hash_algorithm"] = report.hash_algorithm or "sha256"
        result["hashed_at"] = report.hashed_at.isoformat() if report.hashed_at else None
        return result

    @classmethod
    def verify_video(cls, db: Session, video_id: uuid.UUID) -> Dict[str, Any]:
        """Verifies uploaded video file checksum."""
        video = db.query(Video).filter(Video.id == video_id).first()
        if not video:
            raise ValueError(f"Video {video_id} not found.")

        video_path = Path(video.file_path)
        if not video_path.is_file():
            video_path = settings.storage_base / video.file_path
        if not video_path.is_file():
            video_path = settings.videos_dir / video.filename

        result = cls.verify_file(video_path, video.file_hash)
        result["video_id"] = str(video_id)
        result["hash_algorithm"] = video.hash_algorithm or "sha256"
        result["hashed_at"] = video.hashed_at.isoformat() if video.hashed_at else None
        return result

    # Aliases for router convenience
    verify_video_integrity = verify_video
    verify_evidence_integrity = verify_evidence
    verify_report_integrity = verify_report
