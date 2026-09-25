def test_login_success(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "rop2024"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["user"]["username"] == "admin"
    assert response.json()["user"]["role"] == "doctor"


def test_login_failure(client):
    response = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrongpassword"},
    )
    assert response.status_code == 401


def test_me_authenticated(client, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "admin"
    assert data["full_name"] == "Dr. Demo User"


def test_me_unauthenticated(client):
    response = client.get("/api/auth/me")
    assert response.status_code in [401, 403]

