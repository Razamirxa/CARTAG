from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from cartag.errors import too_many
from cartag.models import AuthThrottle

MAX_FAILURES = 5
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


def record_failure(db: Session, key: str) -> None:
    """Counts a failed attempt and commits straight away, because the caller is about to raise."""
    stmt = (
        pg_insert(AuthThrottle)
        .values(key=key, count=1)
        .on_conflict_do_update(index_elements=["key"], set_={"count": AuthThrottle.count + 1})
        .returning(AuthThrottle.count)
    )
    count = db.execute(stmt).scalar_one()
    if count >= MAX_FAILURES:
        row = db.get(AuthThrottle, key)
        if row is not None:
            row.locked_until = datetime.now(UTC) + LOCK
    db.commit()


def clear_failures(db: Session, key: str) -> None:
    db.execute(delete(AuthThrottle).where(AuthThrottle.key == key))
    db.commit()
