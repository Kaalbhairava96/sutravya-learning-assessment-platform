"""Authenticated administrator sessions, safe database browser and audited operations."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import String, cast, func, or_, select, text, update
from sqlalchemy.orm import Session

from app.registration import EVENT_KEY
from app.models import (
    AdminSession, AdminUser, AnswerOption, AuditEvent, Base, Candidate,
    ExamAttempt, ExamSlot, Question, QuestionBank, RateLimitBucket,
    Registration, Result, ScoringRule,
)

router = APIRouter(prefix="/api/admin", tags=["secure administration"])
ADMIN_COOKIE = "sutravya_admin_session"
ITERATIONS = 600_000
SESSION_TOUCH = timedelta(minutes=5)

RESTRICTED_TABLES = {
    "verification_challenges", "candidate_sessions", "admin_sessions", "rate_limit_buckets"
}
SECRET_COLUMNS = {
    "password_hash", "token_digest", "otp_digest", "destination_digest",
    "subject_digest", "is_correct",
}
EDITABLE_FIELDS = {
    "candidates": {"full_name", "phone"},
    "registrations": {"status"},
    "exam_slots": {"starts_at", "ends_at", "capacity"},
    "question_banks": {"title", "description"},
    "questions": {
        "question_text", "category", "section", "difficulty", "time_limit_seconds",
        "explanation", "source_reference", "is_active",
    },
    "answer_options": {"option_text"},
}
SEARCH_COLUMNS = {
    "candidates": ("full_name", "email", "phone"),
    "registrations": ("registration_id", "stream", "status", "payment_status"),
    "exam_slots": ("stream",),
    "question_banks": ("bank_code", "title"),
    "questions": ("question_text", "section", "category"),
    "answer_options": ("identifier", "option_text"),
    "scoring_rules": ("rule_code",),
    "exam_attempts": ("status",),
    "candidate_responses": ("position",),
    "results": ("score",),
    "admin_users": ("email", "role_key"),
    "audit_events": ("action", "target_type"),
}
TABLE_DESCRIPTIONS = {
    "candidates": "Candidate identity and verified contact information.",
    "registrations": "Registration category, eligibility, payment state and slot assignment.",
    "exam_slots": "Stream-specific examination windows and capacity.",
    "question_banks": "Versioned question-bank metadata.",
    "questions": "Question wording, syllabus mapping and timing.",
    "answer_options": "Answer choice wording. Answer-key flags remain private.",
    "scoring_rules": "Approved scoring rules.",
    "exam_attempts": "Candidate examination attempts and lifecycle state.",
    "candidate_responses": "Presented questions and recorded candidate answers.",
    "results": "Calculated score, approval and release state.",
    "admin_users": "Administrator identity and access status; password hashes are never displayed.",
    "audit_events": "Who changed what and when.",
    "verification_challenges": "Restricted OTP and verification state; metadata only.",
    "candidate_sessions": "Restricted candidate session state; metadata only.",
    "admin_sessions": "Restricted administrator session state; metadata only.",
    "rate_limit_buckets": "Restricted abuse-control counters; metadata only.",
}


class AdminCredentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=14, max_length=256)


class SlotPayload(BaseModel):
    stream: str = Field(pattern=r"^(paramedical|nursing|mbbs_ug|mbbs_pg)$")
    starts_at: datetime
    ends_at: datetime
    capacity: int = Field(gt=0, le=1500)


class SlotAssignment(BaseModel):
    registration_ids: list[str] = Field(min_length=1, max_length=1500)


class RecordPatch(BaseModel):
    changes: dict[str, Any] = Field(min_length=1, max_length=12)


@contextmanager
def db_session(request: Request):
    with request.app.state.session_factory() as session:
        yield session


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalise_email(value: str) -> str:
    email = value.strip().lower()
    if not re.fullmatch(r"[^@\s]{1,64}@[^@\s.]+(?:\.[^@\s.]+)+", email):
        raise HTTPException(status_code=422, detail="Enter a valid administrator email address.")
    return email


def password_policy(password: str, email: str) -> None:
    if len(password) < 14:
        raise HTTPException(status_code=422, detail="Use a password with at least 14 characters.")
    if password.casefold() == email.casefold():
        raise HTTPException(status_code=422, detail="Choose a password that is different from your email address.")
    if password.lower() in {"passwordpassword", "administrator123", "qwertyuiopasdfgh"}:
        raise HTTPException(status_code=422, detail="Choose a stronger administrator password.")


def b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return "pbkdf2_sha256$%d$%s$%s" % (ITERATIONS, b64encode(salt), b64encode(digest))


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        hash_password(password)
        return False
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = stored.split("$", 3)
        iterations = int(iterations_raw)
        if algorithm != "pbkdf2_sha256" or iterations < 300_000 or iterations > 2_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), b64decode(salt_raw), iterations
        )
        return hmac.compare_digest(actual, b64decode(digest_raw))
    except (ValueError, TypeError):
        return False


def digest_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_session(session: Session, user: AdminUser, request: Request) -> str:
    ttl = min(max(int(request.app.state.settings.admin_session_ttl_seconds), 900), 43_200)
    token = secrets.token_urlsafe(48)
    session.add(AdminSession(
        admin_user_id=user.id,
        token_digest=digest_token(token),
        expires_at=now_utc() + timedelta(seconds=ttl),
    ))
    return token


def current_admin(session: Session, request: Request) -> AdminUser:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Administrator sign-in is required.")
    current = now_utc()
    saved = session.scalar(
        select(AdminSession).where(AdminSession.token_digest == digest_token(token)).with_for_update()
    )
    if saved is None or saved.revoked_at is not None or saved.expires_at <= current:
        raise HTTPException(status_code=401, detail="Administrator session has expired. Sign in again.")
    user = session.get(AdminUser, saved.admin_user_id)
    if user is None or not user.is_active:
        saved.revoked_at = current
        session.commit()
        raise HTTPException(status_code=401, detail="This administrator account is inactive.")
    if saved.last_seen_at is None or current - saved.last_seen_at >= SESSION_TOUCH:
        saved.last_seen_at = current
        session.commit()
    return user


def require_csrf(request: Request) -> None:
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("x-admin-request") != "1":
        raise HTTPException(status_code=403, detail="The administrator request could not be verified. Refresh and try again.")
    origin = request.headers.get("origin")
    if origin:
        allowed = {value.rstrip("/") for value in request.app.state.settings.cors_origins}
        if request.app.state.settings.admin_frontend_origin:
            allowed.add(request.app.state.settings.admin_frontend_origin.rstrip("/"))
        if origin.rstrip("/") not in allowed:
            raise HTTPException(status_code=403, detail="Origin is not allowed.")


def rate_limit_subject(request: Request, email: str) -> str:
    secret = request.app.state.settings.admin_session_secret or ""
    client = request.client.host if request.client else "unknown"
    return hmac.new(secret.encode("utf-8"), (client + "|" + email).encode("utf-8"), hashlib.sha256).hexdigest()


def login_limited(session: Session, request: Request, email: str) -> bool:
    bucket = session.scalar(select(RateLimitBucket).where(
        RateLimitBucket.scope == "admin_login",
        RateLimitBucket.subject_digest == rate_limit_subject(request, email),
    ))
    return bool(
        bucket and now_utc() - bucket.window_started_at < timedelta(hours=1)
        and bucket.request_count >= 8
    )


def record_failed_login(session: Session, request: Request, email: str) -> None:
    current = now_utc()
    subject = rate_limit_subject(request, email)
    bucket = session.scalar(select(RateLimitBucket).where(
        RateLimitBucket.scope == "admin_login",
        RateLimitBucket.subject_digest == subject,
    ).with_for_update())
    if bucket is None:
        session.add(RateLimitBucket(
            scope="admin_login", subject_digest=subject,
            window_started_at=current, request_count=1,
        ))
    elif current - bucket.window_started_at >= timedelta(hours=1):
        bucket.window_started_at = current
        bucket.request_count = 1
    else:
        bucket.request_count += 1
    session.commit()


def safe_user(user: AdminUser) -> dict[str, Any]:
    return {"id": str(user.id), "email": user.email, "role": user.role_key or "owner", "active": user.is_active}


def serialise(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if isinstance(value, dict):
        return {str(key): serialise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialise(item) for item in value]
    return value


def table_metadata(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "label": name.replace("_", " ").title(),
        "description": TABLE_DESCRIPTIONS.get(name, "Application data."),
        "restricted": name in RESTRICTED_TABLES,
        "editable": name in EDITABLE_FIELDS,
    }


def guard_edit(session: Session, table_name: str, record: dict, changes: dict) -> dict:
    if table_name == "candidates":
        if "full_name" in changes and (
            not isinstance(changes["full_name"], str) or not changes["full_name"].strip()
            or len(changes["full_name"]) > 200
        ):
            raise HTTPException(status_code=422, detail="Candidate name must contain 1–200 characters.")
        if "phone" in changes and (
            not isinstance(changes["phone"], str)
            or not re.fullmatch(r"\+?[0-9 -]{10,20}", changes["phone"])
        ):
            raise HTTPException(status_code=422, detail="Enter a valid candidate phone number.")
        return changes

    if table_name == "registrations":
        if changes.get("status") not in {"active", "suspended", "cancelled"}:
            raise HTTPException(status_code=422, detail="Registration status may only be active, suspended or cancelled.")
        if record["payment_status"] not in {"paid", "not_required"}:
            raise HTTPException(status_code=409, detail="A pending or failed payment cannot be changed from this panel.")
        attempt = session.scalar(select(ExamAttempt.id).where(ExamAttempt.registration_id == record["id"]).limit(1))
        if attempt:
            raise HTTPException(status_code=409, detail="A registration with an exam attempt cannot be suspended or cancelled here.")
        return changes

    if table_name == "exam_slots":
        attempt = session.scalar(select(ExamAttempt.id).where(ExamAttempt.exam_slot_id == record["id"]).limit(1))
        if attempt:
            raise HTTPException(status_code=409, detail="A slot with exam attempts is locked against schedule changes.")
        if "capacity" in changes:
            try:
                capacity = int(changes["capacity"])
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail="Capacity must be a whole number.") from None
            assigned = int(session.scalar(select(func.count(Registration.id)).where(Registration.exam_slot_id == record["id"])) or 0)
            if capacity < max(assigned, 1) or capacity > 1500:
                raise HTTPException(status_code=422, detail="Capacity must cover assigned candidates and cannot exceed 1500.")
            changes["capacity"] = capacity
        starts = changes.get("starts_at", record["starts_at"])
        ends = changes.get("ends_at", record["ends_at"])
        if isinstance(starts, str):
            starts = datetime.fromisoformat(starts.replace("Z", "+00:00"))
        if isinstance(ends, str):
            ends = datetime.fromisoformat(ends.replace("Z", "+00:00"))
        if starts.tzinfo is None or ends.tzinfo is None or starts <= now_utc() or ends - starts < timedelta(minutes=47):
            raise HTTPException(status_code=422, detail="Choose a future timezone-aware slot of at least 47 minutes.")
        if "starts_at" in changes:
            changes["starts_at"] = starts
        if "ends_at" in changes:
            changes["ends_at"] = ends
        return changes

    if table_name == "question_banks":
        if "title" in changes and (
            not isinstance(changes["title"], str) or not changes["title"].strip()
            or len(changes["title"]) > 200
        ):
            raise HTTPException(status_code=422, detail="Question-bank title must contain 1–200 characters.")
        if "description" in changes and changes["description"] is not None and (
            not isinstance(changes["description"], str) or len(changes["description"]) > 2000
        ):
            raise HTTPException(status_code=422, detail="Question-bank description is too long.")
        return changes

    if table_name == "questions":
        attempt = session.scalar(
            select(ExamAttempt.id).where(ExamAttempt.question_bank_id == record["question_bank_id"]).limit(1)
        )
        if attempt:
            raise HTTPException(status_code=409, detail="Question content is locked after exam attempts exist.")
        if "question_text" in changes and (
            not isinstance(changes["question_text"], str) or not changes["question_text"].strip()
            or len(changes["question_text"]) > 10000
        ):
            raise HTTPException(status_code=422, detail="Question text must contain 1–10,000 characters.")
        if "difficulty" in changes and changes["difficulty"] not in {"easy", "moderate"}:
            raise HTTPException(status_code=422, detail="Difficulty must be easy or moderate.")
        if "time_limit_seconds" in changes:
            try:
                seconds = int(changes["time_limit_seconds"])
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail="Question time must be a whole number.") from None
            if not 15 <= seconds <= 60:
                raise HTTPException(status_code=422, detail="Question time must be between 15 and 60 seconds.")
            changes["time_limit_seconds"] = seconds
        if "section" in changes and (
            not isinstance(changes["section"], str) or not changes["section"].strip()
            or len(changes["section"]) > 40
        ):
            raise HTTPException(status_code=422, detail="Enter a valid syllabus section key.")
        if "is_active" in changes and type(changes["is_active"]) is not bool:
            raise HTTPException(status_code=422, detail="Active state must be true or false.")
        return changes

    if table_name == "answer_options":
        question = session.get(Question, record["question_id"])
        attempt = session.scalar(
            select(ExamAttempt.id).where(ExamAttempt.question_bank_id == question.question_bank_id).limit(1)
        ) if question else None
        if attempt:
            raise HTTPException(status_code=409, detail="Answer options are locked after exam attempts exist.")
        value = changes.get("option_text")
        if not isinstance(value, str) or not value.strip() or len(value) > 2000:
            raise HTTPException(status_code=422, detail="Option text must contain 1–2,000 characters.")
        return changes

    raise HTTPException(status_code=403, detail="This database table is read-only in the administrator portal.")


@router.get("/auth/status")
def auth_status(request: Request):
    with db_session(request) as session:
        count = int(session.scalar(select(func.count(AdminUser.id))) or 0)
    return {
        "setup_required": count == 0,
        "setup_available": bool(request.app.state.settings.admin_bootstrap_token),
        "login_available": count > 0,
    }


@router.post("/auth/setup", status_code=201)
def first_admin_setup(payload: AdminCredentials, request: Request,
                      x_admin_bootstrap_token: str | None = Header(default=None)):
    require_csrf(request)
    settings = request.app.state.settings
    if not settings.admin_bootstrap_token or not settings.admin_session_secret:
        raise HTTPException(status_code=503, detail="Administrator first-time setup is not configured.")
    if (
        not x_admin_bootstrap_token or len(x_admin_bootstrap_token) > 512
        or not hmac.compare_digest(x_admin_bootstrap_token.encode(), settings.admin_bootstrap_token.encode())
    ):
        raise HTTPException(status_code=403, detail="The one-time setup token is invalid.")
    email = normalise_email(payload.email)
    password_policy(payload.password, email)
    with db_session(request) as session:
        if session.bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(77321007)"))
        if session.scalar(select(AdminUser.id).limit(1)) is not None:
            raise HTTPException(status_code=409, detail="Administrator setup has already been completed.")
        user = AdminUser(email=email, password_hash=hash_password(payload.password), role_key="owner", is_active=True)
        session.add(user)
        session.flush()
        session.add(AuditEvent(
            actor_admin_id=user.id, action="admin_initial_account_created",
            target_type="admin_user", target_id=user.id,
        ))
        access_token = issue_session(session, user, request)
        session.commit()
        return {"status": "created", "access_token": access_token, "token_type": "bearer", "expires_in": min(max(int(settings.admin_session_ttl_seconds), 900), 43200), "administrator": safe_user(user)}


@router.post("/auth/login")
def login(payload: AdminCredentials, request: Request):
    require_csrf(request)
    settings = request.app.state.settings
    if not settings.admin_session_secret:
        raise HTTPException(status_code=503, detail="Administrator sign-in is not configured.")
    email = normalise_email(payload.email)
    with db_session(request) as session:
        if login_limited(session, request, email):
            raise HTTPException(status_code=429, detail="Too many unsuccessful sign-in attempts. Try again in an hour.")
        user = session.scalar(select(AdminUser).where(func.lower(AdminUser.email) == email))
        if user is None or not user.is_active or not verify_password(payload.password, user.password_hash if user else None):
            record_failed_login(session, request, email)
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        access_token = issue_session(session, user, request)
        session.add(AuditEvent(
            actor_admin_id=user.id, action="admin_login",
            target_type="admin_user", target_id=user.id,
        ))
        session.commit()
        return {"status": "authenticated", "access_token": access_token, "token_type": "bearer", "expires_in": min(max(int(settings.admin_session_ttl_seconds), 900), 43200), "administrator": safe_user(user)}


@router.get("/auth/me")
def me(request: Request):
    with db_session(request) as session:
        return {"administrator": safe_user(current_admin(session, request))}


@router.post("/auth/logout", status_code=204)
def logout(request: Request, response: Response):
    require_csrf(request)
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token and len(token) <= 256:
        with db_session(request) as session:
            saved = session.scalar(select(AdminSession).where(AdminSession.token_digest == digest_token(token)))
            if saved and saved.revoked_at is None:
                saved.revoked_at = now_utc()
                session.add(AuditEvent(
                    actor_admin_id=saved.admin_user_id, action="admin_logout",
                    target_type="admin_user", target_id=saved.admin_user_id,
                ))
                session.commit()
    return Response(status_code=204)


@router.get("/database/overview")
def database_overview(request: Request):
    with db_session(request) as session:
        admin = current_admin(session, request)
        bind = session.get_bind()
        if bind.dialect.name == "postgresql":
            database = dict(session.execute(text(
                "SELECT current_database() AS database_name, current_setting('server_version') AS server_version, current_schema() AS schema_name"
            )).mappings().one())
            try:
                database["schema_revision"] = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            except Exception:
                database["schema_revision"] = None
        else:
            database = {"database_name": bind.url.database or "test", "server_version": bind.dialect.name, "schema_name": "main"}
        tables = []
        for name, table in Base.metadata.tables.items():
            meta = table_metadata(name)
            meta["rows"] = int(session.scalar(select(func.count()).select_from(table)) or 0)
            tables.append(meta)
        return {
            "database": database, "tables": tables,
            "total_tables": len(tables), "total_rows": sum(item["rows"] for item in tables),
            "administrator": safe_user(admin),
        }


@router.get("/database/tables/{table_name}")
def browse_table(table_name: str, request: Request,
                 search: str = Query(default="", max_length=100),
                 limit: int = Query(default=25, ge=1, le=100),
                 offset: int = Query(default=0, ge=0)):
    with db_session(request) as session:
        current_admin(session, request)
        table = Base.metadata.tables.get(table_name)
        if table is None:
            raise HTTPException(status_code=404, detail="Database table not found.")
        total = int(session.scalar(select(func.count()).select_from(table)) or 0)
        if table_name in RESTRICTED_TABLES:
            return {
                **table_metadata(table_name), "total": total, "limit": limit,
                "offset": offset, "columns": [], "editable_fields": [],
                "records": [],
                "notice": "OTP digests, authentication tokens and abuse-control identifiers are intentionally hidden. Only table metadata and row counts are available.",
            }
        visible = [column for column in table.columns if column.name not in SECRET_COLUMNS]
        filters = []
        term = search.strip()
        if term:
            for name in SEARCH_COLUMNS.get(table_name, ()):
                if name in table.c:
                    filters.append(cast(table.c[name], String).ilike("%" + term + "%"))
        where = or_(*filters) if filters else None
        count_stmt = select(func.count()).select_from(table)
        stmt = select(*visible)
        if where is not None:
            count_stmt = count_stmt.where(where)
            stmt = stmt.where(where)
        total = int(session.scalar(count_stmt) or 0)
        order = table.c.created_at if "created_at" in table.c else list(table.primary_key.columns)[0]
        rows = session.execute(stmt.order_by(order.desc()).limit(limit).offset(offset)).mappings().all()
        columns = [{
            "name": column.name, "type": str(column.type), "nullable": column.nullable,
            "editable": column.name in EDITABLE_FIELDS.get(table_name, set()),
        } for column in visible]
        return {
            **table_metadata(table_name), "total": total, "limit": limit, "offset": offset,
            "columns": columns, "editable_fields": sorted(EDITABLE_FIELDS.get(table_name, set())),
            "records": [{column.name: serialise(row[column.name]) for column in visible} for row in rows],
            "notice": None,
        }


@router.patch("/database/tables/{table_name}/{record_id}")
def patch_record(table_name: str, record_id: str, payload: RecordPatch, request: Request):
    require_csrf(request)
    with db_session(request) as session:
        admin = current_admin(session, request)
        table = Base.metadata.tables.get(table_name)
        allowed = EDITABLE_FIELDS.get(table_name)
        if table is None or not allowed:
            raise HTTPException(status_code=403, detail="This database table is read-only in the administrator portal.")
        changes = dict(payload.changes)
        if not changes or not set(changes).issubset(allowed):
            raise HTTPException(status_code=422, detail="One or more requested fields cannot be edited.")
        pk = list(table.primary_key.columns)[0]
        try:
            pk_value = UUID(record_id) if pk.type.python_type is UUID else record_id
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="Record identifier is invalid.") from None
        current = session.execute(select(table).where(pk == pk_value).with_for_update()).mappings().first()
        if current is None:
            raise HTTPException(status_code=404, detail="Database record not found.")
        changes = guard_edit(session, table_name, dict(current), changes)
        if table_name == "questions":
            for field_name, maximum in (("category", 120), ("explanation", 10000), ("source_reference", 200)):
                if field_name in changes and changes[field_name] is not None and (
                    not isinstance(changes[field_name], str) or len(changes[field_name]) > maximum
                ):
                    raise HTTPException(status_code=422, detail=f"{field_name.replace('_',' ').title()} is too long.")
        session.execute(update(table).where(pk == pk_value).values(**changes))
        session.add(AuditEvent(
            actor_admin_id=admin.id, action="admin_record_updated",
            target_type=table_name, target_id=pk_value if isinstance(pk_value, UUID) else None,
        ))
        session.commit()
        return {"status": "updated", "table": table_name, "record_id": record_id, "changed_fields": sorted(changes)}


@router.post("/assessment/slots", status_code=201)
def create_slot(payload: SlotPayload, request: Request):
    require_csrf(request)
    if payload.starts_at.tzinfo is None or payload.ends_at.tzinfo is None:
        raise HTTPException(status_code=422, detail="Slot timestamps must include a timezone.")
    start = payload.starts_at.astimezone(timezone.utc)
    end = payload.ends_at.astimezone(timezone.utc)
    if start <= now_utc() or end - start < timedelta(minutes=47):
        raise HTTPException(status_code=422, detail="Choose a future slot of at least 47 minutes.")
    with db_session(request) as session:
        admin = current_admin(session, request)
        overlapping = session.scalar(select(ExamSlot.id).where(
            ExamSlot.event_key == EVENT_KEY, ExamSlot.stream == payload.stream,
            ExamSlot.starts_at < end, ExamSlot.ends_at > start,
        ))
        if overlapping:
            raise HTTPException(status_code=409, detail="This stream already has an overlapping exam slot.")
        slot = ExamSlot(event_key=EVENT_KEY, stream=payload.stream, starts_at=start, ends_at=end, capacity=payload.capacity)
        session.add(slot)
        session.flush()
        session.add(AuditEvent(
            actor_admin_id=admin.id, action="exam_slot_created",
            target_type="exam_slot", target_id=slot.id,
        ))
        session.commit()
        return {"slot_id": str(slot.id), "stream": slot.stream, "starts_at": start.isoformat(), "ends_at": end.isoformat(), "capacity": slot.capacity}


@router.post("/assessment/slots/{slot_id}/assign")
def assign_slot(slot_id: UUID, payload: SlotAssignment, request: Request):
    require_csrf(request)
    ids = [item.strip() for item in payload.registration_ids]
    if len(set(ids)) != len(ids) or any(not item or len(item) > 32 for item in ids):
        raise HTTPException(status_code=422, detail="Registration IDs must be unique and valid.")
    with db_session(request) as session:
        admin = current_admin(session, request)
        slot = session.get(ExamSlot, slot_id)
        if slot is None or slot.event_key != EVENT_KEY or slot.stream not in {"paramedical", "nursing", "mbbs_ug", "mbbs_pg", "mbbs_1st_year"}:
            raise HTTPException(status_code=404, detail="Assessment slot not found.")
        rows = session.scalars(select(Registration).where(
            Registration.event_key == EVENT_KEY, Registration.registration_id.in_(ids),
            Registration.stream == slot.stream, Registration.status == "active",
            Registration.is_internal_test.is_(False),
            Registration.registration_source.in_(("public_registration", "team_prelaunch")),
        ).with_for_update()).all()
        if len(rows) != len(ids):
            raise HTTPException(status_code=422, detail="One or more registrations are invalid or belong to another stream.")
        existing = session.scalar(select(ExamAttempt.id).where(ExamAttempt.registration_id.in_([row.id for row in rows])).limit(1))
        if existing:
            raise HTTPException(status_code=409, detail="A registration with an exam attempt cannot be reassigned.")
        for row in rows:
            row.exam_slot_id = slot.id
        session.add(AuditEvent(actor_admin_id=admin.id, action="exam_slot_registrations_assigned", target_type="exam_slot", target_id=slot.id))
        session.commit()
        return {"assigned_count": len(rows), "slot_id": str(slot.id), "stream": slot.stream}


@router.get("/audit")
def audit_log(request: Request, limit: int = Query(default=50, ge=1, le=100)):
    with db_session(request) as session:
        current_admin(session, request)
        rows = session.execute(
            select(AuditEvent, AdminUser.email)
            .outerjoin(AdminUser, AdminUser.id == AuditEvent.actor_admin_id)
            .order_by(AuditEvent.created_at.desc()).limit(limit)
        ).all()
        return {"records": [{
            "id": str(event.id), "action": event.action, "target_type": event.target_type,
            "target_id": str(event.target_id) if event.target_id else None,
            "actor": email or "System", "created_at": event.created_at.isoformat(),
        } for event, email in rows]}


@router.post("/results/{result_id}/approve")
def approve_result(result_id: UUID, request: Request):
    require_csrf(request)
    with db_session(request) as session:
        admin = current_admin(session, request)
        result = session.get(Result, result_id, with_for_update=True)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found.")
        if result.approved_at is None:
            result.approved_by_admin_id = admin.id
            result.approved_at = now_utc()
            session.add(AuditEvent(actor_admin_id=admin.id, action="result_approved", target_type="result", target_id=result.id))
            session.commit()
        return {"status": "approved", "result_id": str(result.id), "approved_at": result.approved_at.isoformat()}


@router.post("/results/{result_id}/release")
def release_result(result_id: UUID, request: Request):
    require_csrf(request)
    with db_session(request) as session:
        admin = current_admin(session, request)
        result = session.get(Result, result_id, with_for_update=True)
        if result is None:
            raise HTTPException(status_code=404, detail="Result not found.")
        if result.approved_at is None:
            raise HTTPException(status_code=409, detail="Approve this result before releasing it.")
        if result.released_at is None:
            result.released_at = now_utc()
            session.add(AuditEvent(actor_admin_id=admin.id, action="result_released", target_type="result", target_id=result.id))
            session.commit()
        return {"status": "released", "result_id": str(result.id), "released_at": result.released_at.isoformat()}


@router.get("/assessment/summary")
def assessment_summary(request: Request):
    with db_session(request) as session:
        current_admin(session, request)
        rows = session.execute(
            select(Registration.stream, func.count(Registration.id))
            .where(
                Registration.event_key == EVENT_KEY,
                Registration.is_internal_test.is_(False),
            )
            .group_by(Registration.stream)
        ).all()
        counts = {str(stream or "unassigned"): int(count) for stream, count in rows}
        return {
            "streams": {
                "paramedical": counts.get("paramedical", 0),
                "nursing": counts.get("nursing", 0),
                "mbbs_ug": counts.get("mbbs_ug", 0) + counts.get("mbbs_1st_year", 0),
                "mbbs_pg": counts.get("mbbs_pg", 0),
            },
            "unassigned": sum(
                count for stream, count in counts.items()
                if stream not in {"paramedical", "nursing", "mbbs_ug", "mbbs_pg", "mbbs_1st_year"}
            ),
        }
