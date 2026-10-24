import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-that-is-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite:///./ultron-tests.db")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_register_login_and_task_xp_once():
    email = f"student-{uuid.uuid4().hex}@example.com"
    password = "correct-horse-battery-staple"
    registered = client.post("/auth/register", json={
        "email": email, "display_name": "Test Student", "password": password
    })
    assert registered.status_code == 201
    assert registered.json()["email_verified"] is False

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    created = client.post("/tasks", headers=headers, json={"title": "Revise algebra"})
    assert created.status_code == 201
    task_id = created.json()["id"]
    first = client.post(f"/tasks/{task_id}/complete", headers=headers)
    second = client.post(f"/tasks/{task_id}/complete", headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["total_xp"] == 10
    assert second.json()["total_xp"] == 10


def test_bad_utr_rejected():
    email = f"utr-{uuid.uuid4().hex}@example.com"
    password = "correct-horse-battery-staple"
    client.post("/auth/register", json={
        "email": email, "display_name": "UTR Test", "password": password
    })
    login = client.post("/auth/login", json={"email": email, "password": password})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post("/payments/upi-claims", headers=headers, json={
        "plan": "basic", "utr": "123", "amount_paise": 9900
    })
    assert response.status_code == 422



def test_google_login_requires_server_client_id(monkeypatch):
    import main
    monkeypatch.setattr(main, "GOOGLE_CLIENT_ID", "")
    response = client.post("/auth/google", json={"credential": "x" * 30})
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_google_login_creates_verified_student(monkeypatch):
    import main
    monkeypatch.setattr(main, "GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    monkeypatch.setattr(main.google_id_token, "verify_oauth2_token", lambda *args, **kwargs: {
        "iss": "https://accounts.google.com",
        "aud": "test-client-id.apps.googleusercontent.com",
        "email": "google-student@example.com",
        "email_verified": True,
        "name": "Google Student",
        "sub": "google-subject-test",
    })
    monkeypatch.setattr(main.google_requests, "Request", lambda: object())
    response = client.post("/auth/google", json={"credential": "fake-credential-for-test-only"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["email"] == "google-student@example.com"
    assert payload["user"]["email_verified"] is True
    assert payload["user"]["role"] == "student"
    assert payload["access_token"]
