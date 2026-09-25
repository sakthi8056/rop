"""
Screening history API routes.
"""

import logging
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
import aiosqlite

from database import get_db
from services.auth_service import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def list_screening_history(
    patient_id: Optional[str] = Query(None),
    date_from: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List screening history with filters."""
    query = """
        SELECT
            ss.session_id, ss.patient_id, ss.screening_date, ss.status, ss.notes,
            ss.created_by, ss.created_at,
            p.infant_name, p.gender, p.mother_name, p.hospital_name, p.city_town_village, p.contact_number,
            (SELECT COUNT(*) FROM screening_images si WHERE si.session_id = ss.session_id) as image_count,
            (SELECT sr.classification FROM screening_results sr
             WHERE sr.session_id = ss.session_id LIMIT 1) as latest_classification,
            (SELECT sr.is_demo FROM screening_results sr
             WHERE sr.session_id = ss.session_id LIMIT 1) as is_demo,
            (SELECT r.report_id FROM reports r
             WHERE r.session_id = ss.session_id LIMIT 1) as report_id
        FROM screening_sessions ss
        LEFT JOIN patients p ON ss.patient_id = p.patient_id
        WHERE (ss.is_deleted IS NULL OR ss.is_deleted = 0)
          AND (p.is_deleted IS NULL OR p.is_deleted = 0)
    """
    params = []

    if patient_id:
        param_pattern = f"%{patient_id}%"
        query += " AND (ss.patient_id LIKE ? OR p.infant_name LIKE ? OR p.mother_name LIKE ? OR p.city_town_village LIKE ?)"
        params.extend([param_pattern, param_pattern, param_pattern, param_pattern])

    if date_from:
        query += " AND ss.screening_date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND ss.screening_date <= ?"
        params.append(date_to)

    if status:
        query += " AND ss.status = ?"
        params.append(status)

    query += " ORDER BY ss.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    return [
        {
            "session_id": row["session_id"],
            "patient_id": row["patient_id"],
            "infant_name": row["infant_name"],
            "gender": row["gender"],
            "mother_name": row["mother_name"],
            "hospital_name": row["hospital_name"],
            "city_town_village": row["city_town_village"],
            "contact_number": row["contact_number"],
            "screening_date": row["screening_date"],
            "status": row["status"],
            "notes": row["notes"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
            "image_count": row["image_count"],
            "latest_classification": row["latest_classification"],
            "is_demo": bool(row["is_demo"]) if row["is_demo"] is not None else None,
            "report_id": row["report_id"],
        }
        for row in rows
    ]


@router.get("/{session_id}")
async def get_history_detail(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get detailed history for a specific session."""
    # Reuse the screening results endpoint logic
    from routers.screening import get_screening_results
    return await get_screening_results(session_id, db, current_user)


@router.delete("/{session_id}")
async def delete_screening_session(
    session_id: str,
    confirm: bool = Query(False),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a screening session and all associated data."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion requires confirm=true. This will permanently remove the screening session, images, and results.",
        )

    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ?", (session_id,)
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete in order: results → images → reports → session
    await db.execute("DELETE FROM screening_results WHERE session_id = ?", (session_id,))
    await db.execute("DELETE FROM screening_images WHERE session_id = ?", (session_id,))
    await db.execute("DELETE FROM reports WHERE session_id = ?", (session_id,))
    await db.execute("DELETE FROM screening_sessions WHERE session_id = ?", (session_id,))
    await db.commit()

    logger.info(f"Screening session deleted: {session_id} by {current_user['username']}")
    return {"message": "Screening session deleted", "session_id": session_id}
