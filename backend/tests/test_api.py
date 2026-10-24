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
    response = client.post("/payments/upi-claims", json={
        "plan": "basic", "utr": "123", "amount_paise": 9900
    })
    assert response.status_code == 422
