"""
Report generation and download API routes.
"""

import logging
import os
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
import aiosqlite

from config import get_settings
from database import get_db
from services.auth_service import get_current_user
from services.pdf_generator import generate_pdf_report

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/generate/{session_id}")
async def generate_report(
    session_id: str,
    language: str = Query(default="en", pattern="^(en|ta)$"),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Generate a PDF screening report for a session."""
    # Get session
    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ?", (session_id,)
    )
    session = await cursor.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found")
    session_data = dict(session)

    # Get patient
    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ?", (session_data["patient_id"],)
    )
    patient = await cursor.fetchone()
    patient_data = dict(patient) if patient else {}

    # Get images
    cursor = await db.execute(
        "SELECT * FROM screening_images WHERE session_id = ?", (session_id,)
    )
    images = [dict(row) for row in await cursor.fetchall()]

    # Get results
    cursor = await db.execute(
        "SELECT * FROM screening_results WHERE session_id = ?", (session_id,)
    )
    results = [dict(row) for row in await cursor.fetchall()]

    if not results:
        raise HTTPException(
            status_code=400,
            detail="No screening results found. Please run the analysis before generating a report.",
        )

    try:
        report_id, file_path = generate_pdf_report(
            session_data, patient_data, images, results, language
        )
    except Exception as e:
        logger.error(f"Report generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {str(e)}",
        )

    # Save report record
    from datetime import datetime
    await db.execute(
        """INSERT INTO reports (report_id, session_id, file_path, language)
           VALUES (?, ?, ?, ?)""",
        (report_id, session_id, file_path, language),
    )
    await db.commit()

    return {
        "report_id": report_id,
        "session_id": session_id,
        "language": language,
        "format": "pdf",
        "preview_url": f"/api/reports/preview/{report_id}",
        "download_url": f"/api/reports/download/{report_id}",
        "generated_at": datetime.now().isoformat(),
    }


@router.get("/download/{report_id}")
async def download_report(
    report_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Download a generated genuine PDF report."""
    cursor = await db.execute(
        "SELECT * FROM reports WHERE report_id = ?", (report_id,)
    )
    report = await cursor.fetchone()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    file_path = report["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    filename = f"{report_id}.pdf"

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/preview/{report_id}")
async def preview_report(
    report_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Preview a genuine PDF report (inline display)."""
    cursor = await db.execute(
        "SELECT * FROM reports WHERE report_id = ?", (report_id,)
    )
    report = await cursor.fetchone()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    file_path = report["file_path"]
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=report.pdf"},
    )


@router.get("/session/{session_id}")
async def list_session_reports(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all reports for a screening session."""
    cursor = await db.execute(
        "SELECT * FROM reports WHERE session_id = ? ORDER BY generated_at DESC",
        (session_id,),
    )
    rows = await cursor.fetchall()
    return [
        {
            "report_id": row["report_id"],
            "session_id": row["session_id"],
            "language": row["language"],
            "preview_url": f"/api/reports/preview/{row['report_id']}",
            "download_url": f"/api/reports/download/{row['report_id']}",
            "generated_at": row["generated_at"],
        }
        for row in rows
    ]
