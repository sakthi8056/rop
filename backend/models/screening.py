"""
Pydantic models for screening sessions and results.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ScreeningSessionCreate(BaseModel):
    patient_id: str
    screening_date: Optional[str] = None  # defaults to today
    notes: Optional[str] = None


class ScreeningSessionUpdate(BaseModel):
    screening_date: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class ScreeningSessionResponse(BaseModel):
    id: int
    session_id: str
    patient_id: str
    screening_date: str
    status: str
    notes: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None


class ImageUploadResponse(BaseModel):
    image_id: str
    session_id: str
    eye_label: str
    original_filename: str
    quality_status: str
    quality_score: Optional[float] = None
    quality_details: Optional[dict] = None
    preview_url: str


class QualityCheckResult(BaseModel):
    overall_status: str  # ACCEPTABLE, POOR, UNGRADABLE
    overall_score: float
    is_acceptable: bool
    checks: dict  # individual check results
    message: str


class ScreeningResultResponse(BaseModel):
    result_id: str
    session_id: str
    image_id: str
    classification: Optional[str] = None
    canonical_status: Optional[str] = None
    severity: Optional[str] = None
    plus_disease_status: Optional[str] = None
    quality_status: Optional[str] = None
    confidence: Optional[float] = None
    probabilities: Optional[dict] = None
    is_demo: bool = False
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    status: str
    heatmap_url: Optional[str] = None
    overlay_url: Optional[str] = None
    recommendation: Optional[str] = None
    recommendation_urgency: Optional[str] = None
    screening_limitations: Optional[str] = None
    analyzed_at: Optional[str] = None


class FullScreeningResult(BaseModel):
    session: ScreeningSessionResponse
    patient: dict
    images: list[ImageUploadResponse]
    results: list[ScreeningResultResponse]
    overall_status: str
    canonical_status: Optional[str] = None
    is_demo: bool
