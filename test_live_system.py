import urllib.request
import json
import uuid

def main():
    print("==========================================================")
    print("LIVE SYSTEM END-TO-END VALIDATION (FRONTEND + BACKEND)")
    print("==========================================================")

    # 1. Check frontend is serving
    res_fe = urllib.request.urlopen("http://localhost:5173/")
    print(f"[PASS] Frontend HTTP status: {res_fe.status}")
    html_content = res_fe.read().decode('utf-8')
    assert '<div id="root">' in html_content or 'ROP AI Screener' in html_content
    print("[PASS] Frontend is running and serving Vite application bundle")

    # 2. Check backend health
    res_be = urllib.request.urlopen("http://127.0.0.1:8000/api/health")
    health_data = json.loads(res_be.read().decode())
    print(f"[PASS] Backend Health HTTP status: {res_be.status}, status: {health_data.get('status')}")

    # 3. Authenticate to backend
    login_payload = json.dumps({"username": "admin", "password": "rop2024"}).encode()
    req_login = urllib.request.Request(
        "http://127.0.0.1:8000/api/auth/login",
        data=login_payload,
        headers={"Content-Type": "application/json"}
    )
    token_data = json.loads(urllib.request.urlopen(req_login).read().decode())
    token = token_data["access_token"]
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    print("[PASS] Authenticated successfully as admin, obtained JWT token")

    # 4. Check next-id endpoint
    req_next_id = urllib.request.Request("http://127.0.0.1:8000/api/patients/next-id", headers=headers)
    next_id_data = json.loads(urllib.request.urlopen(req_next_id).read().decode())
    generated_id = next_id_data["patient_id"]
    print(f"[PASS] Auto-generated Next Patient ID: {generated_id}")

    # 5. Register patient with all new fields
    patient_payload = {
        "infant_name": "Baby of Priya Live",
        "gender": "Female",
        "mother_name": "Priya Sundaram",
        "father_name": "Sundaram Raman",
        "date_of_birth": "2026-08-28",
        "gestational_age_weeks": 30,
        "gestational_age_days": 2,
        "birth_weight_grams": 1250,
        "hospital_name": "City Maternity Hospital",
        "city_town_village": "Coimbatore",
        "contact_number": "9876543210",
        "clinical_notes": "Preterm infant on 5 days oxygen therapy"
    }
    req_reg = urllib.request.Request(
        f"http://127.0.0.1:8000/api/patients/?patient_id={generated_id}",
        data=json.dumps(patient_payload).encode(),
        headers=headers
    )
    patient_res = json.loads(urllib.request.urlopen(req_reg).read().decode())
    assert patient_res.get("gender") == "Female", f"Expected gender 'Female', got {patient_res.get('gender')}"
    print(f"[PASS] Registered patient: {patient_res['patient_id']}, Name: {patient_res.get('infant_name')}, Gender: {patient_res.get('gender')}, Mother: {patient_res['mother_name']}")

    # 6. Start Screening Session (Save & Continue workflow)
    session_payload = {
        "patient_id": patient_res["patient_id"],
        "notes": "Pre-discharge baseline ROP screening"
    }
    req_sess = urllib.request.Request(
        "http://127.0.0.1:8000/api/screening/start",
        data=json.dumps(session_payload).encode(),
        headers=headers
    )
    sess_res = json.loads(urllib.request.urlopen(req_sess).read().decode())
    session_id = sess_res["session_id"]
    print(f"[PASS] Initiated screening session: {session_id}")

    # 7. Upload Retinal Fundus Scan
    with open("test_fundus.jpg", "rb") as f:
        img_bytes = f.read()

    boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="test_fundus.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + img_bytes + (
        f"\r\n--{boundary}\r\n"
        f'Content-Disposition: form-data; name="eye_label"\r\n\r\n'
        f"right\r\n--{boundary}--\r\n"
    ).encode()

    req_upload = urllib.request.Request(
        f"http://127.0.0.1:8000/api/images/upload/{session_id}",
        data=body,
        headers={"Authorization": f"Bearer {token}", "Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    upload_res = json.loads(urllib.request.urlopen(req_upload).read().decode())
    print(f"[PASS] Uploaded retinal image. ID: {upload_res['image_id']}, Image Quality: {upload_res.get('quality_status')}")

    # 8. Analyze Screening & Compute Canonical Result
    req_analyze = urllib.request.Request(
        f"http://127.0.0.1:8000/api/screening/{session_id}/analyze",
        data=b"{}",
        headers=headers
    )
    result_res = json.loads(urllib.request.urlopen(req_analyze).read().decode())
    first_res = result_res["results"][0]
    print("[PASS] AI Inference and Canonical Analysis Completed:")
    print(f"       Canonical Status:      {first_res['canonical_status']}")
    print(f"       Classification:        {first_res['classification']}")
    print(f"       Severity:              {first_res['severity']}")
    print(f"       Plus Disease Status:   {first_res['plus_disease_status']}")
    print(f"       Image Quality:         {first_res['quality_status']}")
    print(f"       Confidence:            {first_res['confidence']:.3f} (Is Demo: {first_res.get('is_demo', False)})")
    print(f"       Clinical Action:       {first_res['recommendation']['recommendation']}")

    # 9. Test PDF Report Generation & Download
    req_pdf = urllib.request.Request(
        f"http://127.0.0.1:8000/api/reports/generate/{session_id}?language=en",
        data=b"{}",
        headers=headers
    )
    pdf_meta = json.loads(urllib.request.urlopen(req_pdf).read().decode())
    print(f"[PASS] PDF report generated. ID: {pdf_meta['report_id']}, Format: {pdf_meta['format']}")

    req_download = urllib.request.Request(
        f"http://127.0.0.1:8000/api/reports/download/{pdf_meta['report_id']}",
        headers=headers
    )
    with urllib.request.urlopen(req_download) as resp:
        content_type = resp.headers.get("Content-Type")
        pdf_bytes = resp.read()
        print(f"[PASS] Downloaded report file: {len(pdf_bytes)} bytes, Content-Type: {content_type}")
        assert pdf_bytes.startswith(b"%PDF-"), "Downloaded file is NOT a valid PDF!"
        print("[PASS] Verified binary header: %PDF- (Genuine PDF Document)")

    # 10. Edit Patient Info
    update_payload = {
        "contact_number": "9123456780",
        "clinical_notes": "Updated: Infant stable, ophthalmology follow-up booked"
    }
    req_update = urllib.request.Request(
        f"http://127.0.0.1:8000/api/patients/{patient_res['patient_id']}",
        data=json.dumps(update_payload).encode(),
        headers=headers,
        method="PUT"
    )
    up_res = json.loads(urllib.request.urlopen(req_update).read().decode())
    assert up_res["contact_number"] == "9123456780"
    print(f"[PASS] Patient info successfully updated. Contact: {up_res['contact_number']}")

    # 11. Edit Screening Session Notes
    sess_update = {"notes": "Follow-up screening scheduled at 35 weeks"}
    req_s_up = urllib.request.Request(
        f"http://127.0.0.1:8000/api/screening/{session_id}",
        data=json.dumps(sess_update).encode(),
        headers=headers,
        method="PUT"
    )
    s_up_res = json.loads(urllib.request.urlopen(req_s_up).read().decode())
    assert s_up_res["notes"] == "Follow-up screening scheduled at 35 weeks"
    print(f"[PASS] Screening session notes updated: {s_up_res['notes']}")

    # 12. Soft-delete Screening Record with Confirmation
    req_del = urllib.request.Request(
        f"http://127.0.0.1:8000/api/screening/{session_id}?confirm=true",
        headers=headers,
        method="DELETE"
    )
    del_res = json.loads(urllib.request.urlopen(req_del).read().decode())
    print(f"[PASS] Screening record safely soft-deleted with explicit confirmation: {del_res['message']}")

    # 13. Verify Screening History excludes soft-deleted records
    req_history = urllib.request.Request(
        f"http://127.0.0.1:8000/api/history?patient_id={patient_res['patient_id']}",
        headers=headers
    )
    hist_data = json.loads(urllib.request.urlopen(req_history).read().decode())
    assert len(hist_data) == 0, f"Soft-deleted session should not appear in history! Found: {hist_data}"
    print("[PASS] Screening history correctly excludes deleted records")

    print("\n==========================================================")
    print("ALL 13 END-TO-END VALIDATIONS PASSED PERFECTLY!")
    print("==========================================================")

if __name__ == "__main__":
    main()
