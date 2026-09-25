from services.pdf_generator import generate_pdf_report
import os

def test_pdf_generation_fallback(tmp_path):
    # Test that PDF generation falls back to HTML correctly or writes a file
    session_data = {"session_id": "TEST_SESSION", "screening_date": "2023-01-01"}
    patient_data = {"patient_id": "P_001", "infant_name": "Test Baby"}
    images = []
    results = [{"classification": "Normal", "is_demo": True}]
    
    report_id, file_path = generate_pdf_report(session_data, patient_data, images, results, language="en")
    
    assert report_id.startswith("RPT-")
    assert os.path.exists(file_path)
    assert file_path.endswith(".pdf") or file_path.endswith(".html")

