"""ULTRON API starter. Configure secrets and a persistent database before deployment."""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Generator, Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
if len(SECRET_KEY) < 32:
    raise RuntimeError("Set SECRET_KEY to a random secret of at least 32 characters.")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ultron.db").strip()
TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))
ALLOWED_ORIGINS = [v.strip() for v in os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",") if v.strip()]
UPI_ID = os.getenv("UPI_ID", "shreetulasi@oksbi").strip()
REVIEWER_EMAILS = {"ashokbharadwaj@gmail.com", "manaskakkunuri55@gmail.com"}
PLAN_AMOUNTS = {"basic": 9900, "pro": 29900}
ALGORITHM = "HS256"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
bearer = HTTPBearer(auto_error=False)
app = FastAPI(title="ULTRON API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default="student", index=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    school_id: Mapped[Optional[int]] = mapped_column(ForeignKey("schools.id"), nullable=True, index=True)
    xp: Mapped[int] = mapped_column(Integer, default=0)


class School(Base):
    __tablename__ = "schools"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    academic_year: Mapped[str] = mapped_column(String(30))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class Portal(Base):
    __tablename__ = "portals"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    classes_covered: Mapped[str] = mapped_column(String(200))
    pinned_notice: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"))


class PortalMembership(Base):
    __tablename__ = "portal_memberships"
    __table_args__ = (UniqueConstraint("portal_id", "user_id", name="uq_portal_member"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    membership_role: Mapped[str] = mapped_column(String(20), default="student")


class PortalMessage(Base):
    __tablename__ = "portal_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    portal_id: Mapped[int] = mapped_column(ForeignKey("portals.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    attachment_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    xp_awarded: Mapped[bool] = mapped_column(Boolean, default=False)


class PaymentClaim(Base):
    __tablename__ = "payment_claims"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    plan: Mapped[str] = mapped_column(String(20))
    utr: Mapped[str] = mapped_column(String(12), unique=True, index=True)
    amount_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    independent_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    target_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    detail: Mapped[str] = mapped_column(String(1000), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


Base.metadata.create_all(bind=engine)


class RegisterIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=12, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    display_name: str
    role: str
    email_verified: bool
    school_id: Optional[int]
    xp: int


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class SchoolIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    academic_year: str = Field(min_length=4, max_length=30)


class PortalIn(BaseModel):
    school_id: Optional[int] = None
    name: str = Field(min_length=2, max_length=120)
    classes_covered: str = Field(min_length=1, max_length=200)
    pinned_notice: str = Field(default="", max_length=5000)


class MembershipIn(BaseModel):
    user_id: int
    membership_role: str = Field(default="student", pattern="^(student|teacher|moderator)$")


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    attachment_url: Optional[HttpUrl] = None


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=160)


class PaymentIn(BaseModel):
    plan: str = Field(pattern="^(basic|pro)$")
    utr: str = Field(pattern=r"^\d{12}$")
    amount_paise: int = Field(gt=0, le=100_000_000)

    @field_validator("utr")
    @classmethod
    def validate_utr(cls, value: str) -> str:
        if not re.fullmatch(r"\d{12}", value):
            raise ValueError("UTR must contain exactly 12 digits")
        return value


class ReviewIn(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    note: str = Field(default="", max_length=500)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def password_hash(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000)
    return "pbkdf2_sha256$600000$" + salt.hex() + "$" + digest.hex()


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt_hex, digest_hex = encoded.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(actual.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def issue_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user.id), "iat": int(now.timestamp()),
         "exp": int((now + timedelta(minutes=TOKEN_MINUTES)).timestamp()),
         "jti": secrets.token_urlsafe(16), "iss": "ultron-api", "aud": "ultron-client"},
        SECRET_KEY, algorithm=ALGORITHM,
    )


def current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM],
                             issuer="ultron-api", audience="ultron-client")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, TypeError, ValueError):
        raise HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Account is inactive or unavailable")
    return user


def require_verified(user: User) -> None:
    if not user.email_verified:
        raise HTTPException(403, "Verify your email before using this feature")


def require_school_scope(user: User, school_id: int) -> None:
    if user.role != "super_admin" and user.school_id != school_id:
        raise HTTPException(404, "Resource not found")


def portal_for_user(db: Session, portal_id: int, user: User) -> Portal:
    portal = db.get(Portal, portal_id)
    if not portal:
        raise HTTPException(404, "Portal not found")
    if user.role == "super_admin":
        return portal
    require_school_scope(user, portal.school_id)
    membership = db.scalar(select(PortalMembership).where(
        PortalMembership.portal_id == portal_id, PortalMembership.user_id == user.id))
    if not membership and user.role not in {"school_admin", "principal", "teacher"}:
        raise HTTPException(403, "Portal membership required")
    return portal


def write_audit(db: Session, actor_id: Optional[int], action: str, target: str,
                target_id: Optional[int] = None, detail: str = "") -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, target_type=target,
                    target_id=target_id, detail=detail[:1000]))


def payment_reviewer(user: User = Depends(current_user)) -> User:
    # The allowlist is an extra restriction, never a privilege-granting mechanism.
    if user.email.lower() not in REVIEWER_EMAILS or user.role != "super_admin" or not user.email_verified:
        raise HTTPException(403, "Not authorized to review manual UPI payments")
    return user


@app.get("/health")
def health():
    return {"status": "ok", "service": "ultron-api"}


@app.get("/config/public")
def public_config():
    return {"upi_id": UPI_ID, "plans": {"basic": {"price_inr": 99}, "pro": {"price_inr": 299}}}


@app.post("/auth/register", response_model=UserOut, status_code=201)
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = str(data.email).lower().strip()
    user = User(email=email, display_name=data.display_name.strip(),
                password_hash=password_hash(data.password), role="student",
                email_verified=False, is_active=True)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An account with this email already exists")
    write_audit(db, user.id, "user.registered", "user", user.id, "Email verification required")
    db.commit()
    return user


@app.post("/auth/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == str(data.email).lower().strip()))
    if not user or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return TokenOut(access_token=issue_token(user), expires_in=TOKEN_MINUTES * 60, user=user)


@app.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@app.post("/schools", status_code=201)
def create_school(data: SchoolIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_verified(user)
    if user.role not in {"super_admin", "school_admin", "principal"}:
        raise HTTPException(403, "School administrator role required")
    if user.role != "super_admin" and user.school_id is not None:
        raise HTTPException(409, "Your account already belongs to a school")
    school = School(name=data.name.strip(), academic_year=data.academic_year.strip(), created_by=user.id)
    db.add(school)
    db.flush()
    if user.role != "super_admin":
        user.school_id = school.id
    write_audit(db, user.id, "school.created", "school", school.id, school.name)
    db.commit()
    return {"id": school.id, "name": school.name, "academic_year": school.academic_year}


@app.post("/portals", status_code=201)
def create_portal(data: PortalIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_verified(user)
    if user.role not in {"super_admin", "school_admin", "principal"}:
        raise HTTPException(403, "School administrator role required")
    school_id = data.school_id if user.role == "super_admin" else user.school_id
    if school_id is None or not db.get(School, school_id):
        raise HTTPException(404, "School not found")
    require_school_scope(user, school_id)
    portal = Portal(school_id=school_id, name=data.name.strip(),
                    classes_covered=data.classes_covered.strip(),
                    pinned_notice=data.pinned_notice.strip(), created_by=user.id)
    db.add(portal)
    db.flush()
    write_audit(db, user.id, "portal.created", "portal", portal.id, portal.name)
    db.commit()
    return {"id": portal.id, "school_id": portal.school_id, "name": portal.name,
            "classes_covered": portal.classes_covered, "pinned_notice": portal.pinned_notice}


@app.get("/portals")
def list_portals(db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Portal).order_by(Portal.id.desc()).limit(200)
    if user.role != "super_admin":
        if user.school_id is None:
            return []
        stmt = select(Portal).where(Portal.school_id == user.school_id).order_by(Portal.id.desc()).limit(200)
    return [{"id": p.id, "school_id": p.school_id, "name": p.name,
             "classes_covered": p.classes_covered, "pinned_notice": p.pinned_notice}
            for p in db.scalars(stmt).all()]


@app.post("/portals/{portal_id}/members", status_code=201)
def add_portal_member(portal_id: int, data: MembershipIn, db: Session = Depends(get_db),
                      user: User = Depends(current_user)):
    require_verified(user)
    if user.role not in {"super_admin", "school_admin", "principal", "teacher"}:
        raise HTTPException(403, "School staff role required")
    portal = db.get(Portal, portal_id)
    target = db.get(User, data.user_id)
    if not portal or not target or not target.is_active:
        raise HTTPException(404, "Portal or user not found")
    require_school_scope(user, portal.school_id)
    if target.school_id != portal.school_id:
        raise HTTPException(400, "User must belong to the same school")
    membership = db.scalar(select(PortalMembership).where(
        PortalMembership.portal_id == portal_id, PortalMembership.user_id == target.id))
    if membership:
        membership.membership_role = data.membership_role
    else:
        membership = PortalMembership(portal_id=portal_id, user_id=target.id,
                                      membership_role=data.membership_role)
        db.add(membership)
    write_audit(db, user.id, "portal.member.upserted", "portal", portal.id, f"user_id={target.id}")
    db.commit()
    return {"portal_id": portal_id, "user_id": target.id, "membership_role": membership.membership_role}


@app.get("/portals/{portal_id}/messages")
def list_messages(portal_id: int, limit: int = 50, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    portal = portal_for_user(db, portal_id, user)
    limit = max(1, min(limit, 100))
    rows = db.scalars(select(PortalMessage).where(
        PortalMessage.portal_id == portal.id).order_by(PortalMessage.id.desc()).limit(limit)).all()
    rows.reverse()
    return [{"id": m.id, "portal_id": m.portal_id, "user_id": m.user_id,
             "body": m.body, "attachment_url": m.attachment_url, "created_at": m.created_at}
            for m in rows]


@app.post("/portals/{portal_id}/messages", status_code=201)
def send_message(portal_id: int, data: MessageIn, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    require_verified(user)
    portal = portal_for_user(db, portal_id, user)
    attachment = str(data.attachment_url) if data.attachment_url else None
    if attachment and urlparse(attachment).scheme != "https":
        raise HTTPException(422, "Attachments must use HTTPS")
    message = PortalMessage(portal_id=portal.id, user_id=user.id,
                            body=data.body.strip(), attachment_url=attachment)
    db.add(message)
    db.commit()
    db.refresh(message)
    return {"id": message.id, "portal_id": message.portal_id, "user_id": message.user_id,
            "body": message.body, "attachment_url": message.attachment_url, "created_at": message.created_at}


@app.post("/tasks", status_code=201)
def create_task(data: TaskIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = Task(user_id=user.id, title=data.title.strip())
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"id": task.id, "title": task.title, "completed": task.completed, "xp_awarded": task.xp_awarded}


@app.get("/tasks")
def list_tasks(db: Session = Depends(get_db), user: User = Depends(current_user)):
    tasks = db.scalars(select(Task).where(Task.user_id == user.id).order_by(Task.id.desc()).limit(200)).all()
    return [{"id": t.id, "title": t.title, "completed": t.completed,
             "completed_at": t.completed_at, "xp_awarded": t.xp_awarded} for t in tasks]


@app.post("/tasks/{task_id}/complete")
def complete_task(task_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    task = db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user.id))
    if not task:
        raise HTTPException(404, "Task not found")
    if not task.completed:
        task.completed = True
        task.completed_at = datetime.now(timezone.utc)
        if not task.xp_awarded:
            user.xp += 10
            task.xp_awarded = True
            write_audit(db, user.id, "task.xp_awarded", "task", task.id, "10 XP")
        db.commit()
    return {"id": task.id, "completed": task.completed, "xp_awarded": task.xp_awarded, "total_xp": user.xp}


@app.post("/payments/upi-claims", status_code=201)
def create_payment_claim(data: PaymentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    require_verified(user)
    if data.amount_paise != PLAN_AMOUNTS[data.plan]:
        raise HTTPException(422, "Amount does not match selected plan")
    claim = PaymentClaim(user_id=user.id, plan=data.plan, utr=data.utr,
                         amount_paise=data.amount_paise, independent_verification=False)
    db.add(claim)
    try:
        db.commit()
        db.refresh(claim)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This UTR has already been submitted")
    write_audit(db, user.id, "payment.claim_submitted", "payment_claim", claim.id, f"plan={claim.plan}")
    db.commit()
    return {"id": claim.id, "status": claim.status,
            "message": "Claim received; subscription remains inactive until independent verification."}


@app.get("/admin/payments")
def admin_payments(status_filter: str = "pending", limit: int = 100, db: Session = Depends(get_db),
                   reviewer: User = Depends(payment_reviewer)):
    if status_filter not in {"pending", "approved", "rejected", "all"}:
        raise HTTPException(422, "Invalid status filter")
    stmt = select(PaymentClaim)
    if status_filter != "all":
        stmt = stmt.where(PaymentClaim.status == status_filter)
    rows = db.scalars(stmt.order_by(PaymentClaim.id.desc()).limit(max(1, min(limit, 200)))).all()
    return [{"id": c.id, "user_id": c.user_id, "plan": c.plan, "utr": c.utr,
             "amount_paise": c.amount_paise, "status": c.status,
             "independent_verification": c.independent_verification,
             "created_at": c.created_at, "reviewed_by": c.reviewed_by, "review_note": c.review_note}
            for c in rows]


@app.post("/admin/payments/{claim_id}/review")
def review_payment(claim_id: int, data: ReviewIn, db: Session = Depends(get_db),
                   reviewer: User = Depends(payment_reviewer)):
    claim = db.get(PaymentClaim, claim_id)
    if not claim:
        raise HTTPException(404, "Payment claim not found")
    if claim.status != "pending":
        raise HTTPException(409, "This claim has already been reviewed")
    if data.decision == "approve" and not claim.independent_verification:
        raise HTTPException(409, "Independent payment verification is required before approval")
    claim.status = "approved" if data.decision == "approve" else "rejected"
    claim.reviewed_by = reviewer.id
    claim.review_note = data.note.strip() or None
    claim.reviewed_at = datetime.now(timezone.utc)
    write_audit(db, reviewer.id, f"payment.{claim.status}", "payment_claim", claim.id, claim.review_note or "")
    db.commit()
    return {"id": claim.id, "status": claim.status, "subscription_activated": False}


@app.get("/admin/audit-logs")
def admin_audit_logs(limit: int = 100, db: Session = Depends(get_db),
                     reviewer: User = Depends(payment_reviewer)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 200)))).all()
    return [{"id": r.id, "actor_id": r.actor_id, "action": r.action,
             "target_type": r.target_type, "target_id": r.target_id,
             "detail": r.detail, "created_at": r.created_at} for r in rows]


# There is deliberately no public route to grant admin roles, verify email, or
# mark a payment as independently verified. Those actions need a trusted ops process.


from features import router as features_router
app.include_router(features_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=os.getenv("APP_ENV") == "development")
