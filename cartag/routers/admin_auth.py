from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from cartag.config import Settings
from cartag.db import get_db
from cartag.deps import (
    admin_token,
    clear_session_cookie,
    ip_hash,
    limit_auth,
    optional_admin,
    require_admin,
    set_session_cookie,
    settings_dep,
)
from cartag.errors import unauthorized
from cartag.models import Admin
from cartag.schemas import AdminLoginIn
from cartag.security import verify_against_dummy, verify_password
from cartag.services.audit import Actor, audit
from cartag.services.sessions import create_admin_session, destroy_admin_session
from cartag.services.throttle import assert_not_locked, clear_failures, record_failure

router = APIRouter(prefix="/admin/auth", tags=["admin"])


def public_admin(admin: Admin) -> dict[str, Any]:
    return {"id": str(admin.id), "name": admin.name, "email": admin.email}


@router.get("/me")
def me(admin: Admin | None = Depends(optional_admin)):
    return {"admin": public_admin(admin) if admin else None}


@router.post("/login", dependencies=[Depends(limit_auth)])
def login(
    body: AdminLoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    throttle_key = f"admin:{body.email}"
    assert_not_locked(db, throttle_key)

    admin = db.scalar(select(Admin).where(Admin.email == body.email))
    if admin is not None and admin.disabled_at is None:
        ok = verify_password(admin.password_hash, body.password)
    else:
        verify_against_dummy(body.password)
        ok = False

    if admin is None or not ok:
        record_failure(db, throttle_key)
        raise unauthorized("Incorrect email or password.", "INVALID_CREDENTIALS")

    clear_failures(db, throttle_key)
    admin.last_login_at = datetime.now(UTC)
    audit(db, Actor.admin(admin.id), "admin.login", "Admin", admin.id)
    db.commit()

    session = create_admin_session(db, admin.id, request.headers.get("user-agent"), ip_hash(request))
    set_session_cookie(response, settings.admin_cookie_name, session.token, session.expires_at)
    return {"admin": public_admin(admin)}


@router.post("/logout", dependencies=[Depends(require_admin)])
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    token = admin_token(request)
    if token:
        destroy_admin_session(db, token)
    clear_session_cookie(response, settings.admin_cookie_name)
    return {"ok": True}
