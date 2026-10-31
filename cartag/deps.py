"""Things routes ask FastAPI to hand them: the logged-in owner or admin, the client IP, limiters."""

from datetime import datetime

from fastapi import Depends, Path, Request, Response
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import Session

from cartag.config import Settings, get_settings
from cartag.db import get_db
from cartag.errors import bad_request, unauthorized
from cartag.models import Admin, User
from cartag.ratelimit import Limiters
from cartag.schemas import TagCode
from cartag.security import hash_ip
from cartag.services.sessions import find_admin_by_session, find_user_by_session
from cartag.services.sms import SmsProvider


def client_ip(request: Request) -> str | None:
    """The real client address, trusting only as many proxy hops as configured."""
    hops = get_settings().trust_proxy
    forwarded = request.headers.get("x-forwarded-for")
    if hops > 0 and forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            return parts[max(len(parts) - hops, 0)]
    return request.client.host if request.client else None


def ip_hash(request: Request) -> str | None:
    return hash_ip(client_ip(request))


def settings_dep() -> Settings:
    return get_settings()


_tag_code = TypeAdapter(TagCode)


def tag_code_param(code: str = Path(...)) -> str:
    """Normalizes and validates the {code} in a URL the same way request bodies do."""
    try:
        return _tag_code.validate_python(code)
    except ValidationError as error:
        message = str(error.errors()[0]["msg"]).removeprefix("Value error, ")
        raise bad_request(message, "VALIDATION_ERROR") from None


def sms_dep(request: Request) -> SmsProvider:
    return request.app.state.sms


def payment_provider_dep(request: Request):
    """The online payment provider, or None while online payment is switched off."""
    return request.app.state.payment_provider


def limiters_dep(request: Request) -> Limiters:
    return request.app.state.limiters


def session_token(request: Request) -> str | None:
    token = request.cookies.get(get_settings().session_cookie_name)
    return token or None


def optional_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = session_token(request)
    return find_user_by_session(db, token) if token else None


def require_user(user: User | None = Depends(optional_user)) -> User:
    if user is None:
        raise unauthorized()
    return user


def admin_token(request: Request) -> str | None:
    token = request.cookies.get(get_settings().admin_cookie_name)
    return token or None


def optional_admin(request: Request, db: Session = Depends(get_db)) -> Admin | None:
    token = admin_token(request)
    return find_admin_by_session(db, token) if token else None


def require_admin(admin: Admin | None = Depends(optional_admin)) -> Admin:
    if admin is None:
        raise unauthorized("Admin login required", "ADMIN_UNAUTHORIZED")
    return admin


def set_session_cookie(response: Response, name: str, token: str, expires: datetime) -> None:
    response.set_cookie(
        name,
        token,
        expires=expires,
        httponly=True,
        secure=get_settings().is_production,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response, name: str) -> None:
    response.delete_cookie(name, httponly=True, secure=get_settings().is_production, samesite="lax", path="/")


# ---------- per-IP rate limits as dependencies ----------
def limit_api(request: Request, limiters: Limiters = Depends(limiters_dep)) -> None:
    limiters.api.consume(client_ip(request) or "unknown")


def limit_auth(request: Request, limiters: Limiters = Depends(limiters_dep)) -> None:
    limiters.auth.consume(client_ip(request) or "unknown")


def limit_otp(request: Request, limiters: Limiters = Depends(limiters_dep)) -> None:
    limiters.otp.consume(client_ip(request) or "unknown")


def limit_activate(request: Request, limiters: Limiters = Depends(limiters_dep)) -> None:
    limiters.activate.consume(client_ip(request) or "unknown")


def limit_scan(request: Request, limiters: Limiters = Depends(limiters_dep)) -> None:
    ip = client_ip(request) or "unknown"
    limiters.scan.consume(ip)
    limiters.scan_miss.check(ip)
