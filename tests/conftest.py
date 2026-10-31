import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def _test_database_url() -> str:
    """The development URL with `_test` added to the database name. Tests wipe this database."""
    dev_url = os.environ.get("DATABASE_URL") or dotenv_values(ROOT / ".env").get("DATABASE_URL") or ""
    parts = urlsplit(dev_url)
    name = parts.path.lstrip("/")
    if not name.endswith("_test"):
        name += "_test"
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, ""))


# These must be set before anything from cartag is imported, because settings are read once.
os.environ.update(
    {
        "APP_ENV": "test",
        "DATABASE_URL": _test_database_url(),
        "PUBLIC_BASE_URL": "http://localhost:5173",
        "SESSION_SECRET": "test-session-secret-0123456789abcdef0123456789abcdef",
        "OTP_SECRET": "test-otp-secret-0123456789abcdef0123456789abcdef",
        "IP_HASH_SALT": "test-ip-salt-0123456789abcdef",
        "SMS_PROVIDER": "console",
        "PAYMENT_PROVIDER": "mock",
        "SHIPPING_FEE_PKR": "200",
        "TAG_CODE_LENGTH": "10",
        "QR_PHYSICAL_SIZE_MM": "25",
        "TRUST_PROXY": "0",
    }
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from cartag.db import SessionLocal, engine  # noqa: E402
from cartag.models import Base  # noqa: E402
from cartag.services.shop import ensure_catalog  # noqa: E402


def alembic_config() -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


@pytest.fixture(scope="session", autouse=True)
def _database():
    """Builds a fresh schema in the test database once per run."""
    name = engine.url.database or ""
    if not name.endswith("_test"):
        raise RuntimeError(f'Refusing to run tests against database "{name}". Its name must end with _test.')
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    # Build the schema with the real migrations, so they are exercised on every test run.
    command.upgrade(alembic_config(), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(_database):
    """Empties every table before each test."""
    names = ", ".join(f'"{table.name}"' for table in Base.metadata.sorted_tables)
    with engine.begin() as connection:
        connection.execute(text(f"TRUNCATE TABLE {names} RESTART IDENTITY CASCADE"))
    # The migration seeds the twelve products once; emptying every table removed them, so put them back.
    with SessionLocal() as db:
        ensure_catalog(db)
    yield
