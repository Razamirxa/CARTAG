from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from cartag.config import Settings
from cartag.db import get_db
from cartag.deps import (
    clear_session_cookie,
    ip_hash,
    limit_auth,
    limit_otp,
    optional_user,
    session_token,
    set_session_cookie,
    settings_dep,
    sms_dep,
)
from cartag.domain import OtpPurpose, UserStatus
from cartag.errors import AppError, bad_request, forbidden, unauthorized
from cartag.models import User
from cartag.schemas import LoginIn, PasswordResetIn, PasswordResetRequestIn, RegisterIn
from cartag.security import hash_password, verify_against_dummy, verify_password
from cartag.services.audit import Actor, audit
from cartag.services.otp import request_otp, verify_otp
from cartag.services.sessions import create_user_session, destroy_user_session, revoke_user_sessions
from cartag.services.sms import SmsProvider
from cartag.services.throttle import assert_login_allowed, clear_login_failures, record_login_failure

router = APIRouter(prefix="/auth", tags=["auth"])


def public_user(user: User) -> dict[str, Any]:
    return {
        "id": str(user.id),
        "name": user.name,
        "phone": user.phone,
        "phoneVerified": user.phone_verified_at is not None,
        "hasCard": user.card is not None,
        "createdAt": user.created_at,
    }


@router.get("/me")
def me(user: User | None = Depends(optional_user)):
    return {"user": public_user(user) if user else None}


@router.post("/register", status_code=201, dependencies=[Depends(limit_auth)])
def register(
    body: RegisterIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    """Creates an account with a mobile number and password. The number is confirmed later, when a tag is turned on."""
    user = User(
        phone=body.phone, name=body.name, password_hash=hash_password(body.password), last_login_at=datetime.now(UTC)
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise AppError(
            409,
            "PHONE_TAKEN",
            "An account with this mobile number already exists. Log in, or reset your password if you forgot it.",
        ) from None

    audit(db, Actor.user(user.id), "user.register", "User", user.id)
    db.commit()

    session = create_user_session(db, user.id, request.headers.get("user-agent"), ip_hash(request))
    set_session_cookie(response, settings.session_cookie_name, session.token, session.expires_at)
    return {"user": public_user(user)}


@router.post("/login", dependencies=[Depends(limit_auth)])
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    address = ip_hash(request)
    assert_login_allowed(db, "user", body.phone, address)

    user = db.scalar(select(User).where(User.phone == body.phone))
    if user is not None:
        password_ok = verify_password(user.password_hash, body.password)
    else:
        verify_against_dummy(body.password)
        password_ok = False

    if user is None or not password_ok or user.status == UserStatus.DELETED:
        record_login_failure(db, "user", body.phone, address)
        raise unauthorized("Incorrect mobile number or password.", "INVALID_CREDENTIALS")
    # The password was right, so telling the owner about the block leaks nothing.
    if user.status != UserStatus.ACTIVE:
        raise forbidden("This account has been blocked. Please contact support.", "ACCOUNT_BLOCKED")

    clear_login_failures(db, "user", body.phone)
    user.last_login_at = datetime.now(UTC)
    db.commit()

    session = create_user_session(db, user.id, request.headers.get("user-agent"), ip_hash(request))
    set_session_cookie(response, settings.session_cookie_name, session.token, session.expires_at)
    return {"user": public_user(user)}


@router.post("/password/reset/request", dependencies=[Depends(limit_otp)])
def password_reset_request(
    body: PasswordResetRequestIn,
    request: Request,
    db: Session = Depends(get_db),
    sms: SmsProvider = Depends(sms_dep),
):
    user = db.scalar(select(User).where(User.phone == body.phone))
    eligible = user is not None and user.status == UserStatus.ACTIVE
    resend = request_otp(
        db, phone=body.phone, purpose=OtpPurpose.RESET_PASSWORD, ip_hash=ip_hash(request), eligible=eligible, sms=sms
    )
    # Same answer whether or not the number has an account.
    return {"ok": True, "resendAfterSeconds": resend}


@router.post("/password/reset/confirm", dependencies=[Depends(limit_auth)])
def password_reset_confirm(body: PasswordResetIn, db: Session = Depends(get_db)):
    invalid = bad_request("That code is incorrect or has expired.", "INVALID_OTP")
    if not verify_otp(db, body.phone, OtpPurpose.RESET_PASSWORD, body.otp):
        raise invalid

    user = db.scalar(select(User).where(User.phone == body.phone))
    if user is None or user.status != UserStatus.ACTIVE:
        raise invalid

    user.password_hash = hash_password(body.new_password)
    # Whoever can receive texts on this number proved it is theirs.
    if user.phone_verified_at is None:
        user.phone_verified_at = datetime.now(UTC)
    db.commit()
    # A reset means the old password may be compromised: end every session and clear lockouts.
    revoke_user_sessions(db, user.id)
    clear_login_failures(db, "user", body.phone)
    audit(db, Actor.user(user.id), "user.password_reset", "User", user.id)
    db.commit()
    return {"ok": True}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    token = session_token(request)
    if token:
        destroy_user_session(db, token)
    clear_session_cookie(response, settings.session_cookie_name)
    return {"ok": True}
