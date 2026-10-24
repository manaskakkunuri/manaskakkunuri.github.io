import asyncio
import os
import sys
import uuid
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-only-secret-key-that-is-at-least-32-characters-long")
os.environ.setdefault("DATABASE_URL", "sqlite:///./ultron-tests.db")
os.environ.setdefault("ALLOWED_ORIGINS", "http://localhost:3000")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
import main
import features

client = TestClient(main.app)


def create_student_token():
    email = f"features-{uuid.uuid4().hex}@example.com"
    password = "correct-horse-battery-staple"
    registered = client.post("/auth/register", json={
        "email": email, "display_name": "Feature Test", "password": password
    })
    assert registered.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_subscription_plans_are_public_and_correct():
    response = client.get("/subscriptions/plans")
    assert response.status_code == 200
    payload = response.json()
    assert payload["plans"]["basic"]["price_inr"] == 99
    assert payload["plans"]["pro"]["price_inr"] == 299


def test_ai_endpoint_returns_first_successful_provider(monkeypatch):
    async def fast_tinyfish(prompt, mode):
        await asyncio.sleep(0.01)
        return "TinyFish source-backed answer"

    async def slower_gemini(prompt, mode):
        await asyncio.sleep(0.20)
        return "Gemini answer"

    monkeypatch.setattr(features, "tinyfish_answer", fast_tinyfish)
    monkeypatch.setattr(features, "gemini_answer", slower_gemini)
    response = client.post("/ai/answer", headers=create_student_token(), json={
        "mode": "doubt", "prompt": "Explain fractions"
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "tinyfish"
    assert payload["answer"] == "TinyFish source-backed answer"
    assert payload["elapsed_ms"] >= 0
    assert payload["usage"]["daily_limit"] == 20


def test_admin_overview_denies_regular_students():
    response = client.get("/admin/overview", headers=create_student_token())
    assert response.status_code == 403


def test_image_generation_requires_backend_key(monkeypatch):
    monkeypatch.setattr(features, "GEMINI_API_KEY", "")
    response = client.post("/images/generate", headers=create_student_token(), json={
        "prompt": "A clear water cycle diagram for grade eight"
    })
    assert response.status_code == 503



def test_ai_falls_back_when_tinyfish_fails(monkeypatch):
    async def failing_tinyfish(prompt, mode):
        await asyncio.sleep(0.01)
        raise RuntimeError("TinyFish unavailable")

    async def working_gemini(prompt, mode):
        await asyncio.sleep(0.03)
        return "Gemini fallback answer"

    monkeypatch.setattr(features, "tinyfish_answer", failing_tinyfish)
    monkeypatch.setattr(features, "gemini_answer", working_gemini)
    response = client.post("/ai/answer", headers=create_student_token(), json={
        "mode": "summary", "prompt": "Summarize photosynthesis"
    })
    assert response.status_code == 200
    assert response.json()["provider"] == "google_ai_studio"
    assert response.json()["answer"] == "Gemini fallback answer"
