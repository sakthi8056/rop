"""
Screening workflow API routes.
Orchestrates the complete screening pipeline: session → upload → analyze → results.
"""

import logging
import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
import aiosqlite

from config import get_settings
from database import get_db
from models.screening import ScreeningSessionCreate, ScreeningSessionUpdate
from services.auth_service import get_current_user
from services.ai_engine import get_ai_engine
from services.explainability import get_explainability_service
from services.recommendation import get_recommendation, determine_clinical_status

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/start")
async def start_screening_session(
    session_data: Optional[ScreeningSessionCreate] = Body(None),
    patient_id: Optional[str] = Query(None),
    screening_date: Optional[str] = Query(None),
    notes: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a new screening session for a patient."""
    target_patient_id = (session_data.patient_id if session_data and session_data.patient_id else patient_id)
    if not target_patient_id:
        raise HTTPException(status_code=422, detail="patient_id is required")

    target_date = (session_data.screening_date if session_data and session_data.screening_date else screening_date) or datetime.now().strftime("%Y-%m-%d")
    target_notes = (session_data.notes if session_data and session_data.notes else notes)

    # Verify patient exists
    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ? AND is_deleted = 0",
        (target_patient_id,),
    )
    patient = await cursor.fetchone()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    session_id = f"SCR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

    await db.execute(
        """INSERT INTO screening_sessions (session_id, patient_id, screening_date, status, notes, created_by)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (session_id, target_patient_id, target_date, "created", target_notes, current_user["username"]),
    )
    await db.commit()

    logger.info(f"Screening session started: {session_id} for patient {target_patient_id}")

    return {
        "session_id": session_id,
        "patient_id": target_patient_id,
        "screening_date": target_date,
        "notes": target_notes,
        "status": "created",
    }


@router.post("/{session_id}/analyze")
async def analyze_screening(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    Run the full screening pipeline on all uploaded images for this session.
    Pipeline: Quality Check → AI Inference → Explainability → Recommendation.
    """
    settings = get_settings()

    # Get session
    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ?", (session_id,)
    )
    session = await cursor.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found")

    # Get images
    cursor = await db.execute(
        "SELECT * FROM screening_images WHERE session_id = ? ORDER BY uploaded_at",
        (session_id,),
    )
    images = await cursor.fetchall()
    if not images:
        raise HTTPException(
            status_code=400,
            detail="No images uploaded for this session. Please upload a retinal image first.",
        )

    results = []
    overall_status = "completed"

    for image in images:
        image_dict = dict(image)
        quality_status = image_dict["quality_status"]

        # Skip ungradable images
        if quality_status == "UNGRADABLE":
            result_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
            clinical_info = determine_clinical_status("UNGRADABLE", None, None, False)

            await db.execute(
                """INSERT INTO screening_results
                   (result_id, session_id, image_id, classification, confidence,
                    probabilities, is_demo, model_name, model_version, status,
                    recommendation, recommendation_urgency, screening_limitations)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result_id, session_id, image_dict["image_id"],
                    "Ungradable", None, None, 0,
                    settings.MODEL_NAME, settings.MODEL_VERSION, "ungradable",
                    clinical_info["recommendation"], clinical_info["urgency"],
                    "Image quality was insufficient for AI analysis. Recapture required.",
                ),
            )

            results.append({
                "result_id": result_id,
                "image_id": image_dict["image_id"],
                "status": "ungradable",
                "classification": "Ungradable",
                "canonical_status": clinical_info["canonical_status"],
                "severity": clinical_info["severity"],
                "plus_disease_status": clinical_info["plus_disease_status"],
                "quality_status": clinical_info["quality_display"],
                "recommendation": {
                    "recommendation": clinical_info["recommendation"],
                    "urgency": clinical_info["urgency"],
                    "color": clinical_info["color"],
                    "disclaimer": clinical_info["disclaimer"],
                },
            })
            overall_status = "manual_review"
            continue

        # Run AI inference
        engine = get_ai_engine()
        ai_result = engine.analyze(image_dict["file_path"])

        # Generate explainability
        xai_service = get_explainability_service()
        xai_result = xai_service.generate(
            image_dict["file_path"],
            session_id,
            image_dict["image_id"],
            ai_result.get("predicted_class_index"),
        )

        # Synthesize clinical status with clinical safeguards against misleading negatives
        clinical_info = determine_clinical_status(
            quality_status=quality_status,
            classification=ai_result.get("classification"),
            confidence=ai_result.get("confidence"),
            is_demo=ai_result.get("is_demo", False),
        )

        # Store result
        result_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
        await db.execute(
            """INSERT INTO screening_results
               (result_id, session_id, image_id, classification, confidence,
                probabilities, is_demo, model_name, model_version, status,
                heatmap_path, overlay_path,
                recommendation, recommendation_urgency, screening_limitations)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result_id, session_id, image_dict["image_id"],
                ai_result.get("classification"),
                ai_result.get("confidence") if not ai_result.get("is_demo") else None,
                json.dumps(ai_result.get("probabilities")),
                1 if ai_result.get("is_demo") else 0,
                ai_result.get("model_name"),
                ai_result.get("model_version"),
                ai_result.get("status", "failed"),
                xai_result.get("heatmap_url"),
                xai_result.get("overlay_url"),
                clinical_info["recommendation"],
                clinical_info["urgency"],
                ai_result.get("screening_limitations"),
            ),
        )

        results.append({
            "result_id": result_id,
            "image_id": image_dict["image_id"],
            "status": ai_result.get("status"),
            "classification": ai_result.get("classification"),
            "canonical_status": clinical_info["canonical_status"],
            "severity": clinical_info["severity"],
            "plus_disease_status": clinical_info["plus_disease_status"],
            "quality_status": clinical_info["quality_display"],
            "confidence": ai_result.get("confidence") if not ai_result.get("is_demo") else None,
            "probabilities": ai_result.get("probabilities"),
            "is_demo": ai_result.get("is_demo", False),
            "model_name": ai_result.get("model_name"),
            "model_version": ai_result.get("model_version"),
            "heatmap_url": xai_result.get("heatmap_url"),
            "overlay_url": xai_result.get("overlay_url"),
            "xai_explanation": xai_result.get("explanation"),
            "recommendation": {
                "recommendation": clinical_info["recommendation"],
                "urgency": clinical_info["urgency"],
                "color": clinical_info["color"],
                "disclaimer": clinical_info["disclaimer"],
            },
            "screening_limitations": ai_result.get("screening_limitations"),
        })

        if ai_result.get("is_demo"):
            overall_status = "demo"
        elif ai_result.get("status") == "failed":
            overall_status = "failed"
        elif clinical_info["canonical_status"].startswith("INCONCLUSIVE"):
            overall_status = "manual_review"

    # Update session status
    await db.execute(
        "UPDATE screening_sessions SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (overall_status, session_id),
    )
    await db.commit()

    logger.info(f"Screening analysis completed: {session_id}, status: {overall_status}")

    return {
        "session_id": session_id,
        "overall_status": overall_status,
        "is_demo": settings.demo_mode,
        "results": results,
    }


@router.get("/{session_id}/results")
async def get_screening_results(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get full screening results for a session."""
    # Get session
    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ? AND is_deleted = 0", (session_id,)
    )
    session = await cursor.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found or deleted")

    session_dict = dict(session)

    # Get patient
    cursor = await db.execute(
        "SELECT * FROM patients WHERE patient_id = ?", (session_dict["patient_id"],)
    )
    patient = await cursor.fetchone()
    patient_dict = dict(patient) if patient else {}

    # Get images
    cursor = await db.execute(
        "SELECT * FROM screening_images WHERE session_id = ?", (session_id,)
    )
    images = await cursor.fetchall()
    image_list = []
    image_qualities = {}
    for img in images:
        img_dict = dict(img)
        image_qualities[img_dict["image_id"]] = img_dict["quality_status"]
        image_list.append({
            "image_id": img_dict["image_id"],
            "eye_label": img_dict["eye_label"],
            "original_filename": img_dict["original_filename"],
            "quality_status": img_dict["quality_status"],
            "quality_score": img_dict["quality_score"],
            "quality_details": json.loads(img_dict["quality_details"]) if img_dict["quality_details"] else None,
            "preview_url": f"/uploads/{img_dict['stored_filename']}",
        })

    # Get results
    cursor = await db.execute(
        "SELECT * FROM screening_results WHERE session_id = ?", (session_id,)
    )
    results = await cursor.fetchall()
    result_list = []
    is_demo = False
    canonical_statuses = []

    for res in results:
        res_dict = dict(res)
        if res_dict["is_demo"]:
            is_demo = True
        
        q_status = image_qualities.get(res_dict["image_id"], "ACCEPTABLE")
        clin = determine_clinical_status(
            quality_status=q_status,
            classification=res_dict["classification"],
            confidence=res_dict["confidence"] if not res_dict["is_demo"] else None,
            is_demo=bool(res_dict["is_demo"]),
        )
        canonical_statuses.append(clin["canonical_status"])

        result_list.append({
            "result_id": res_dict["result_id"],
            "image_id": res_dict["image_id"],
            "classification": res_dict["classification"],
            "canonical_status": clin["canonical_status"],
            "severity": clin["severity"],
            "plus_disease_status": clin["plus_disease_status"],
            "quality_status": clin["quality_display"],
            "confidence": res_dict["confidence"] if not res_dict["is_demo"] else None,
            "probabilities": json.loads(res_dict["probabilities"]) if res_dict["probabilities"] else None,
            "is_demo": bool(res_dict["is_demo"]),
            "model_name": res_dict["model_name"],
            "model_version": res_dict["model_version"],
            "status": res_dict["status"],
            "heatmap_url": res_dict["heatmap_path"],
            "overlay_url": res_dict["overlay_path"],
            "recommendation": res_dict["recommendation"],
            "recommendation_urgency": res_dict["recommendation_urgency"],
            "screening_limitations": res_dict["screening_limitations"],
            "analyzed_at": res_dict["analyzed_at"],
        })

    # Overall canonical summary
    primary_canonical = canonical_statuses[0] if canonical_statuses else "PENDING_ANALYSIS"

    return {
        "session": {
            "session_id": session_dict["session_id"],
            "patient_id": session_dict["patient_id"],
            "screening_date": session_dict["screening_date"],
            "status": session_dict["status"],
            "notes": session_dict.get("notes"),
            "created_by": session_dict["created_by"],
            "created_at": session_dict["created_at"],
        },
        "patient": patient_dict,
        "images": image_list,
        "results": result_list,
        "overall_status": session_dict["status"],
        "canonical_status": primary_canonical,
        "is_demo": is_demo,
    }


@router.put("/{session_id}")
async def update_screening_session(
    session_id: str,
    session_update: ScreeningSessionUpdate,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Update screening session details (e.g. notes, screening date)."""
    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ? AND is_deleted = 0",
        (session_id,),
    )
    existing = await cursor.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Screening session not found")

    update_data = session_update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields provided to update")

    set_clause = ", ".join(f"{k} = ?" for k in update_data.keys())
    values = list(update_data.values())
    values.append(session_id)

    await db.execute(
        f"UPDATE screening_sessions SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        values,
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ?", (session_id,)
    )
    row = await cursor.fetchone()
    logger.info(f"Screening session updated: {session_id} by {current_user['username']}")
    return dict(row)


@router.delete("/{session_id}")
async def delete_screening_session(
    session_id: str,
    confirm: bool = Query(False, description="Must be true to confirm deletion"),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Soft-delete a screening session (requires confirm=true)."""
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Deletion requires confirm=true. This action cannot be undone.",
        )

    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ? AND is_deleted = 0",
        (session_id,),
    )
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="Screening session not found")

    await db.execute(
        "UPDATE screening_sessions SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
        (session_id,),
    )
    await db.commit()
    logger.info(f"Screening session deleted: {session_id} by {current_user['username']}")
    return {"message": "Screening session deleted successfully", "session_id": session_id}
