"""
Pydantic models for report generation.
"""

from pydantic import BaseModel
from typing import Optional


class ReportGenerateRequest(BaseModel):
    language: str = "en"  # "en" or "ta"


class ReportResponse(BaseModel):
    report_id: str
    session_id: str
    language: str
    preview_url: str
    download_url: str
    generated_at: str
