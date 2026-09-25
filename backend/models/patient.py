"""
Pydantic models for patient registration.
"""

import re
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import date


class PatientCreate(BaseModel):
    infant_name: Optional[str] = Field(None, max_length=200, description="Baby's Name")
    gender: Optional[str] = Field(None, max_length=20, description="Gender ('Male' or 'Female')")
    mother_name: Optional[str] = Field(None, max_length=200, description="Mother's Name")
    father_name: Optional[str] = Field(None, max_length=200, description="Father's Name")
    date_of_birth: str = Field(..., description="Date of birth in YYYY-MM-DD format")
    gestational_age_weeks: int = Field(..., ge=22, le=42, description="Gestational age in weeks (22–42)")
    gestational_age_days: int = Field(default=0, ge=0, le=6, description="Additional days (0–6)")
    birth_weight_grams: int = Field(..., ge=200, le=5000, description="Birth weight in grams (200–5000)")
    postnatal_age_days: Optional[int] = Field(None, ge=0)
    hospital_name: Optional[str] = Field(None, max_length=300, description="Hospital or Screening Center Name")
    city_town_village: Optional[str] = Field(None, max_length=200, description="Village, Town, or City")
    contact_number: Optional[str] = Field(None, max_length=30, description="Parent or Guardian Contact Number")
    clinical_history: Optional[str] = Field(None, max_length=2000)
    clinical_notes: Optional[str] = Field(None, max_length=2000, description="Relevant Clinical Notes")
    healthcare_worker_name: Optional[str] = Field(None, max_length=200)
    healthcare_worker_id: Optional[str] = Field(None, max_length=100)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is not None and v.strip():
            if v.strip() not in ("Male", "Female"):
                raise ValueError("Gender must be either 'Male' or 'Female'")
            return v.strip()
        return None

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v):
        try:
            dob = date.fromisoformat(v)
            if dob > date.today():
                raise ValueError("Date of birth cannot be in the future")
            return v
        except ValueError as e:
            if "cannot be in the future" in str(e):
                raise
            raise ValueError("Invalid date format. Use YYYY-MM-DD")

    @field_validator("contact_number")
    @classmethod
    def validate_contact_number(cls, v):
        if v is not None and v.strip():
            digits = re.sub(r"[^\d]", "", v)
            if len(digits) < 7 or len(digits) > 15:
                raise ValueError("Contact number must contain between 7 and 15 digits")
            return v.strip()
        return None


class PatientUpdate(BaseModel):
    infant_name: Optional[str] = Field(None, max_length=200)
    gender: Optional[str] = Field(None, max_length=20)
    mother_name: Optional[str] = Field(None, max_length=200)
    father_name: Optional[str] = Field(None, max_length=200)
    date_of_birth: Optional[str] = None
    gestational_age_weeks: Optional[int] = Field(None, ge=22, le=42)
    gestational_age_days: Optional[int] = Field(None, ge=0, le=6)
    birth_weight_grams: Optional[int] = Field(None, ge=200, le=5000)
    postnatal_age_days: Optional[int] = Field(None, ge=0)
    hospital_name: Optional[str] = Field(None, max_length=300)
    city_town_village: Optional[str] = Field(None, max_length=200)
    contact_number: Optional[str] = Field(None, max_length=30)
    clinical_history: Optional[str] = Field(None, max_length=2000)
    clinical_notes: Optional[str] = Field(None, max_length=2000)
    healthcare_worker_name: Optional[str] = Field(None, max_length=200)
    healthcare_worker_id: Optional[str] = Field(None, max_length=100)

    @field_validator("gender")
    @classmethod
    def validate_gender(cls, v):
        if v is not None and v.strip():
            if v.strip() not in ("Male", "Female"):
                raise ValueError("Gender must be either 'Male' or 'Female'")
            return v.strip()
        return v

    @field_validator("date_of_birth")
    @classmethod
    def validate_date_of_birth(cls, v):
        if v is not None:
            try:
                dob = date.fromisoformat(v)
                if dob > date.today():
                    raise ValueError("Date of birth cannot be in the future")
                return v
            except ValueError as e:
                if "cannot be in the future" in str(e):
                    raise
                raise ValueError("Invalid date format. Use YYYY-MM-DD")
        return v

    @field_validator("contact_number")
    @classmethod
    def validate_contact_number(cls, v):
        if v is not None and v.strip():
            digits = re.sub(r"[^\d]", "", v)
            if len(digits) < 7 or len(digits) > 15:
                raise ValueError("Contact number must contain between 7 and 15 digits")
            return v.strip()
        return v


class PatientResponse(BaseModel):
    id: int
    patient_id: str
    infant_name: Optional[str] = None
    gender: Optional[str] = None
    mother_name: Optional[str] = None
    father_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    gestational_age_weeks: Optional[int] = None
    gestational_age_days: Optional[int] = None
    birth_weight_grams: Optional[int] = None
    postnatal_age_days: Optional[int] = None
    hospital_name: Optional[str] = None
    city_town_village: Optional[str] = None
    contact_number: Optional[str] = None
    clinical_history: Optional[str] = None
    clinical_notes: Optional[str] = None
    healthcare_worker_name: Optional[str] = None
    healthcare_worker_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
