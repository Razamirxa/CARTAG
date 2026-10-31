import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from cartag.domain import UserStatus
from cartag.models import Admin, AdminSession, AuthThrottle, OtpChallenge, User, UserSession
from cartag.security import hash_session_token, new_session_token

USER_SESSION_TTL = timedelta(days=30)
ADMIN_SESSION_TTL = timedelta(hours=8)
ADMIN_IDLE_TIMEOUT = timedelta(hours=2)
TOUCH_INTERVAL = timedelta(minutes=5)


@dataclass(frozen=True)
class CreatedSession:
    token: str
    expires_at: datetime


def _clip(value: str | None) -> str | None:
    return value[:250] if value else None


# ---------- owners ----------
def create_user_session(db: Session, user_id: uuid.UUID, user_agent: str | None, ip_hash: str | None) -> CreatedSession:
    token = new_session_token()
    expires_at = datetime.now(UTC) + USER_SESSION_TTL
    db.add(
        UserSession(
            token_hash=hash_session_token(token),
            user_id=user_id,
            expires_at=expires_at,
            user_agent=_clip(user_agent),
            ip_hash=ip_hash,
        )
    )
    db.commit()
    return CreatedSession(token, expires_at)


def find_user_by_session(db: Session, token: str) -> User | None:
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_session_token(token)))
    if session is None:
        return None
    now = datetime.now(UTC)
    user = session.user
    if session.expires_at <= now or user.status != UserStatus.ACTIVE:
        return None
    if now - session.last_seen_at > TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return user


def destroy_user_session(db: Session, token: str) -> None:
    db.execute(delete(UserSession).where(UserSession.token_hash == hash_session_token(token)))
    db.commit()


def revoke_user_sessions(db: Session, user_id: uuid.UUID, keep_token: str | None = None) -> None:
    """Logs a user out everywhere, optionally keeping the session that is making the request."""
    stmt = delete(UserSession).where(UserSession.user_id == user_id)
    if keep_token:
        stmt = stmt.where(UserSession.token_hash != hash_session_token(keep_token))
    db.execute(stmt)
    db.commit()


# ---------- admins ----------
def create_admin_session(
    db: Session, admin_id: uuid.UUID, user_agent: str | None, ip_hash: str | None
) -> CreatedSession:
    token = new_session_token()
    expires_at = datetime.now(UTC) + ADMIN_SESSION_TTL
    db.add(
        AdminSession(
            token_hash=hash_session_token(token),
            admin_id=admin_id,
            expires_at=expires_at,
            user_agent=_clip(user_agent),
            ip_hash=ip_hash,
        )
    )
    db.commit()
    return CreatedSession(token, expires_at)


def find_admin_by_session(db: Session, token: str) -> Admin | None:
    session = db.scalar(select(AdminSession).where(AdminSession.token_hash == hash_session_token(token)))
    if session is None:
        return None
    now = datetime.now(UTC)
    admin = session.admin
    expired = session.expires_at <= now
    idle = now - session.last_seen_at > ADMIN_IDLE_TIMEOUT
    if expired or idle or admin.disabled_at is not None:
        return None
    if now - session.last_seen_at > TOUCH_INTERVAL:
        session.last_seen_at = now
        db.commit()
    return admin


def destroy_admin_session(db: Session, token: str) -> None:
    db.execute(delete(AdminSession).where(AdminSession.token_hash == hash_session_token(token)))
    db.commit()


def purge_expired(db: Session) -> None:
    """Housekeeping: removes expired sessions and old OTP challenges. Safe to run at any time."""
    now = datetime.now(UTC)
    day_ago = now - timedelta(hours=24)
    db.execute(delete(UserSession).where(UserSession.expires_at < now))
    db.execute(delete(AdminSession).where(AdminSession.expires_at < now))
    db.execute(delete(OtpChallenge).where(OtpChallenge.created_at < day_ago))
    db.execute(delete(AuthThrottle).where(AuthThrottle.updated_at < day_ago))
    db.commit()
