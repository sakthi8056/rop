def test_create_patient(client, auth_headers):
    response = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={
            "infant_name": "Test Baby",
            "date_of_birth": "2023-01-01",
            "gestational_age_weeks": 28,
            "birth_weight_grams": 1000,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "patient_id" in data
    assert data["infant_name"] == "Test Baby"


def test_get_patient(client, auth_headers):
    create_res = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={
            "infant_name": "Baby Two",
            "date_of_birth": "2023-02-01",
            "gestational_age_weeks": 26,
            "birth_weight_grams": 800,
        },
    )
    assert create_res.status_code == 201
    patient_id = create_res.json()["patient_id"]

    response = client.get(f"/api/patients/{patient_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["infant_name"] == "Baby Two"


def test_list_patients(client, auth_headers):
    response = client.get("/api/patients/", headers=auth_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


def test_create_patient_with_gender(client, auth_headers):
    # Test Male
    res_male = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={
            "infant_name": "Baby Boy",
            "gender": "Male",
            "date_of_birth": "2023-01-01",
            "gestational_age_weeks": 29,
            "birth_weight_grams": 1100,
        },
    )
    assert res_male.status_code == 201
    male_data = res_male.json()
    assert male_data["gender"] == "Male"

    # Test Female
    res_female = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={
            "infant_name": "Baby Girl",
            "gender": "Female",
            "date_of_birth": "2023-01-01",
            "gestational_age_weeks": 30,
            "birth_weight_grams": 1200,
        },
    )
    assert res_female.status_code == 201
    female_data = res_female.json()
    assert female_data["gender"] == "Female"

    # Test retrieval retains gender
    get_res = client.get(f"/api/patients/{female_data['patient_id']}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["gender"] == "Female"


def test_invalid_gender_rejected(client, auth_headers):
    res_invalid = client.post(
        "/api/patients/",
        headers=auth_headers,
        json={
            "infant_name": "Invalid Gender Baby",
            "gender": "Other",
            "date_of_birth": "2023-01-01",
            "gestational_age_weeks": 30,
            "birth_weight_grams": 1200,
        },
    )
    assert res_invalid.status_code == 422


