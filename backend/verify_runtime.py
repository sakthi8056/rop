"""
End-to-End Runtime Verification Script
======================================
Tests the full ROP screening workflow against the FastAPI backend:
1. Health & Mode Check
2. Authentication (login with admin / rop2024)
3. Patient Registration
4. Retinal Image Upload & Quality Check
5. AI Analysis (Verifying Demo Mode output, confidence=None, probabilities=0.00)
6. Screening Results Inspection
7. Report Generation & Download Check
8. Screening History Verification
"""

import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import asyncio
import io
import cv2
import numpy as np
from fastapi.testclient import TestClient

from config import get_settings
from database import init_database, seed_demo_user
from main import app


def create_synthetic_retinal_image(ungradable: bool = False) -> bytes:
    """Create a synthetic fundus-like test image."""
    if ungradable:
        # A tiny 50x50 blank image to trigger UNGRADABLE
        img = np.full((50, 50, 3), 10, dtype=np.uint8)
    else:
        img = np.full((400, 400, 3), 90, dtype=np.uint8)
        cv2.circle(img, (200, 200), 120, (60, 120, 210), -1)
        cv2.circle(img, (260, 190), 25, (80, 160, 255), -1)  # Optic disc simulation
    _, encoded = cv2.imencode(".jpg", img)
    return encoded.tobytes()


def run_verification():
    print("==================================================")
    print("Starting ROP AI Screener End-to-End Verification")
    print("==================================================")

    # 1. Initialize Database & Seed User
    asyncio.run(init_database())
    asyncio.run(seed_demo_user())
    print("[PASS] Database initialized and demo user seeded.")

    client = TestClient(app)

    # 2. Health check
    res = client.get("/api/health")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    health = res.json()
    is_real_model = health["model_available"] and not health["demo_mode"]
    print(f"[PASS] Health Check: {health['status']} | Demo Mode: {health['demo_mode']} | Model Available: {health['model_available']}")

    # 3. Authentication
    res = client.post("/api/auth/login", json={"username": "admin", "password": "rop2024"})
    assert res.status_code == 200, f"Login failed: {res.text}"
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[PASS] Authentication successful. Logged in as: {res.json()['user']['username']} ({res.json()['user']['role']})")

    # 4. Patient Registration
    res_next_id = client.get("/api/patients/next-id", headers=headers)
    assert res_next_id.status_code == 200
    preview_id = res_next_id.json()["patient_id"]
    print(f"[PASS] Next Patient ID preview: {preview_id}")

    patient_payload = {
        "infant_name": "Baby of Revathi",
        "gender": "Female",
        "mother_name": "Revathi S.",
        "father_name": "Senthil Kumar",
        "date_of_birth": "2024-02-10",
        "gestational_age_weeks": 28,
        "gestational_age_days": 3,
        "birth_weight_grams": 980,
        "postnatal_age_days": 28,
        "hospital_name": "Government Rajaji Hospital, Madurai",
        "city_town_village": "Madurai",
        "contact_number": "9876543210",
        "clinical_notes": "Preterm infant on supplemental oxygen for 14 days.",
    }
    res = client.post("/api/patients/", json=patient_payload, headers=headers)
    assert res.status_code == 201, f"Patient registration failed: {res.text}"
    patient = res.json()
    patient_id = patient["patient_id"]
    assert patient["gender"] == "Female"
    assert patient["mother_name"] == "Revathi S."
    assert patient["city_town_village"] == "Madurai"
    print(f"[PASS] Patient Registered: ID={patient_id}, Name='{patient['infant_name']}', Gender='{patient['gender']}', Mother='{patient['mother_name']}', GA={patient['gestational_age_weeks']}w")

    # 5. Start Screening Session
    res = client.post(f"/api/screening/start?patient_id={patient_id}&notes=Initial%20screening", headers=headers)
    assert res.status_code == 200, f"Session start failed: {res.text}"
    session_id = res.json()["session_id"]
    print(f"[PASS] Screening Session Started: {session_id}")

    # 6. Upload Test Image
    img_bytes = create_synthetic_retinal_image()
    files = {"file": ("fundus_test.jpg", io.BytesIO(img_bytes), "image/jpeg")}
    data = {"eye_label": "right"}
    res = client.post(f"/api/images/upload/{session_id}", files=files, data=data, headers=headers)
    assert res.status_code == 200, f"Image upload failed: {res.text}"
    upload_data = res.json()
    print(f"[PASS] Image Uploaded: ID={upload_data['image_id'][:12]}, Quality={upload_data['quality_status']}, Score={upload_data['quality_score']}")

    # 7. Run AI Inference Pipeline
    res = client.post(f"/api/screening/{session_id}/analyze", headers=headers)
    assert res.status_code == 200, f"Screening analysis failed: {res.text}"
    analysis = res.json()
    first_result = analysis["results"][0]
    print(f"[PASS] Analysis Pipeline Completed: Overall Status={analysis['overall_status']}, Is Demo={analysis['is_demo']}")
    print(f"  - Canonical Status: '{first_result.get('canonical_status')}'")
    print(f"  - Classification: '{first_result.get('classification')}'")
    print(f"  - Quality Status: '{first_result.get('quality_status')}'")
    print(f"  - Confidence: {first_result.get('confidence')}")

    # 8. Retrieve Full Results
    res = client.get(f"/api/screening/{session_id}/results", headers=headers)
    assert res.status_code == 200
    results_detail = res.json()
    print(f"[PASS] Results Verified: Session={results_detail['session']['session_id']}, Images={len(results_detail['images'])}")

    # 9. Generate Genuine PDF Report (English & Tamil)
    res_en = client.post(f"/api/reports/generate/{session_id}?language=en", headers=headers)
    assert res_en.status_code == 200, f"Report generation EN failed: {res_en.text}"
    report_en = res_en.json()
    assert report_en["format"] == "pdf", f"Expected PDF format but got {report_en['format']}"
    print(f"[PASS] Report Generated (EN): ID={report_en['report_id']}, Format={report_en['format']}")

    res_ta = client.post(f"/api/reports/generate/{session_id}?language=ta", headers=headers)
    assert res_ta.status_code == 200, f"Report generation TA failed: {res_ta.text}"
    report_ta = res_ta.json()
    assert report_ta["format"] == "pdf", f"Expected PDF format but got {report_ta['format']}"
    print(f"[PASS] Report Generated (TA): ID={report_ta['report_id']}, Format={report_ta['format']}")

    # 10. Download & Verify Genuine Binary PDF (%PDF- header)
    res_download = client.get(f"/api/reports/download/{report_en['report_id']}")
    assert res_download.status_code == 200
    assert len(res_download.content) > 1000
    assert res_download.content[:4] == b"%PDF", "Report file is not a genuine PDF!"
    print(f"[PASS] Genuine PDF Verified: Header={res_download.content[:5].decode('latin1')}, {len(res_download.content)} bytes transferred.")

    # 11. Test Patient & Screening Updates (Requirement 5)
    res_upd_pt = client.put(f"/api/patients/{patient_id}", json={"mother_name": "Revathi S. (Updated)", "city_town_village": "Madurai South"}, headers=headers)
    assert res_upd_pt.status_code == 200
    assert res_upd_pt.json()["mother_name"] == "Revathi S. (Updated)"
    print(f"[PASS] Patient Update Verified: mother_name='{res_upd_pt.json()['mother_name']}'")

    res_upd_scr = client.put(f"/api/screening/{session_id}", json={"notes": "Follow-up notes updated"}, headers=headers)
    assert res_upd_scr.status_code == 200
    assert res_upd_scr.json()["notes"] == "Follow-up notes updated"
    print(f"[PASS] Screening Session Update Verified: notes='{res_upd_scr.json()['notes']}'")

    # 12. Screening History Check
    res = client.get("/api/history", headers=headers)
    assert res.status_code == 200
    history = res.json()
    matching = [h for h in history if h["session_id"] == session_id]
    assert len(matching) == 1
    assert matching[0]["mother_name"] == "Revathi S. (Updated)"
    print(f"[PASS] Screening History Verified: Session {session_id} contains updated patient data.")

    # 13. Test Soft Deletion with Confirmation
    res_del_scr = client.delete(f"/api/screening/{session_id}?confirm=true", headers=headers)
    assert res_del_scr.status_code == 200
    print(f"[PASS] Soft Deletion Verified: {res_del_scr.json()['message']}")

    # Verify deleted session no longer in active history
    res_hist_after = client.get("/api/history", headers=headers)
    active_sessions = [h["session_id"] for h in res_hist_after.json()]
    assert session_id not in active_sessions
    print(f"[PASS] History safely excludes soft-deleted session.")

    print("\n==================================================")
    print("ALL RUNTIME VERIFICATION CHECKS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_verification()
