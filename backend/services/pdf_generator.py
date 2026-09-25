"""
Professional PDF report generation service using ReportLab.
Produces genuine, print-ready, high-resolution vector PDF screening reports
with zero external C-library / GTK dependencies.
"""

import logging
import os
import json
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether, HRFlowable
)

from config import get_settings, BASE_DIR
from services.recommendation import determine_clinical_status

logger = logging.getLogger(__name__)


def _calculate_ages(patient_data: dict, screening_date_str: str) -> dict:
    """Accurately calculates chronological age, gestational age, PMA, and corrected age."""
    dob_str = patient_data.get("date_of_birth")
    ga_weeks = int(patient_data.get("gestational_age_weeks") or 0)
    ga_days = int(patient_data.get("gestational_age_days") or 0)

    if not dob_str:
        return {
            "ga_str": f"{ga_weeks}w {ga_days}d" if ga_weeks else "—",
            "chrono_str": "—",
            "pma_str": "—",
            "corrected_str": "—",
        }

    try:
        dob = date.fromisoformat(dob_str)
        try:
            ref_date = date.fromisoformat(screening_date_str) if screening_date_str else date.today()
        except Exception:
            ref_date = date.today()

        chrono_days = max((ref_date - dob).days, 0)
        chrono_weeks = chrono_days // 7
        chrono_rem_days = chrono_days % 7
        chrono_str = f"{chrono_weeks} wks {chrono_rem_days} days ({chrono_days} days)"

        ga_str = f"{ga_weeks} wks {ga_days} days"

        total_pma_days = (ga_weeks * 7 + ga_days) + chrono_days
        pma_weeks = total_pma_days // 7
        pma_rem_days = total_pma_days % 7
        pma_str = f"{pma_weeks} wks {pma_rem_days} days"

        if pma_weeks >= 40:
            corr_days = total_pma_days - 280
            corr_weeks = corr_days // 7
            corr_rem = corr_days % 7
            corrected_str = f"{corr_weeks} wks {corr_rem} days corrected"
        else:
            corrected_str = f"Preterm ({40 - pma_weeks} wks before 40w term equivalent)"

        return {
            "ga_str": ga_str,
            "chrono_str": chrono_str,
            "pma_str": pma_str,
            "corrected_str": corrected_str,
        }
    except Exception as e:
        logger.warning(f"Error calculating clinical ages: {e}")
        return {
            "ga_str": f"{ga_weeks}w {ga_days}d",
            "chrono_str": "—",
            "pma_str": "—",
            "corrected_str": "—",
        }


def generate_pdf_report(
    session_data: dict,
    patient_data: dict,
    images: list,
    results: list,
    language: str = "en",
) -> Tuple[str, str]:
    """
    Generate a genuine, print-ready PDF screening report.
    Returns (report_id, file_path).
    """
    settings = get_settings()
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)

    report_id = f"RPT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
    output_path = os.path.join(settings.REPORTS_DIR, f"{report_id}.pdf")
    generated_at_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Document setup
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Custom styles
    header_style = ParagraphStyle(
        "DocHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F172A"),
    )
    sub_header_style = ParagraphStyle(
        "SubHeader",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#475569"),
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
    )
    table_label_style = ParagraphStyle(
        "TableLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#334155"),
    )
    table_value_style = ParagraphStyle(
        "TableValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#0F172A"),
    )
    banner_demo_style = ParagraphStyle(
        "BannerDemo",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor("#9A3412"),
    )
    result_banner_style = ParagraphStyle(
        "ResultBanner",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=17,
        textColor=colors.white,
        alignment=1,  # Center
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#64748B"),
    )

    story = []

    # 1. Header Section
    header_table_data = [
        [
            Paragraph("<b>ROP AI SCREENER</b><br/><font size=9 color='#475569'>AI-Assisted Retinopathy of Prematurity Clinical Screening Report</font>", header_style),
            Paragraph(f"<b>Report ID:</b> {report_id}<br/><b>Date:</b> {session_data.get('screening_date') or generated_at_str[:10]}<br/><b>Time:</b> {generated_at_str[11:]}", sub_header_style),
        ]
    ]
    header_table = Table(header_table_data, colWidths=[340, 180])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0284C7"), spaceAfter=10))

    # Demo Banner if applicable
    is_demo = bool(results and results[0].get("is_demo", False)) or settings.demo_mode
    if is_demo:
        demo_box_data = [
            [
                Paragraph(
                    "<b>WARNING: DEMO / SIMULATION MODE ACTIVE</b><br/>"
                    "This report was generated without a validated AI model. Findings are demonstration baseline simulations and have NO clinical diagnostic validity.",
                    banner_demo_style,
                )
            ]
        ]
        demo_table = Table(demo_box_data, colWidths=[520])
        demo_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFEDD5")),
            ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#F97316")),
            ("PADDING", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(demo_table)
        story.append(Spacer(1, 10))

    # 2. Patient Demographics & Clinical Information
    ages = _calculate_ages(patient_data, session_data.get("screening_date", ""))

    story.append(Paragraph("1. Patient & Clinical Demographics", section_title_style))
    story.append(Spacer(1, 4))

    patient_grid_data = [
        [
            Paragraph("Patient ID", table_label_style),
            Paragraph(str(patient_data.get("patient_id") or "—"), table_value_style),
            Paragraph("Session ID", table_label_style),
            Paragraph(str(session_data.get("session_id") or "—"), table_value_style),
        ],
        [
            Paragraph("Baby's Name", table_label_style),
            Paragraph(str(patient_data.get("infant_name") or "—"), table_value_style),
            Paragraph("Gender", table_label_style),
            Paragraph(str(patient_data.get("gender") or "—"), table_value_style),
        ],
        [
            Paragraph("Mother's Name", table_label_style),
            Paragraph(str(patient_data.get("mother_name") or "—"), table_value_style),
            Paragraph("Guardian Contact", table_label_style),
            Paragraph(str(patient_data.get("contact_number") or "—"), table_value_style),
        ],
        [
            Paragraph("Father's Name", table_label_style),
            Paragraph(str(patient_data.get("father_name") or "—"), table_value_style),
            Paragraph("City / Town / Village", table_label_style),
            Paragraph(str(patient_data.get("city_town_village") or "—"), table_value_style),
        ],
        [
            Paragraph("Hospital / Center", table_label_style),
            Paragraph(str(patient_data.get("hospital_name") or "—"), table_value_style),
            Paragraph("Screened By", table_label_style),
            Paragraph(str(session_data.get("created_by") or patient_data.get("healthcare_worker_name") or "Clinician"), table_value_style),
        ],
        [
            Paragraph("Date of Birth", table_label_style),
            Paragraph(str(patient_data.get("date_of_birth") or "—"), table_value_style),
            Paragraph("Birth Weight", table_label_style),
            Paragraph(f"{patient_data.get('birth_weight_grams')} grams" if patient_data.get("birth_weight_grams") else "—", table_value_style),
        ],
        [
            Paragraph("Gestational Age (Birth)", table_label_style),
            Paragraph(ages["ga_str"], table_value_style),
            Paragraph("Chronological Age", table_label_style),
            Paragraph(ages["chrono_str"], table_value_style),
        ],
        [
            Paragraph("Postmenstrual Age (PMA)", table_label_style),
            Paragraph(ages["pma_str"], table_value_style),
            Paragraph("Corrected Age", table_label_style),
            Paragraph(ages["corrected_str"], table_value_style),
        ],
        [
            Paragraph("Clinical Notes", table_label_style),
            Paragraph(str(patient_data.get("clinical_notes") or patient_data.get("clinical_history") or "None documented"), table_value_style),
            "",
            "",
        ],
    ]

    patient_table = Table(patient_grid_data, colWidths=[120, 140, 120, 140])
    patient_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("SPAN", (1, 8), (3, 8)),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(patient_table)
    story.append(Spacer(1, 10))

    # 3. Screening Findings & AI Classification
    first_res = results[0] if results else {}
    first_img = images[0] if images else {}
    quality_status = first_img.get("quality_status", "ACCEPTABLE")
    raw_class = first_res.get("classification")
    confidence = first_res.get("confidence") if not is_demo else None

    clinical = determine_clinical_status(
        quality_status=quality_status,
        classification=raw_class,
        confidence=confidence,
        is_demo=is_demo,
    )

    canonical_status = clinical["canonical_status"]

    # Select banner color
    if "POSITIVE" in canonical_status:
        banner_bg = colors.HexColor("#DC2626")  # Red
    elif "NEGATIVE" in canonical_status:
        banner_bg = colors.HexColor("#16A34A")  # Green
    elif "INCONCLUSIVE" in canonical_status or "UNGRADABLE" in canonical_status:
        banner_bg = colors.HexColor("#D97706")  # Amber
    else:
        banner_bg = colors.HexColor("#EA580C")  # Orange for Demo

    banner_data = [[Paragraph(canonical_status, result_banner_style)]]
    banner_table = Table(banner_data, colWidths=[520])
    banner_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), banner_bg),
        ("PADDING", (0, 0), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    story.append(Paragraph("2. AI Screening Assessment", section_title_style))
    story.append(Spacer(1, 4))
    story.append(banner_table)
    story.append(Spacer(1, 6))

    findings_data = [
        [
            Paragraph("Image Quality Assessment", table_label_style),
            Paragraph(f"<b>{clinical['quality_display']}</b> (Score: {first_img.get('quality_score', '—')})", table_value_style),
            Paragraph("AI Confidence", table_label_style),
            Paragraph(clinical["confidence_display"] or ("Not Applicable (Demo Mode)" if is_demo else "—"), table_value_style),
        ],
        [
            Paragraph("ROP Classification / Severity", table_label_style),
            Paragraph(f"<b>{clinical['severity']}</b>", table_value_style),
            Paragraph("Plus Disease Status", table_label_style),
            Paragraph(f"<b>{clinical['plus_disease_status']}</b>", table_value_style),
        ],
        [
            Paragraph("Eye Examined", table_label_style),
            Paragraph(str(first_img.get("eye_label") or "Unspecified").capitalize(), table_value_style),
            Paragraph("Inference Model", table_label_style),
            Paragraph(f"{settings.MODEL_NAME} ({settings.MODEL_VERSION})" if not is_demo else "Simulation Mode", table_value_style),
        ],
    ]

    findings_table = Table(findings_data, colWidths=[140, 120, 120, 140])
    findings_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 4.5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(findings_table)
    story.append(Spacer(1, 10))

    # 4. Retinal Scan Images (Fundus Photo & Attention Overlay)
    img_cells = []
    has_images = False

    # Original Image
    original_path = None
    stored_name = first_img.get("stored_filename")
    if stored_name:
        candidate_path = os.path.join(settings.UPLOADS_DIR, stored_name)
        if os.path.exists(candidate_path):
            original_path = candidate_path

    # Overlay / Heatmap
    overlay_path = None
    raw_overlay = first_res.get("overlay_path") or first_res.get("heatmap_path")
    if raw_overlay:
        if os.path.isabs(raw_overlay) and os.path.exists(raw_overlay):
            overlay_path = raw_overlay
        else:
            fname = os.path.basename(raw_overlay)
            candidate = os.path.join(settings.UPLOADS_DIR, fname)
            if os.path.exists(candidate):
                overlay_path = candidate

    col_w = 255
    target_h = 135

    def create_rl_image(img_p):
        try:
            return RLImage(img_p, width=col_w - 20, height=target_h)
        except Exception as e:
            logger.warning(f"Could not load image into reportlab: {e}")
            return Paragraph("<i>Image not displayable</i>", table_value_style)

    if original_path or overlay_path:
        has_images = True
        img_row = []
        label_row = []

        if original_path:
            img_row.append(create_rl_image(original_path))
            label_row.append(Paragraph("<b>Uploaded Retinal Scan</b>", table_label_style))
        else:
            img_row.append(Paragraph("<i>No scan uploaded</i>", table_value_style))
            label_row.append(Paragraph("<b>Uploaded Retinal Scan</b>", table_label_style))

        if overlay_path:
            img_row.append(create_rl_image(overlay_path))
            label_row.append(Paragraph("<b>AI Attention / Vessel Heatmap</b>", table_label_style))
        else:
            img_row.append(Paragraph("<i>No heatmap generated</i>", table_value_style))
            label_row.append(Paragraph("<b>AI Attention / Vessel Heatmap</b>", table_label_style))

        img_table = Table([img_row, label_row], colWidths=[col_w, col_w])
        img_table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
            ("PADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(Paragraph("3. Retinal Imaging & Vascular Attention", section_title_style))
        story.append(Spacer(1, 4))
        story.append(img_table)
        story.append(Spacer(1, 10))

    # 5. Clinical Recommendation & Referral Guidance
    story.append(Paragraph("4. Recommended Clinical Action Plan", section_title_style))
    story.append(Spacer(1, 4))

    rec_data = [
        [
            Paragraph(
                f"<b>Action Guidance:</b> {clinical['recommendation']}<br/><br/>"
                f"<b>Follow-up Urgency Level:</b> <font color='{banner_bg.hexval()}'>{clinical['urgency'].upper()}</font>",
                table_value_style,
            )
        ]
    ]
    rec_table = Table(rec_data, colWidths=[520])
    rec_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, banner_bg),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(rec_table)
    story.append(Spacer(1, 10))

    # 6. Medical Disclaimer & Statutory Notice
    disclaimer_text = (
        "<b>LEGAL & CLINICAL DISCLAIMER:</b><br/>"
        "This software is an AI-assisted screening decision-support tool and research prototype. "
        "It does NOT constitute a confirmed clinical diagnosis. All findings, severity grades, and referrals must be "
        "independently verified through dilated indirect ophthalmoscopy or retinal examination by a qualified ophthalmologist. "
        "Screening recommendations do not replace direct clinical examination by a specialist."
    )
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CBD5E1"), spaceAfter=6))
    story.append(Paragraph(disclaimer_text, disclaimer_style))

    # Build the PDF
    doc.build(story)
    logger.info(f"Genuine ReportLab PDF successfully generated: {output_path}")

    return report_id, output_path
