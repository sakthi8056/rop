"""
Retinal image upload API routes.
"""

import logging
import uuid
import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
import aiosqlite

from config import get_settings
from database import get_db
from services.auth_service import get_current_user
from services.image_quality import get_quality_assessor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload/{session_id}")
async def upload_image(
    session_id: str,
    file: UploadFile = File(...),
    eye_label: str = Form(default="unspecified"),
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Upload a retinal image for a screening session."""
    settings = get_settings()

    # Validate session exists
    cursor = await db.execute(
        "SELECT * FROM screening_sessions WHERE session_id = ?", (session_id,)
    )
    session = await cursor.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Screening session not found")

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS)}",
        )

    # Validate file size
    contents = await file.read()
    if len(contents) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )

    if len(contents) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # Save file
    image_id = str(uuid.uuid4())[:12]
    stored_filename = f"{session_id}_{image_id}{ext}"
    file_path = os.path.join(settings.UPLOADS_DIR, stored_filename)

    with open(file_path, "wb") as f:
        f.write(contents)

    # Run quality assessment
    assessor = get_quality_assessor()
    quality_result = assessor.assess(file_path)

    # Store in database
    import json

    await db.execute(
        """INSERT INTO screening_images (
            image_id, session_id, eye_label, original_filename,
            stored_filename, file_path, file_size_bytes, mime_type,
            quality_status, quality_score, quality_details
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            image_id,
            session_id,
            eye_label,
            file.filename,
            stored_filename,
            file_path,
            len(contents),
            file.content_type,
            quality_result["overall_status"],
            quality_result["overall_score"],
            json.dumps(quality_result),
        ),
    )
    await db.commit()

    logger.info(
        f"Image uploaded: {image_id} for session {session_id}, quality: {quality_result['overall_status']}"
    )

    return {
        "image_id": image_id,
        "session_id": session_id,
        "eye_label": eye_label,
        "original_filename": file.filename,
        "quality_status": quality_result["overall_status"],
        "quality_score": quality_result["overall_score"],
        "quality_details": quality_result,
        "preview_url": f"/uploads/{stored_filename}",
    }


@router.delete("/{image_id}")
async def delete_image(
    image_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Remove an uploaded image before analysis."""
    cursor = await db.execute(
        "SELECT * FROM screening_images WHERE image_id = ?", (image_id,)
    )
    image = await cursor.fetchone()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    # Check if already analyzed
    cursor = await db.execute(
        "SELECT * FROM screening_results WHERE image_id = ?", (image_id,)
    )
    if await cursor.fetchone():
        raise HTTPException(
            status_code=400,
            detail="Cannot delete an image that has already been analyzed",
        )

    # Delete file
    try:
        if os.path.exists(image["file_path"]):
            os.remove(image["file_path"])
    except OSError as e:
        logger.warning(f"Could not delete file {image['file_path']}: {e}")

    await db.execute("DELETE FROM screening_images WHERE image_id = ?", (image_id,))
    await db.commit()

    return {"message": "Image deleted", "image_id": image_id}


@router.get("/session/{session_id}")
async def list_session_images(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all images for a screening session."""
    cursor = await db.execute(
        "SELECT * FROM screening_images WHERE session_id = ? ORDER BY uploaded_at",
        (session_id,),
    )
    rows = await cursor.fetchall()
    import json

    return [
        {
            "image_id": row["image_id"],
            "session_id": row["session_id"],
            "eye_label": row["eye_label"],
            "original_filename": row["original_filename"],
            "quality_status": row["quality_status"],
            "quality_score": row["quality_score"],
            "quality_details": json.loads(row["quality_details"]) if row["quality_details"] else None,
            "preview_url": f"/uploads/{row['stored_filename']}",
        }
        for row in rows
    ]
