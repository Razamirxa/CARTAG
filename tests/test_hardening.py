from fastapi.testclient import TestClient
from sqlalchemy import func, select

from cartag import cli
from cartag.config import get_settings
from cartag.db import SessionLocal
from cartag.errors import AppError
from cartag.main import create_app
from cartag.models import Admin, AuthThrottle
from cartag.security import verify_password
from cartag.services.throttle import (
    MAX_FAILURES,
    MAX_FAILURES_ANY_IP,
    assert_login_allowed,
    clear_login_failures,
    record_login_failure,
)
from tests.helpers import ADMIN_EMAIL, ADMIN_PASSWORD, create_admin


def fail(email: str, ip: str, times: int) -> None:
    with SessionLocal() as db:
        for _ in range(times):
            record_login_failure(db, "admin", email, ip)


def allowed(email: str, ip: str) -> bool:
    with SessionLocal() as db:
        try:
            assert_login_allowed(db, "admin", email, ip)
        except AppError as error:
            assert error.code == "LOCKED"
            return False
    return True


def test_failing_five_times_locks_that_address_only_not_the_account_for_everyone():
    fail("boss@example.com", "address-a", MAX_FAILURES)

    assert allowed("boss@example.com", "address-a") is False
    # A stranger cannot keep the real admin out by failing from their own address.
    assert allowed("boss@example.com", "address-b") is True
    assert allowed("other@example.com", "address-a") is True


def test_a_guesser_who_rotates_addresses_still_hits_the_account_wide_limit():
    for index in range(MAX_FAILURES_ANY_IP):
        fail("boss@example.com", f"address-{index}", 1)

    assert allowed("boss@example.com", "a-brand-new-address") is False


def test_a_good_login_or_a_password_reset_clears_every_counter_for_the_account():
    fail("boss@example.com", "address-a", MAX_FAILURES)
    fail("boss@example.com", "address-b", 2)
    fail("keep@example.com", "address-a", 2)

    with SessionLocal() as db:
        clear_login_failures(db, "admin", "boss@example.com")

    assert allowed("boss@example.com", "address-a") is True
    with SessionLocal() as db:
        keys = set(db.scalars(select(AuthThrottle.key)))
    assert not any(key.startswith("admin:boss@example.com") for key in keys)
    assert any(key.startswith("admin:keep@example.com") for key in keys)


def test_api_docs_can_be_switched_off_outside_production():
    on = TestClient(create_app())
    assert on.get("/api/docs").status_code == 200
    assert on.get("/api/openapi.json").status_code == 200

    off = TestClient(create_app(settings=get_settings().model_copy(update={"api_docs": False})))
    assert off.get("/api/docs").status_code == 404
    assert off.get("/api/openapi.json").status_code == 404


def test_create_admin_if_none_never_resets_an_existing_admin(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD", "a-different-password-9")

    cli.create_admin("new@example.com", "New", if_none=True)  # no admin yet: creates one
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Admin)) == 1

    cli.create_admin("new@example.com", "New", if_none=True)  # an admin exists: leaves everything alone
    cli.create_admin("another@example.com", "Another", if_none=True)
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(Admin)) == 1


def test_create_admin_without_the_flag_still_resets_the_password(monkeypatch):
    create_admin()
    monkeypatch.setenv("ADMIN_PASSWORD", "a-different-password-9")

    cli.create_admin(ADMIN_EMAIL, "Admin")

    with SessionLocal() as db:
        admin = db.scalar(select(Admin).where(Admin.email == ADMIN_EMAIL))
    assert verify_password(admin.password_hash, "a-different-password-9")
    assert not verify_password(admin.password_hash, ADMIN_PASSWORD)
