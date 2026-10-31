from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from cartag.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=10)

# expire_on_commit=False keeps objects usable after commit, so a route can return them without
# triggering another query per attribute.
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """One database session per request. Services commit explicitly; anything not committed is rolled back."""
    with SessionLocal() as session:
        yield session
