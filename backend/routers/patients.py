"""
Patient registration API routes.
"""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
import aiosqlite

from database import get_db
from models.patient import PatientCreate, PatientUpdate, PatientResponse
from services.auth_service import get_current_user
from services.patient_service import generate_patient_id

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/next-id")
async def get_next_patient_id(
    current_user: dict = Depends(get_current_user),
):
    """Generate the next auto-generated patient ID for preview."""
    return {"patient_id": generate_patient_id()}


@router.post("/", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient: PatientCreate,
    patient_id: Optional[str] = Query(None, description="Optional pre-generated patient ID"),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Register a new patient."""
    assigned_id = patient_id.strip() if (patient_id and patient_id.strip()) else generate_patient_id()

    # Check if ID already exists
    cursor = await db.execute("SELECT 1 FROM patients WHERE patient_id = ?", (assigned_id,))
    if await cursor.fetchone():
        assigned_id = generate_patient_id()

    clinical_notes = patient.clinical_notes or patient.clinical_history

    await db.execute(
        """INSERT INTO patients (
            patient_id, infant_name, gender, mother_name, father_name, date_of_birth,
            gestational_age_weeks, gestational_age_days, birth_weight_grams,
            postnatal_age_days, clinical_history, clinical_notes, hospital_name,
            city_town_village, contact_number,
            healthcare_worker_name, healthcare_worker_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            assigned_id,
            patient.infant_name,
            patient.gender,
            patient.mother_name,
            patient.father_name,
            patient.date_of_birth,
            patient.gestational_age_weeks,
            patient.gestational_age_days,
            patient.birth_weight_grams,
            patient.postnatal_age_days,
            patient.clinical_history,
            clinical_notes,
            patient.hospital_name,
            patient.city_town_village,
            patient.contact_number,
            patient.healthcare_worker_name or current_user["full_name"],
            patient.healthcare_worker_id or current_user["username"],
        ),
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ?", (assigned_id,)
    )
    row = await cursor.fetchone()
    logger.info(f"Patient registered: {assigned_id}")
    return PatientResponse(**dict(row))


@router.get("/", response_model=list[PatientResponse])
async def list_patients(
    search: Optional[str] = Query(None, description="Search by patient ID, name, or location"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List patients with optional search."""
    if search:
        search_param = f"%{search}%"
        cursor = await db.execute(
            """SELECT * FROM patients WHERE is_deleted = 0
               AND (patient_id LIKE ? OR infant_name LIKE ? OR mother_name LIKE ? OR city_town_village LIKE ? OR hospital_name LIKE ?)
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (search_param, search_param, search_param, search_param, search_param, limit, offset),
        )
    else:
        cursor = await db.execute(
            """SELECT * FROM patients WHERE is_deleted = 0
               ORDER BY created_at DESC LIMIT ? OFFSET ?""",
            (limit, offset),
        )
    rows = await cursor.fetchall()
    return [PatientResponse(**dict(row)) for row in rows]


@router.get("/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a single patient by ID."""
    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ? AND is_deleted = 0",
        (patient_id,),
    )
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")
    return PatientResponse(**dict(row))


@router.put("/{patient_id}", response_model=PatientResponse)
async def update_patient(
    patient_id: str,
    patient_update: PatientUpdate,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update patient information."""
    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ? AND is_deleted = 0",
        (patient_id,),
    )
    existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Patient not found")

    update_data = patient_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # If clinical_notes is updated, keep clinical_history in sync
    if "clinical_notes" in update_data and "clinical_history" not in update_data:
        update_data["clinical_history"] = update_data["clinical_notes"]

    set_clause = ", ".join(f"{k} = ?" for k in update_data.keys())
    values = list(update_data.values())
    values.append(patient_id)

    await db.execute(
        f"UPDATE patients SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE patient_id = ?",
        values,
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ?", (patient_id,)
    )
    row = await cursor.fetchone()
    return PatientResponse(**dict(row))


@router.delete("/{patient_id}")
async def delete_patient(
    patient_id: str,
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a patient record and cascade to their screening sessions (requires confirm=true)."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion requires confirm=true. This action is irreversible.",
        )

    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ? AND is_deleted = 0",
        (patient_id,),
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Patient not found")

    # Soft delete patient
    await db.execute(
        "UPDATE patients SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE patient_id = ?",
        (patient_id,),
    )
    # Safely cascade soft deletion to associated screening sessions
    await db.execute(
        "UPDATE screening_sessions SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE patient_id = ?",
        (patient_id,),
    )
    await db.commit()
    logger.info(f"Patient and sessions soft-deleted: {patient_id} by {current_user['username']}")
    return {"message": "Patient and related records deleted successfully", "patient_id": patient_id}
