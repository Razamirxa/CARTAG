from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from cartag.errors import too_many
from cartag.models import AuthThrottle

MAX_FAILURES = 5
MAX_FAILURES_ANY_IP = 25
LOCK = timedelta(minutes=15)
WINDOW = timedelta(minutes=15)


def assert_not_locked(db: Session, key: str) -> None:
    """Raises 429 while the key is locked. Clears stale counters so old failures do not add up."""
    row = db.scalar(select(AuthThrottle).where(AuthThrottle.key == key))
    if row is None:
        return

    now = datetime.now(UTC)
    if row.locked_until and row.locked_until > now:
        retry = int((row.locked_until - now).total_seconds()) + 1
        raise too_many(
            "Too many failed attempts. Please wait a few minutes and try again.",
            "LOCKED",
            {"retryAfterSeconds": retry},
        )

    stale = row.locked_until is not None or now - row.updated_at > WINDOW
    if stale:
        db.execute(delete(AuthThrottle).where(AuthThrottle.key == key))
        db.commit()


def record_failure(db: Session, key: str, limit: int = MAX_FAILURES) -> None:
    """Counts a failed attempt and commits straight away, because the caller is about to raise."""
    stmt = (
        pg_insert(AuthThrottle)
        .values(key=key, count=1)
        .on_conflict_do_update(index_elements=["key"], set_={"count": AuthThrottle.count + 1})
        .returning(AuthThrottle.count)
    )
    count = db.execute(stmt).scalar_one()
    if count >= limit:
        row = db.get(AuthThrottle, key)
        if row is not None:
            row.locked_until = datetime.now(UTC) + LOCK
    db.commit()


def clear_failures(db: Session, key: str) -> None:
    db.execute(delete(AuthThrottle).where(AuthThrottle.key == key))
    db.commit()


# ---------- login lockouts that one stranger cannot use against everyone ----------
# A lock per account would let anyone who knows an email or number keep that person out by failing five
# times. So each account has two counters: failures from one address (locks after 5, for that address only)
# and failures from anywhere (locks after 25, which stops a guesser who rotates addresses).
def login_keys(kind: str, identity: str, ip_hash: str | None) -> tuple[str, str]:
    return f"{kind}:{identity}:{ip_hash or '-'}", f"{kind}:{identity}"


def assert_login_allowed(db: Session, kind: str, identity: str, ip_hash: str | None) -> None:
    for key in login_keys(kind, identity, ip_hash):
        assert_not_locked(db, key)


def record_login_failure(db: Session, kind: str, identity: str, ip_hash: str | None) -> None:
    per_address, anywhere = login_keys(kind, identity, ip_hash)
    record_failure(db, per_address)
    record_failure(db, anywhere, MAX_FAILURES_ANY_IP)


def clear_login_failures(db: Session, kind: str, identity: str) -> None:
    """Forgets every counter for the account, from any address."""
    db.execute(
        delete(AuthThrottle).where(
            (AuthThrottle.key == f"{kind}:{identity}")
            | AuthThrottle.key.startswith(f"{kind}:{identity}:", autoescape=True)
        )
    )
    db.commit()
