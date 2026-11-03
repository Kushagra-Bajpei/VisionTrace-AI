"""
Forensic Investigation PDF Report Generator Service.
Uses FPDF to construct printable, audit-grade surveillance investigation reports.
"""
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fpdf import FPDF
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.investigation import Investigation, InvestigationEvidence, InvestigationMessage
from app.models.report import Report
from app.models.video import Video

logger = logging.getLogger(__name__)
settings = get_settings()


def clean_text(text: Optional[str]) -> str:
    """
    Sanitize unicode strings to prevent Latin-1 encoding errors in FPDF.
    Replaces common typographic unicode glyphs with ASCII equivalents.
    """
    if not text:
        return ""
    replacements = {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "--",
        "\u2026": "...",
        "\u2022": "*",
        "\u00a0": " ",
        "\u25b6": ">",
        "\u25cf": "*",
    }
    for orig, repl in replacements.items():
        text = text.replace(orig, repl)
    # Filter any remaining non-latin1 characters
    return text.encode("latin-1", "replace").decode("latin-1")


def format_seconds(seconds: float) -> str:
    """Format seconds as MM:SS.SS"""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins:02d}:{secs:05.2f}"


class ForensicPDF(FPDF):
    """
    Customized FPDF template for VisionTrace AI forensic investigation reports.
    """

    def __init__(self, case_title: str, case_id: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.case_title = clean_text(case_title)
        self.case_id = str(case_id)
        self.set_auto_page_break(auto=True, margin=18)
        self.alias_nb_pages()

    def header(self):
        # Top banner
        self.set_fill_color(22, 27, 34)  # Dark charcoal header bar
        self.rect(0, 0, 210, 14, "F")

        # Cyan indicator stripe
        self.set_fill_color(0, 229, 255)  # Restrained cyan
        self.rect(0, 14, 210, 1.2, "F")

        self.set_xy(10, 4)
        self.set_font("Arial", "B", 8)
        self.set_text_color(255, 255, 255)
        self.cell(100, 6, "VISIONTRACE AI // EVIDENTIARY SURVEILLANCE DOSSIER", 0, 0, "L")

        self.set_font("Arial", "", 7)
        self.set_text_color(180, 190, 205)
        self.cell(90, 6, f"CASE REF: {self.case_id[:18]}...", 0, 1, "R")

        self.ln(6)

    def footer(self):
        self.set_y(-14)
        # Separator line
        self.set_draw_color(200, 205, 215)
        self.line(10, self.get_y(), 200, self.get_y())

        self.set_y(-11)
        self.set_font("Arial", "I", 7)
        self.set_text_color(100, 110, 120)
        self.cell(120, 6, "OFFICIAL LAW ENFORCEMENT & SECURITY AUDIT LOG | FOR AUTHORIZED USE ONLY", 0, 0, "L")
        self.cell(70, 6, f"Page {self.page_no()} of {{nb}}", 0, 0, "R")


class InvestigationReportService:
    """
    Constructs and persists comprehensive forensic investigation reports.
    """

    @classmethod
    def generate_report(
        cls,
        db: Session,
        investigation_id: uuid.UUID,
        title: Optional[str] = None,
        executive_summary: Optional[str] = None,
        include_evidence_thumbnails: bool = True,
        custom_notes: Optional[str] = None,
    ) -> Report:
        """
        Generate a forensic PDF report for an investigation and record it in the database.
        """
        investigation: Optional[Investigation] = db.query(Investigation).filter(
            Investigation.id == investigation_id
        ).first()

        if not investigation:
            raise ValueError(f"Investigation {investigation_id} not found.")

        # Gather evidence items ordered by sequence and timestamp
        evidence_items: List[InvestigationEvidence] = (
            db.query(InvestigationEvidence)
            .filter(InvestigationEvidence.investigation_id == investigation_id)
            .order_by(InvestigationEvidence.sequence_number.asc(), InvestigationEvidence.timestamp.asc())
            .all()
        )

        # Gather messages / log notes
        messages: List[InvestigationMessage] = (
            db.query(InvestigationMessage)
            .filter(InvestigationMessage.investigation_id == investigation_id)
            .order_by(InvestigationMessage.created_at.asc())
            .all()
        )

        report_title = clean_text(title or f"Forensic Case Report: {investigation.title}")
        exec_summary = clean_text(
            executive_summary
            or (
                f"Investigation dossier compiled for case '{investigation.title}'. "
                f"Contains {len(evidence_items)} recorded evidentiary items and "
                f"{len(messages)} chronologically recorded investigator observations. "
                f"Current case status is {investigation.status.upper()} with {investigation.priority.upper()} priority."
            )
        )

        # Initialize PDF
        pdf = ForensicPDF(case_title=investigation.title, case_id=str(investigation.id))
        pdf.add_page()

        # ── Document Title Block ──
        pdf.set_font("Arial", "B", 18)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 9, report_title, ln=1)

        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(100, 116, 139)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        pdf.cell(0, 5, f"Report Generated: {now_str} | System: VisionTrace AI v0.1.0", ln=1)
        pdf.ln(3)

        # ── Metadata Grid ──
        pdf.set_fill_color(245, 247, 250)
        pdf.set_draw_color(220, 226, 235)
        pdf.rect(10, pdf.get_y(), 190, 24, "FD")

        y_meta = pdf.get_y() + 2
        pdf.set_xy(14, y_meta)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(40, 5, "CASE IDENTIFIER", 0, 0)
        pdf.cell(40, 5, "STATUS", 0, 0)
        pdf.cell(40, 5, "PRIORITY", 0, 0)
        pdf.cell(50, 5, "EVIDENCE ITEMS", 0, 1)

        pdf.set_xy(14, y_meta + 5)
        pdf.set_font("Courier", "B", 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(40, 5, str(investigation.id)[:16] + "...", 0, 0)

        pdf.set_font("Arial", "B", 8)
        status_color = (
            (16, 185, 129) if investigation.status == "closed"
            else (245, 158, 11) if investigation.status == "in_progress"
            else (59, 130, 246)
        )
        pdf.set_text_color(*status_color)
        pdf.cell(40, 5, investigation.status.upper(), 0, 0)

        priority_color = (
            (239, 68, 68) if investigation.priority in ["high", "critical"]
            else (245, 158, 11) if investigation.priority == "medium"
            else (71, 85, 105)
        )
        pdf.set_text_color(*priority_color)
        pdf.cell(40, 5, investigation.priority.upper(), 0, 0)

        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(50, 5, f"{len(evidence_items)} Items Documented", 0, 1)

        # Row 2 of metadata
        pdf.set_xy(14, y_meta + 12)
        pdf.set_font("Arial", "B", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(40, 5, "CREATED AT", 0, 0)
        pdf.cell(40, 5, "LAST MODIFIED", 0, 0)
        pdf.cell(90, 5, "TAGS / CLASSIFICATION", 0, 1)

        pdf.set_xy(14, y_meta + 16)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(15, 23, 42)
        created_str = investigation.created_at.strftime("%Y-%m-%d %H:%M") if investigation.created_at else "N/A"
        updated_str = investigation.updated_at.strftime("%Y-%m-%d %H:%M") if investigation.updated_at else "N/A"
        tags_str = ", ".join(investigation.tags or []) if investigation.tags else "None"
        pdf.cell(40, 5, created_str, 0, 0)
        pdf.cell(40, 5, updated_str, 0, 0)
        pdf.cell(90, 5, clean_text(tags_str), 0, 1)

        pdf.set_y(y_meta + 25)

        # ── Executive Summary ──
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 7, "1. EXECUTIVE SUMMARY & INVESTIGATOR BRIEFING", ln=1)

        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(51, 65, 85)
        pdf.multi_cell(0, 5, exec_summary)
        pdf.ln(3)

        if custom_notes:
            pdf.set_font("Arial", "B", 9)
            pdf.set_text_color(71, 85, 105)
            pdf.cell(0, 5, "Investigator Addendum:", ln=1)
            pdf.set_font("Arial", "I", 9)
            pdf.set_text_color(51, 65, 85)
            pdf.multi_cell(0, 5, clean_text(custom_notes))
            pdf.ln(3)

        # ── Chronological Evidence Timeline ──
        pdf.ln(2)
        pdf.set_font("Arial", "B", 11)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 7, f"2. CHRONOLOGICAL EVIDENCE TIMELINE ({len(evidence_items)} ITEMS)", ln=1)

        if not evidence_items:
            pdf.set_font("Arial", "I", 9)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(0, 6, "No evidence items have been associated with this investigation case yet.", ln=1)
        else:
            for idx, item in enumerate(evidence_items, start=1):
                # Check space for evidence card (need approx 45mm, if not enough, page break)
                if pdf.get_y() > 230:
                    pdf.add_page()

                # Card container
                card_y = pdf.get_y()
                pdf.set_fill_color(250, 252, 255)
                pdf.set_draw_color(210, 220, 235)
                pdf.rect(10, card_y, 190, 42, "FD")

                # Sequence pill
                pdf.set_fill_color(15, 23, 42)
                pdf.rect(12, card_y + 3, 10, 6, "F")
                pdf.set_xy(12, card_y + 3)
                pdf.set_font("Arial", "B", 8)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(10, 6, f"#{idx}", 0, 0, "C")

                # Time & Evidence Type
                pdf.set_xy(25, card_y + 3)
                pdf.set_font("Arial", "B", 9)
                pdf.set_text_color(15, 23, 42)
                time_fmt = format_seconds(item.timestamp)
                ev_type = clean_text(item.evidence_type.replace("_", " ").upper())
                pdf.cell(75, 6, f"Timestamp: {time_fmt} ({item.timestamp:.1f}s)  |  Type: {ev_type}", 0, 0)

                # Video details
                video_title = (item.video.original_filename or item.video.filename) if item.video else str(item.video_id)
                pdf.set_font("Arial", "", 8)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(85, 6, f"Source: {clean_text(video_title)[:38]}", 0, 1, "R")

                # Technical metrics bar
                pdf.set_xy(14, card_y + 10)
                pdf.set_font("Arial", "B", 8)

                # Object Class
                pdf.set_text_color(71, 85, 105)
                pdf.cell(24, 5, "Object Class:", 0, 0)
                pdf.set_text_color(15, 23, 42)
                cls_str = clean_text(item.object_class or "Unspecified")
                pdf.cell(30, 5, cls_str, 0, 0)

                # Detector Confidence
                pdf.set_text_color(71, 85, 105)
                pdf.cell(32, 5, "Detector Confidence:", 0, 0)
                pdf.set_text_color(15, 23, 42)
                if item.confidence is not None:
                    conf_str = f"{item.confidence * 100:.1f}% (YOLOv8)"
                else:
                    conf_str = "N/A"
                pdf.cell(34, 5, conf_str, 0, 0)

                # Visual Similarity Ranking
                pdf.set_text_color(71, 85, 105)
                pdf.cell(32, 5, "Visual Similarity:", 0, 0)
                if item.visual_similarity_score is not None:
                    pdf.set_text_color(2, 132, 199)
                    sim_str = f"{item.visual_similarity_score * 100:.1f}% (OpenCLIP)"
                else:
                    pdf.set_text_color(100, 116, 139)
                    sim_str = "None"
                pdf.cell(25, 5, sim_str, 0, 1)

                # Image preview (Thumbnail / Crop) on the right side
                img_embedded = False
                if include_evidence_thumbnails:
                    img_path = None
                    # Try crop first if available
                    if item.crop_path:
                        candidate = settings.storage_base / item.crop_path
                        if candidate.is_file():
                            img_path = candidate
                        elif (settings.crops_dir / Path(item.crop_path).name).is_file():
                            img_path = settings.crops_dir / Path(item.crop_path).name

                    # Try frame if crop is missing
                    if not img_path and item.frame_path:
                        candidate = settings.storage_base / item.frame_path
                        if candidate.is_file():
                            img_path = candidate
                        elif (settings.frames_dir / str(item.video_id) / Path(item.frame_path).name).is_file():
                            img_path = settings.frames_dir / str(item.video_id) / Path(item.frame_path).name

                    if img_path and img_path.is_file():
                        try:
                            # Render image at x=155, y=card_y + 14, max width=40, max height=24
                            pdf.image(str(img_path), x=155, y=card_y + 14, w=38, h=24)
                            img_embedded = True
                        except Exception as e:
                            logger.warning(f"Could not render image {img_path} in PDF: {e}")

                if not img_embedded:
                    # Draw a placeholder box
                    pdf.set_draw_color(225, 230, 240)
                    pdf.set_fill_color(240, 243, 248)
                    pdf.rect(155, card_y + 14, 38, 24, "FD")
                    pdf.set_xy(155, card_y + 22)
                    pdf.set_font("Arial", "I", 7)
                    pdf.set_text_color(140, 150, 165)
                    pdf.cell(38, 4, "[No Image Stored]", 0, 0, "C")

                # Investigator Notes block (left 140mm)
                pdf.set_xy(14, card_y + 16)
                pdf.set_font("Arial", "B", 8)
                pdf.set_text_color(71, 85, 105)
                pdf.cell(30, 4, "Investigator Observation:", ln=1)

                pdf.set_xy(14, card_y + 20)
                pdf.set_font("Arial", "", 8)
                pdf.set_text_color(51, 65, 85)
                notes_text = clean_text(item.notes or "No manual observation recorded for this evidence item.")
                pdf.multi_cell(138, 4, notes_text)

                pdf.set_y(card_y + 44)

        # ── Case Activity & Investigator Notes Log ──
        if messages:
            if pdf.get_y() > 230:
                pdf.add_page()
            pdf.ln(3)
            pdf.set_font("Arial", "B", 11)
            pdf.set_text_color(15, 23, 42)
            pdf.cell(0, 7, f"3. INVESTIGATION LOG & NOTES ({len(messages)} ENTRIES)", ln=1)

            for msg in messages:
                if pdf.get_y() > 250:
                    pdf.add_page()
                pdf.set_font("Courier", "B", 8)
                pdf.set_text_color(100, 116, 139)
                t_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S") if msg.created_at else "RECORDED"
                pdf.cell(35, 5, f"[{t_str}]", 0, 0)
                pdf.set_font("Arial", "B", 8)
                pdf.set_text_color(15, 23, 42)
                sender = (msg.sender_type or "INVESTIGATOR").upper()
                pdf.cell(30, 5, f"{sender}:", 0, 0)
                pdf.set_font("Arial", "", 8)
                pdf.set_text_color(51, 65, 85)
                pdf.multi_cell(0, 5, clean_text(msg.message))

        # ── Forensic Methodology & Legal Disclaimer ──
        if pdf.get_y() > 220:
            pdf.add_page()
        pdf.ln(4)
        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, "4. FORENSIC METHODOLOGY, LIMITATIONS & EVIDENTIARY DISCLAIMER", ln=1)

        pdf.set_draw_color(220, 226, 235)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(2)

        pdf.set_font("Arial", "", 7.5)
        pdf.set_text_color(100, 116, 139)
        disclaimer_paragraphs = [
            "1. OBJECT DETECTION & TRACKING: Machine detections (YOLOv8) and multi-frame trajectories (ByteTrack) are automated algorithmic processes. Detections and confidence metrics reflect probabilistic model estimations and do not constitute absolute legal certainty or verified identification.",
            "2. VISUAL SIMILARITY RANKING: Similarity scores derived via OpenCLIP ViT-B-32 reflect cross-modal cosine similarity between visual crops and investigator text queries. Visual similarity is an investigative prioritization aid and must NOT be interpreted as detector confidence, biometric identification, or proof of identity.",
            "3. TIMESTAMP ACCURACY: All timeline markers, durations, and sequence numbers are relative to the source digital video file timestamp stream and do not guarantee synchronization with external atomic or real-world UTC clocks unless specifically calibrated with timecode metadata.",
            "4. CHAIN OF CUSTODY: This document was generated automatically by VisionTrace AI evidentiary reporting engine. Raw source footage, frames, and extracted crop artifacts are preserved in the platform's secure asset repository.",
        ]
        for p in disclaimer_paragraphs:
            pdf.multi_cell(0, 4, clean_text(p))
            pdf.ln(1)

        # ── Persist Report PDF to Disk ──
        report_id = uuid.uuid4()
        case_report_dir = settings.reports_dir / str(investigation.id)
        case_report_dir.mkdir(parents=True, exist_ok=True)
        pdf_filename = f"report_{report_id}.pdf"
        full_pdf_path = case_report_dir / pdf_filename

        pdf.output(str(full_pdf_path), "F")
        logger.info(f"Generated forensic report {report_id} at {full_pdf_path}")

        # Relative path for portable storage reference
        rel_pdf_path = f"reports/{investigation.id}/{pdf_filename}"

        # ── Create or Update Report Database Record ──
        timeline_summary = {
            "evidence_count": len(evidence_items),
            "evidence_ids": [str(e.id) for e in evidence_items],
            "video_ids": list({str(e.video_id) for e in evidence_items}),
        }

        db_report = Report(
            id=report_id,
            investigation_id=investigation.id,
            title=report_title,
            executive_summary=exec_summary,
            findings={"notes": clean_text(custom_notes)} if custom_notes else {},
            evidence_timeline=timeline_summary,
            pdf_path=rel_pdf_path,
            status="completed",
            generated_by_ai=True,
        )
        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        return db_report
