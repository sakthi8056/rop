import io
import cv2
import numpy as np
import pytest


def test_create_session(client, auth_headers):
    # Create a patient first
    patient_res = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={"date_of_birth": "2023-01-01", "gestational_age_weeks": 28, "birth_weight_grams": 1000},
    )
    assert patient_res.status_code == 201
    patient_id = patient_res.json()["patient_id"]

    # Start session
    response = client.post(f"/api/screening/start?patient_id={patient_id}", headers=auth_headers)
    assert response.status_code == 200
    assert "session_id" in response.json()
    assert response.json()["status"] == "created"


def test_analyze_empty_session(client, auth_headers):
    # Start session
    patient_res = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={"date_of_birth": "2023-01-01", "gestational_age_weeks": 28, "birth_weight_grams": 1000},
    )
    assert patient_res.status_code == 201
    session_res = client.post(
        f"/api/screening/start?patient_id={patient_res.json()['patient_id']}",
        headers=auth_headers,
    )
    session_id = session_res.json()["session_id"]

    # Analyze without images should fail with 400
    response = client.post(f"/api/screening/{session_id}/analyze", headers=auth_headers)
    assert response.status_code == 400
    assert "No images uploaded" in response.json()["detail"]


def test_complete_screening_workflow(client, auth_headers):
    # 1. Register patient
    patient_res = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={
            "infant_name": "Screening Test Infant",
            "date_of_birth": "2024-01-15",
            "gestational_age_weeks": 29,
            "gestational_age_days": 2,
            "birth_weight_grams": 1150,
            "hospital_name": "General Hospital",
        },
    )
    assert patient_res.status_code == 201
    patient_id = patient_res.json()["patient_id"]

    # 2. Start screening session
    session_res = client.post(
        f"/api/screening/start?patient_id={patient_id}",
        headers=auth_headers,
    )
    assert session_res.status_code == 200
    session_id = session_res.json()["session_id"]

    # 3. Create synthetic retinal image in memory
    img = np.full((300, 300, 3), 100, dtype=np.uint8)
    cv2.circle(img, (150, 150), 70, (80, 140, 220), -1)
    _, img_bytes = cv2.imencode(".jpg", img)

    # Upload image
    upload_res = client.post(
        f"/api/images/upload/{session_id}",
        headers=auth_headers,
        files={"file": ("test_retina.jpg", io.BytesIO(img_bytes.tobytes()), "image/jpeg")},
        data={"eye_label": "left"},
    )
    assert upload_res.status_code == 200
    upload_data = upload_res.json()
    assert upload_data["quality_status"] in ["ACCEPTABLE", "POOR"]

    # 4. Run analysis
    analyze_res = client.post(f"/api/screening/{session_id}/analyze", headers=auth_headers)
    assert analyze_res.status_code == 200
    analyze_data = analyze_res.json()
    assert "results" in analyze_data
    assert len(analyze_data["results"]) == 1

    # 5. Fetch results
    results_res = client.get(f"/api/screening/{session_id}/results", headers=auth_headers)
    assert results_res.status_code == 200
    results_data = results_res.json()
    assert results_data["session"]["session_id"] == session_id
    assert len(results_data["results"]) == 1
    result = results_data["results"][0]
    from config import get_settings
    settings = get_settings()
    if settings.is_model_available:
        assert result["is_demo"] is False
        assert result["classification"] in settings.MODEL_CLASS_LABELS
        assert result["confidence"] is not None
        assert 0.0 <= result["confidence"] <= 1.0
    else:
        assert result["is_demo"] is True
        assert "DEMO" in result["classification"]

    # 6. Generate report
    report_res = client.post(f"/api/reports/generate/{session_id}", headers=auth_headers)
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert "report_id" in report_data
    assert report_data["format"] in ["pdf", "html"]

    # 7. Check history includes the screening session
    history_res = client.get("/api/history", headers=auth_headers)
    assert history_res.status_code == 200
    history_list = history_res.json()
    session_ids = [s["session_id"] for s in history_list]
    assert session_id in session_ids

