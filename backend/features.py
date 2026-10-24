"""ULTRON premium features: race-first AI, subscriptions, image studio, and admin APIs."""
from __future__ import annotations

import asyncio
import base64
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, select, func
from sqlalchemy.orm import Mapped, Session, mapped_column

# Imported after main.py has declared its core models and helpers.
from main import (
    Base, SessionLocal, User, PaymentClaim, AuditLog, current_user, get_db,
    payment_reviewer, write_audit, PLAN_AMOUNTS, UPI_ID,
)

router = APIRouter()
TINYFISH_API_KEY = os.getenv("TINYFISH_API_KEY", "").strip()
TINYFISH_SEARCH_URL = os.getenv("TINYFISH_SEARCH_URL", "https://api.search.tinyfish.ai").strip()
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_AI_STUDIO_API_KEY") or "").strip()
GEMINI_TEXT_MODEL = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash").strip()
GEMINI_IMAGE_MODEL = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image").strip()
RECONCILIATION_SECRET = os.getenv("PAYMENT_RECONCILIATION_SECRET", "").strip()
AI_DAILY_LIMITS = {"free": 20, "basic": 250, "pro": 1000}
IMAGE_MONTHLY_LIMITS = {"free": 2, "basic": 15, "pro": 60}
PLAN_DETAILS = {
    "free": {"name": "Free", "price_inr": 0, "ai_daily_limit": 20, "images_monthly": 2},
    "basic": {"name": "Basic", "price_inr": 99, "ai_daily_limit": 250, "images_monthly": 15},
    "pro": {"name": "Pro", "price_inr": 299, "ai_daily_limit": 1000, "images_monthly": 60},
}


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    plan: Mapped[str] = mapped_column(String(20), default="free")
    status: Mapped[str] = mapped_column(String(20), default="active")
    current_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class UsageCounter(Base):
    __tablename__ = "usage_counters"
    __table_args__ = (UniqueConstraint("user_id", "period_key", "kind", name="uq_usage_period"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    period_key: Mapped[str] = mapped_column(String(20), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    count: Mapped[int] = mapped_column(Integer, default=0)


Base.metadata.create_all(bind=SessionLocal.kw["bind"])


class AskIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=12000)
    mode: str = Field(default="doubt", pattern="^(doubt|homework|summary|flashcards|quiz)$")


class ImageIn(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)


class ClaimIn(BaseModel):
    plan: str = Field(pattern="^(basic|pro)$")
    utr: str = Field(pattern=r"^\d{12}$")


def active_plan(db: Session, user_id: int) -> str:
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user_id))
    now = datetime.now(timezone.utc)
    if not sub or sub.status != "active" or sub.current_period_end.replace(tzinfo=timezone.utc) <= now:
        return "free"
    return sub.plan if sub.plan in PLAN_DETAILS else "free"


def use_quota(db: Session, user_id: int, kind: str, limit: int) -> tuple[int, int]:
    now = datetime.now(timezone.utc)
    period_key = now.strftime("%Y-%m") if kind == "image" else now.strftime("%Y-%m-%d")
    row = db.scalar(select(UsageCounter).where(
        UsageCounter.user_id == user_id,
        UsageCounter.period_key == period_key,
        UsageCounter.kind == kind,
    ))
    used = row.count if row else 0
    if used >= limit:
        reset = "next month" if kind == "image" else "tomorrow"
        raise HTTPException(429, f"{kind.title()} limit reached for your {active_plan(db, user_id).title()} plan. Resets {reset}.")
    if row:
        row.count += 1
    else:
        db.add(UsageCounter(user_id=user_id, period_key=period_key, kind=kind, count=1))
    db.commit()
    return used + 1, limit


def parse_tinyfish_answer(payload: object) -> str:
    if isinstance(payload, dict):
        results = payload.get("results") or payload.get("data") or payload.get("organic_results") or []
        if isinstance(results, dict):
            results = results.get("results") or results.get("items") or []
        if isinstance(results, list):
            lines = []
            for item in results[:5]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or item.get("name") or "Web result").strip()
                snippet = str(item.get("snippet") or item.get("description") or item.get("content") or "").strip()
                url = str(item.get("url") or item.get("link") or "").strip()
                if snippet or url:
                    lines.append(f"{title}\n{snippet}\n{url}".strip())
            if lines:
                return "Live web research from TinyFish:\n\n" + "\n\n".join(lines)
        for key in ("answer", "text", "content", "message", "output"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(payload, str) and payload.strip():
        return payload.strip()
    raise RuntimeError("TinyFish returned no usable answer")


async def tinyfish_answer(prompt: str, mode: str) -> str:
    if not TINYFISH_API_KEY:
        raise RuntimeError("TinyFish is not configured")
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=4.0)) as client:
        response = await client.get(
            TINYFISH_SEARCH_URL,
            params={"query": f"{prompt} (student learning, {mode})"},
            headers={"X-API-Key": TINYFISH_API_KEY, "Accept": "application/json"},
        )
        response.raise_for_status()
        return parse_tinyfish_answer(response.json())


async def gemini_answer(prompt: str, mode: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("Google AI Studio is not configured")
    instructions = {
        "doubt": "Explain clearly step by step with an example.",
        "homework": "Guide the student through the solution and explain the method.",
        "summary": "Create a concise, accurate revision summary with headings and key points.",
        "flashcards": "Create useful Q&A flashcards with one card per line.",
        "quiz": "Create a short quiz and put the answer key at the end.",
    }
    body = {
        "system_instruction": {"parts": [{"text": "You are ULTRON, a supportive and accurate school study tutor. " + instructions[mode] + " If uncertain, say so. Format for readability."}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1800},
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=4.0)) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_TEXT_MODEL}:generateContent",
            headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
            json=body,
        )
        response.raise_for_status()
        data = response.json()
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    answer = "\n".join(str(p.get("text", "")) for p in parts if isinstance(p, dict) and p.get("text"))
    if not answer.strip():
        raise RuntimeError("Google AI Studio returned no text")
    return answer.strip()


@router.get("/subscriptions/plans")
def subscription_plans():
    return {"upi_id": UPI_ID, "plans": PLAN_DETAILS}


@router.get("/subscriptions/me")
def my_subscription(db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = active_plan(db, user.id)
    sub = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    now = datetime.now(timezone.utc)
    day_key, month_key = now.strftime("%Y-%m-%d"), now.strftime("%Y-%m")
    ai_row = db.scalar(select(UsageCounter).where(UsageCounter.user_id == user.id, UsageCounter.period_key == day_key, UsageCounter.kind == "ai"))
    image_row = db.scalar(select(UsageCounter).where(UsageCounter.user_id == user.id, UsageCounter.period_key == month_key, UsageCounter.kind == "image"))
    return {
        "plan": plan,
        "status": sub.status if sub and plan != "free" else "active",
        "period_end": sub.current_period_end.isoformat() if sub and plan != "free" else None,
        "usage": {
            "ai_today": ai_row.count if ai_row else 0,
            "ai_daily_limit": AI_DAILY_LIMITS[plan],
            "images_this_month": image_row.count if image_row else 0,
            "images_monthly_limit": IMAGE_MONTHLY_LIMITS[plan],
        },
    }


@router.post("/subscriptions/upi-claims", status_code=201)
def subscription_claim(data: ClaimIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    # A claim is not proof of payment. The subscription remains unchanged until
    # trusted reconciliation and the separately authorized reviewer approve it.
    claim = PaymentClaim(user_id=user.id, plan=data.plan, utr=data.utr,
                         amount_paise=PLAN_AMOUNTS[data.plan], independent_verification=False)
    db.add(claim)
    try:
        db.commit()
        db.refresh(claim)
    except Exception as exc:
        db.rollback()
        if "IntegrityError" in type(exc).__name__:
            raise HTTPException(409, "This UTR has already been submitted")
        raise
    write_audit(db, user.id, "subscription.claim_submitted", "payment_claim", claim.id, f"plan={data.plan}")
    db.commit()
    return {"id": claim.id, "status": "pending", "message": "Claim submitted. Your plan will not change until payment is independently verified and reviewed."}


@router.post("/ai/answer")
async def ai_answer(data: AskIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    plan = active_plan(db, user.id)
    used, limit = use_quota(db, user.id, "ai", AI_DAILY_LIMITS[plan])
    prompt = data.prompt.strip()
    started = time.perf_counter()
    tasks = {
        asyncio.create_task(tinyfish_answer(prompt, data.mode)): "tinyfish",
        asyncio.create_task(gemini_answer(prompt, data.mode)): "google_ai_studio",
    }
    failures = []
    winner = None
    pending = set(tasks)
    try:
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                provider = tasks[task]
                try:
                    answer = task.result()
                    if answer.strip():
                        winner = {"answer": answer, "provider": provider}
                        break
                except Exception as exc:
                    failures.append(f"{provider}: {type(exc).__name__}")
            if winner:
                break
        if not winner:
            raise HTTPException(503, "No AI provider returned a usable answer. Check the backend API keys and provider configuration.")
    finally:
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    write_audit(db, user.id, "ai.answer", "ai_request", None, f"provider={winner['provider']}; elapsed_ms={elapsed_ms}")
    db.commit()
    return {"answer": winner["answer"], "provider": winner["provider"], "elapsed_ms": elapsed_ms,
            "usage": {"used_today": used, "daily_limit": limit, "plan": plan}}


@router.post("/images/generate")
async def generate_image(data: ImageIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not GEMINI_API_KEY:
        raise HTTPException(503, "Image generation is not configured. Set GEMINI_API_KEY on the backend.")
    plan = active_plan(db, user.id)
    used, limit = use_quota(db, user.id, "image", IMAGE_MONTHLY_LIMITS[plan])
    body = {
        "model": GEMINI_IMAGE_MODEL,
        "input": [{"type": "text", "text": "Create a polished, original image based on this prompt. Follow safety rules. Prompt: " + data.prompt.strip()}],
        "response_format": [{"type": "image"}],
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=5.0)) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
                json=body,
            )
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(502, "Google image generation failed. Check the configured model, API access, and billing.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(504, "Image generation timed out or could not connect.") from exc
    image_data = None
    mime_type = "image/png"
    output_image = payload.get("output_image")
    if isinstance(output_image, dict):
        image_data = output_image.get("data")
        mime_type = output_image.get("mime_type") or mime_type
    if not image_data:
        for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
            if isinstance(item, dict) and item.get("type") == "image":
                image_data = item.get("data")
                mime_type = item.get("mime_type") or mime_type
                break
    if not image_data:
        raise HTTPException(502, "The image provider returned no image data.")
    write_audit(db, user.id, "image.generated", "image", None, f"plan={plan}")
    db.commit()
    return {"image_base64": image_data, "mime_type": mime_type, "prompt": data.prompt,
            "usage": {"used_this_month": used, "monthly_limit": limit, "plan": plan}}


def require_admin(user: User = Depends(current_user)) -> User:
    # Allowlist is a restriction only; it never grants a role.
    if user.role != "super_admin" or not user.email_verified or user.email.lower() not in {
        "ashokbharadwaj@gmail.com", "manaskakkunuri55@gmail.com"
    }:
        raise HTTPException(403, "Super Admin access required")
    return user


@router.get("/admin/overview")
def admin_overview(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    now = datetime.now(timezone.utc)
    users = db.scalar(select(func.count(User.id))) or 0
    active_subs = db.scalar(select(func.count(Subscription.id)).where(
        Subscription.plan.in_(["basic", "pro"]), Subscription.status == "active",
        Subscription.current_period_end > now.replace(tzinfo=None))) or 0
    pending = db.scalar(select(func.count(PaymentClaim.id)).where(PaymentClaim.status == "pending")) or 0
    tasks = db.scalar(select(func.count()).select_from(__import__("main").Task)) or 0
    return {"users": users, "active_paid_subscriptions": active_subs, "pending_payment_claims": pending,
            "tasks": tasks, "role": admin.role}


@router.get("/admin/users")
def admin_users(limit: int = 100, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(User).order_by(User.id.desc()).limit(max(1, min(limit, 200)))).all()
    return [{"id": u.id, "email": u.email, "display_name": u.display_name, "role": u.role,
             "email_verified": u.email_verified, "is_active": u.is_active, "xp": u.xp,
             "plan": active_plan(db, u.id)} for u in rows]


@router.post("/ops/payments/{claim_id}/verify")
def independently_verify_payment(
    claim_id: int,
    x_payment_reconciliation_secret: Optional[str] = Header(default=None),
    db: Session = Depends(get_db),
):
    # This is a server-to-server operations hook, never exposed as an admin UI action.
    if not RECONCILIATION_SECRET or not x_payment_reconciliation_secret or not hmac.compare_digest(
        x_payment_reconciliation_secret, RECONCILIATION_SECRET
    ):
        raise HTTPException(403, "Trusted payment reconciliation required")
    claim = db.get(PaymentClaim, claim_id)
    if not claim:
        raise HTTPException(404, "Payment claim not found")
    if claim.status != "pending":
        raise HTTPException(409, "Only pending claims can be verified")
    claim.independent_verification = True
    write_audit(db, None, "payment.independently_verified", "payment_claim", claim.id, "Trusted reconciliation secret")
    db.commit()
    return {"id": claim.id, "independent_verification": True, "next_step": "Authorized reviewer must approve or reject the claim."}


# Wrap the existing review route with subscription activation only after a trusted
# verification flag is present. The original endpoint remains fail-closed; the
# subscription is activated by this explicit approval endpoint.
@router.post("/admin/subscriptions/{claim_id}/approve")
def approve_subscription_claim(
    claim_id: int,
    note: str = "",
    db: Session = Depends(get_db),
    reviewer: User = Depends(payment_reviewer),
):
    claim = db.get(PaymentClaim, claim_id)
    if not claim:
        raise HTTPException(404, "Payment claim not found")
    if claim.status != "pending":
        raise HTTPException(409, "This claim has already been reviewed")
    if not claim.independent_verification:
        raise HTTPException(409, "Independent payment verification is required before approval")
    now = datetime.now(timezone.utc)
    sub = db.scalar(select(Subscription).where(Subscription.user_id == claim.user_id))
    if not sub:
        sub = Subscription(user_id=claim.user_id, plan=claim.plan, status="active",
                           current_period_start=now, current_period_end=now + timedelta(days=30), updated_at=now)
        db.add(sub)
    else:
        sub.plan = claim.plan
        sub.status = "active"
        sub.current_period_start = now
        sub.current_period_end = now + timedelta(days=30)
        sub.updated_at = now
    claim.status = "approved"
    claim.reviewed_by = reviewer.id
    claim.review_note = note.strip()[:500] or None
    claim.reviewed_at = now
    write_audit(db, reviewer.id, "subscription.activated", "subscription", claim.user_id, f"plan={claim.plan}; claim_id={claim.id}")
    db.commit()
    return {"claim_id": claim.id, "status": "approved", "subscription_activated": True,
            "user_id": claim.user_id, "plan": claim.plan, "period_end": sub.current_period_end.isoformat()}


@router.get("/admin/subscriptions")
def admin_subscriptions(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    rows = db.scalars(select(Subscription).order_by(Subscription.updated_at.desc()).limit(200)).all()
    return [{"user_id": s.user_id, "plan": active_plan(db, s.user_id), "status": s.status,
             "period_start": s.current_period_start.isoformat(), "period_end": s.current_period_end.isoformat()}
            for s in rows]
