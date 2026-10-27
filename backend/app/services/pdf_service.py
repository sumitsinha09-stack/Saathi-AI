import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from backend.app.services.redaction_service import RedactionService

logger = logging.getLogger(__name__)

# Register Unicode TrueType font if available (for Hindi, Tamil, and Indic scripts)
UNICODE_FONT_NAME = "Helvetica"
UNICODE_FONT_BOLD = "Helvetica-Bold"

CANDIDATE_FONTS = [
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "ArialUnicode"),
    ("/Library/Fonts/Arial Unicode.ttf", "ArialUnicode"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVuSans"),
    ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf", "NotoSans"),
]

for font_path, font_name in CANDIDATE_FONTS:
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            UNICODE_FONT_NAME = font_name
            UNICODE_FONT_BOLD = font_name
            logger.info(f"Registered PDF font {font_name} from {font_path}")
            break
        except Exception as e:
            logger.debug(f"Could not register font {font_path}: {e}")


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and print 'Page X of Y'
    along with running confidentiality and disclaimer footer.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer divider line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.75)
        self.line(36, 42, 595.27 - 36, 42)

        # Left: Legal notice note
        footer_text = "Saathi AI Relief Report — User-Generated Document (Not an Official Police FIR)"
        self.drawString(36, 30, footer_text)

        # Right: Page X of Y
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(595.27 - 36, 30, page_str)
        self.restoreState()


class PDFService:
    """
    Generates formal, mobile-readable Complaint Summary PDFs for confirmed complaints.
    - Zero permanent file storage: generated in-memory via io.BytesIO.
    - Credential redaction guaranteed across all narrative and metadata fields.
    - Prominent reference number, status timeline, and legal disclaimer.
    """

    @classmethod
    def _sanitize_text(cls, text: Optional[str]) -> str:
        """Sanitizes text, applies redaction, and escapes XML/HTML tags for ReportLab Paragraphs."""
        if not text:
            return ""
        redacted = RedactionService.redact_text(str(text))
        # Escape XML entities
        escaped = (
            redacted.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )
        return escaped

    @classmethod
    def _safe_unicode_text(cls, text: Optional[str]) -> str:
        """
        If standard Helvetica is the active font, replaces unsupported Unicode characters
        with safe representation to prevent UnicodeEncodeError.
        """
        raw = cls._sanitize_text(text)
        if UNICODE_FONT_NAME == "Helvetica":
            # Filter to latin-1 / ascii safe characters
            return raw.encode("ascii", "replace").decode("ascii")
        return raw

    @classmethod
    def generate_complaint_pdf(
        cls,
        complaint: Dict[str, Any],
        history: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        """
        Generates a professional PDF document from complaint data.
        Returns bytes representing the complete PDF file.
        """
        buffer = io.BytesIO()

        # Target A4 size with 36pt (0.5 inch) margins for mobile & print readability
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=54,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        title_style = ParagraphStyle(
            "DocTitle",
            parent=styles["Heading1"],
            fontName=UNICODE_FONT_BOLD,
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "DocSubTitle",
            parent=styles["Normal"],
            fontName=UNICODE_FONT_NAME,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
            spaceAfter=12,
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading2"],
            fontName=UNICODE_FONT_BOLD,
            fontSize=11,
            leading=15,
            textColor=colors.HexColor("#1E293B"),
            spaceBefore=8,
            spaceAfter=4,
        )
        body_style = ParagraphStyle(
            "Body",
            parent=styles["Normal"],
            fontName=UNICODE_FONT_NAME,
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#1E293B"),
        )
        body_bold = ParagraphStyle(
            "BodyBold",
            parent=styles["Normal"],
            fontName=UNICODE_FONT_BOLD,
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#0F172A"),
        )
        meta_label = ParagraphStyle(
            "MetaLabel",
            parent=styles["Normal"],
            fontName=UNICODE_FONT_BOLD,
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#64748B"),
        )
        meta_val = ParagraphStyle(
            "MetaVal",
            parent=styles["Normal"],
            fontName=UNICODE_FONT_NAME,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0F172A"),
        )
        disclaimer_style = ParagraphStyle(
            "Disclaimer",
            parent=styles["Normal"],
            fontName=UNICODE_FONT_NAME,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#7F1D1D"),
        )
        disclaimer_bold = ParagraphStyle(
            "DisclaimerBold",
            parent=styles["Normal"],
            fontName=UNICODE_FONT_BOLD,
            fontSize=8.5,
            leading=12,
            textColor=colors.HexColor("#991B1B"),
        )

        elements = []

        ref = complaint.get("reference_number", "SAI-XXXXXX")
        status_val = (complaint.get("status") or "CONFIRMED").upper()
        created_at_str = complaint.get("created_at") or datetime.now(timezone.utc).isoformat()
        confirmed_at_str = complaint.get("confirmed_at") or created_at_str

        # Format dates nicely
        def format_iso(dt_str: Optional[str]) -> str:
            if not dt_str:
                return "Not recorded"
            try:
                dt = datetime.fromisoformat(str(dt_str).replace("Z", "+00:00"))
                return dt.strftime("%d %b %Y, %I:%M %p UTC")
            except Exception:
                return str(dt_str)

        created_formatted = format_iso(created_at_str)
        confirmed_formatted = format_iso(confirmed_at_str)

        # -------------------------------------------------------------
        # 1. HEADER & BRANDING
        # -------------------------------------------------------------
        header_data = [
            [
                Paragraph("<b>SAATHI AI</b> | Incident Relief Report", title_style),
                Paragraph(f"<b>CASE REF:</b> {ref}<br/><b>STATUS:</b> {status_val}", meta_label),
            ]
        ]
        header_table = Table(header_data, colWidths=[350, 173])
        header_table.setStyle(
            TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, 0), "RIGHT"),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ])
        )
        elements.append(header_table)

        elements.append(Paragraph("Emergency Cybercrime Victim Record & Immediate Dispute Notice Summary", subtitle_style))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

        # -------------------------------------------------------------
        # 2. KEY METADATA SUMMARY BOX
        # -------------------------------------------------------------
        loss_val = complaint.get("financial_loss")
        curr = complaint.get("currency") or "INR"
        loss_display = f"{curr} {float(loss_val):,.2f}" if loss_val is not None else "Nil / Unspecified"

        meta_grid = [
            [
                Paragraph("Complaint Reference", meta_label),
                Paragraph("Verification Status", meta_label),
                Paragraph("Incident Category", meta_label),
            ],
            [
                Paragraph(f"<b>{ref}</b>", body_bold),
                Paragraph(f"<font color='#059669'><b>{status_val}</b></font>", body_style),
                Paragraph(cls._safe_unicode_text(complaint.get("incident_type") or "Cyber Financial Fraud"), body_style),
            ],
            [
                Paragraph("Incident Date / Time", meta_label),
                Paragraph("Reported Financial Loss", meta_label),
                Paragraph("Reported Entity / Bank", meta_label),
            ],
            [
                Paragraph(cls._safe_unicode_text(complaint.get("incident_date") or "Not provided"), body_style),
                Paragraph(f"<b>{cls._safe_unicode_text(loss_display)}</b>", body_bold),
                Paragraph(cls._safe_unicode_text(complaint.get("reported_entity") or "Not provided"), body_style),
            ],
            [
                Paragraph("Filing Timestamp", meta_label),
                Paragraph("Confirmation Timestamp", meta_label),
                Paragraph("Suspect Contact / Phone", meta_label),
            ],
            [
                Paragraph(created_formatted, meta_val),
                Paragraph(confirmed_formatted, meta_val),
                Paragraph(cls._safe_unicode_text(complaint.get("phone_number") or "Not provided"), body_style),
            ],
        ]

        meta_table = Table(meta_grid, colWidths=[174, 174, 175])
        meta_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ])
        )
        elements.append(meta_table)
        elements.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 3. COMPLAINT SUMMARY (ENGLISH)
        # -------------------------------------------------------------
        elements.append(Paragraph("1. Incident Summary (English)", section_heading))
        summary_text = complaint.get("english_summary") or complaint.get("summary") or "No summary provided."
        elements.append(Paragraph(cls._safe_unicode_text(summary_text), body_style))
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 4. FACTUAL NARRATIVE & DESCRIPTION
        # -------------------------------------------------------------
        elements.append(Paragraph("2. Detailed Factual Statement", section_heading))
        desc_text = complaint.get("description") or "No detailed description provided."
        elements.append(Paragraph(cls._safe_unicode_text(desc_text), body_style))
        elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 5. ORIGINAL SPOKEN TRANSCRIPT (NATIVE SCRIPT)
        # -------------------------------------------------------------
        transcript_text = complaint.get("original_transcript") or complaint.get("raw_transcript_redacted")
        if transcript_text:
            lang_name = complaint.get("language_name") or complaint.get("language", "Native")
            elements.append(Paragraph(f"3. Original Voice Transcript (Spoken: {cls._safe_unicode_text(lang_name)})", section_heading))

            safe_transcript = cls._safe_unicode_text(transcript_text)
            transcript_box = [
                [Paragraph(f"<i>&ldquo;{safe_transcript}&rdquo;</i>", body_style)]
            ]
            t_table = Table(transcript_box, colWidths=[523])
            t_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#CBD5E1")),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ])
            )
            elements.append(t_table)
            elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 6. TRANSACTION EVIDENCE & IDENTIFIERS
        # -------------------------------------------------------------
        evidence_text = complaint.get("evidence_description")
        if evidence_text:
            elements.append(Paragraph("4. Evidence & Transaction Identifiers", section_heading))
            elements.append(Paragraph(cls._safe_unicode_text(evidence_text), body_style))
            elements.append(Spacer(1, 8))

        # -------------------------------------------------------------
        # 7. STATUS TIMELINE / AUDIT TRAIL
        # -------------------------------------------------------------
        if history:
            elements.append(Paragraph("5. Complaint Status Timeline", section_heading))
            hist_rows = [
                [
                    Paragraph("Timestamp", meta_label),
                    Paragraph("Status Event", meta_label),
                    Paragraph("Audit Note", meta_label),
                ]
            ]
            for ev in history:
                if ev.get("is_demo"):
                    continue  # Keep real audit timeline isolated from simulated demo events
                ts = format_iso(ev.get("created_at"))
                st = (ev.get("status") or "").upper()
                nt = ev.get("note") or ""
                hist_rows.append([
                    Paragraph(ts, meta_val),
                    Paragraph(f"<b>{st}</b>", meta_val),
                    Paragraph(cls._safe_unicode_text(nt), body_style),
                ])

            hist_table = Table(hist_rows, colWidths=[130, 95, 298])
            hist_table.setStyle(
                TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F8FAFC")),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ])
            )
            elements.append(hist_table)
            elements.append(Spacer(1, 10))

        # -------------------------------------------------------------
        # 8. MANDATORY LEGAL DISCLAIMER
        # -------------------------------------------------------------
        disclaimer_rows = [
            [
                Paragraph("<b>LEGAL NOTICE & CITIZEN ADVISORY</b>", disclaimer_bold),
            ],
            [
                Paragraph(
                    "This document is a user-generated incident summary compiled through Saathi AI "
                    "for victim relief, formal bank dispute notification, and personal record preservation. "
                    "<b>This document is NOT an official First Information Report (FIR), court summons, "
                    "or government-issued certificate.</b><br/>"
                    "Under Indian cybersecurity regulations, you should promptly report financial cybercrime "
                    "on the official National Cyber Crime Reporting Portal (<b>https://cybercrime.gov.in</b>) "
                    "or by calling the financial fraud helpline <b>1930</b>.",
                    disclaimer_style,
                )
            ]
        ]
        disc_table = Table(disclaimer_rows, colWidths=[523])
        disc_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FEF2F2")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#FCA5A5")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ])
        )
        elements.append(KeepTogether(disc_table))

        # Build document with NumberedCanvas
        doc.build(elements, canvasmaker=NumberedCanvas)
        return buffer.getvalue()
