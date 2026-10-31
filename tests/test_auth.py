from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from cartag.config import get_settings
from cartag.db import SessionLocal
from cartag.models import Admin, AdminSession, AuthThrottle, OtpChallenge, User, UserSession
from tests.helpers import (
    PASSWORD,
    admin_client,
    client_for,
    create_admin,
    make_app,
    register_owner,
)

PHONE_INPUT = "0300 1234567"
PHONE = "+923001234567"
NEW_PHONE_INPUT = "0345 7654321"
NEW_PHONE = "+923457654321"


def ago(**kwargs) -> datetime:
    return datetime.now(UTC) - timedelta(**kwargs)


def one(statement):
    with SessionLocal() as db:
        return db.scalar(statement)


def run(statement):
    with SessionLocal() as db:
        db.execute(statement)
        db.commit()


def reset_request(client, phone: str = PHONE_INPUT):
    return client.post("/api/auth/password/reset/request", json={"phone": phone})


# ---------- registration (no code: the mobile is confirmed later, when a tag is turned on) ----------
def test_registration_needs_only_a_mobile_number_name_and_password():
    app, sms = make_app()
    client, phone = register_owner(app, sms)
    assert phone == PHONE
    assert sms.messages == []  # no text message is sent at registration

    user = client.get("/api/auth/me").json()["user"]
    assert user["name"] == "Ali Raza"
    assert user["phone"] == PHONE
    assert user["phoneVerified"] is False
    assert user["hasCard"] is False
    assert "passwordHash" not in user


def test_registering_a_number_that_already_has_an_account_is_refused():
    app, sms = make_app()
    register_owner(app, sms)
    res = client_for(app).post(
        "/api/auth/register", json={"phone": "03001234567", "name": "Other", "password": PASSWORD}
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "PHONE_TAKEN"
    assert one(select(func.count()).select_from(User)) == 1


def test_session_cookie_is_httponly_and_only_a_hash_is_stored():
    app, _ = make_app()
    client = client_for(app)
    res = client.post("/api/auth/register", json={"phone": PHONE_INPUT, "name": "Ali", "password": PASSWORD})
    cookie = res.headers["set-cookie"]
    name = get_settings().session_cookie_name
    assert name in cookie
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()

    token = cookie.split(f"{name}=")[1].split(";")[0]
    assert token not in one(select(UserSession)).token_hash


def test_weak_password_and_bad_numbers_are_rejected():
    app, _ = make_app()
    client = client_for(app)
    weak = client.post("/api/auth/register", json={"phone": PHONE_INPUT, "name": "Ali", "password": "short"})
    assert weak.status_code == 400
    assert weak.json()["error"]["code"] == "VALIDATION_ERROR"
    assert weak.json()["error"]["details"][0]["field"] == "password"
    for phone in ["+14155552671", "042 35761234", "12345", ""]:
        assert (
            client.post("/api/auth/register", json={"phone": phone, "name": "Ali", "password": PASSWORD}).status_code
            == 400
        )
    assert one(select(func.count()).select_from(User)) == 0


def test_password_is_stored_as_an_argon2id_hash():
    app, sms = make_app()
    register_owner(app, sms)
    user = one(select(User))
    assert user.password_hash.startswith("$argon2id$")
    assert PASSWORD not in user.password_hash


# ---------- login ----------
def test_login_and_logout():
    app, sms = make_app()
    register_owner(app, sms)

    client = client_for(app)
    assert client.post("/api/auth/login", json={"phone": PHONE_INPUT, "password": "wrong password"}).status_code == 401
    ok = client.post("/api/auth/login", json={"phone": "03001234567", "password": PASSWORD})
    assert ok.status_code == 200
    assert client.get("/api/auth/me").json()["user"]["phone"] == PHONE

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["user"] is None


def test_wrong_password_and_unknown_number_give_the_same_error():
    app, sms = make_app()
    register_owner(app, sms)
    client = client_for(app)
    wrong = client.post("/api/auth/login", json={"phone": PHONE_INPUT, "password": "nope nope nope"})
    unknown = client.post("/api/auth/login", json={"phone": NEW_PHONE_INPUT, "password": "nope nope nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_five_failures_lock_the_account_and_unknown_numbers_lock_the_same_way():
    app, sms = make_app()
    register_owner(app, sms)
    client = client_for(app)

    for phone in [PHONE_INPUT, NEW_PHONE_INPUT]:
        for _ in range(5):
            assert client.post("/api/auth/login", json={"phone": phone, "password": "wrong wrong"}).status_code == 401
        locked = client.post("/api/auth/login", json={"phone": phone, "password": PASSWORD})
        assert locked.status_code == 429
        assert locked.json()["error"]["code"] == "LOCKED"


def test_lock_expires():
    app, sms = make_app()
    register_owner(app, sms)
    client = client_for(app)
    for _ in range(5):
        client.post("/api/auth/login", json={"phone": PHONE_INPUT, "password": "wrong wrong"})
    run(update(AuthThrottle).values(locked_until=ago(seconds=1)))
    assert client.post("/api/auth/login", json={"phone": PHONE_INPUT, "password": PASSWORD}).status_code == 200


def test_blocked_owner_cannot_log_in_and_loses_existing_sessions():
    app, sms = make_app()
    client, _ = register_owner(app, sms)
    run(update(User).values(status="BLOCKED"))

    assert client.get("/api/auth/me").json()["user"] is None
    res = client_for(app).post("/api/auth/login", json={"phone": PHONE_INPUT, "password": PASSWORD})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ACCOUNT_BLOCKED"


# ---------- password reset ----------
def test_reset_text_message_and_the_answer_are_the_same_for_any_number():
    app, sms = make_app()
    register_owner(app, sms)
    known = reset_request(client_for(app), PHONE_INPUT)
    unknown = reset_request(client_for(app), NEW_PHONE_INPUT)
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"ok": True, "resendAfterSeconds": 60}
    assert [to for to, _ in sms.messages] == [PHONE]  # only the real account was texted


def test_reset_with_a_code_ends_every_session_and_allows_the_new_password():
    app, sms = make_app()
    client, _ = register_owner(app, sms)

    other = client_for(app)
    reset_request(other)
    res = other.post(
        "/api/auth/password/reset/confirm",
        json={"phone": PHONE_INPUT, "otp": sms.last_code(PHONE), "newPassword": "brand new password"},
    )
    assert res.status_code == 200

    assert client.get("/api/auth/me").json()["user"] is None
    assert client_for(app).post("/api/auth/login", json={"phone": PHONE_INPUT, "password": PASSWORD}).status_code == 401
    new = client_for(app).post("/api/auth/login", json={"phone": PHONE_INPUT, "password": "brand new password"})
    assert new.status_code == 200


def test_otp_stores_only_a_hash_and_codes_are_one_time_and_expire():
    app, sms = make_app()
    register_owner(app, sms)
    client = client_for(app)
    reset_request(client)
    code = sms.last_code(PHONE)
    row = one(select(OtpChallenge))
    assert code not in row.code_hash
    assert len(row.code_hash) == 64

    body = {"phone": PHONE_INPUT, "otp": code, "newPassword": "brand new password"}
    # Two requests at once with the same code: exactly one wins.
    with ThreadPoolExecutor(2) as pool:
        futures = [
            pool.submit(lambda: client_for(app).post("/api/auth/password/reset/confirm", json=body)) for _ in range(2)
        ]
        assert sorted(f.result().status_code for f in futures) == [200, 400]


def test_wrong_code_five_times_kills_it_and_an_expired_code_is_refused():
    app, sms = make_app()
    register_owner(app, sms)
    client = client_for(app)
    reset_request(client)
    real = sms.last_code(PHONE)
    wrong = "111111" if real == "000000" else "000000"

    for _ in range(5):
        res = client.post(
            "/api/auth/password/reset/confirm",
            json={"phone": PHONE_INPUT, "otp": wrong, "newPassword": "brand new password"},
        )
        assert res.json()["error"]["code"] == "INVALID_OTP"
    res = client.post(
        "/api/auth/password/reset/confirm",
        json={"phone": PHONE_INPUT, "otp": real, "newPassword": "brand new password"},
    )
    assert res.status_code == 400

    run(update(OtpChallenge).values(created_at=ago(minutes=5)))
    reset_request(client)
    run(update(OtpChallenge).values(expires_at=ago(seconds=1)))
    res = client.post(
        "/api/auth/password/reset/confirm",
        json={"phone": PHONE_INPUT, "otp": sms.last_code(PHONE), "newPassword": "brand new password"},
    )
    assert res.status_code == 400


def test_cooldown_applies_to_unknown_numbers_too_so_timing_cannot_reveal_accounts():
    app, _ = make_app()
    client = client_for(app)
    reset_request(client, NEW_PHONE_INPUT)
    again = reset_request(client, NEW_PHONE_INPUT)
    assert again.status_code == 429
    assert again.json()["error"]["code"] == "OTP_COOLDOWN"
    assert "retry-after" in again.headers


def test_codes_per_phone_per_hour_are_capped():
    app, _ = make_app()
    old = ago(minutes=10)
    with SessionLocal() as db:
        db.add_all(
            OtpChallenge(phone=PHONE, purpose="RESET_PASSWORD", code_hash="x", expires_at=old, created_at=old)
            for _ in range(5)
        )
        db.commit()
    res = reset_request(client_for(app))
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "OTP_LIMIT"


# ---------- activation code ----------
def test_activation_code_goes_to_the_owners_own_number_and_needs_a_login():
    app, sms = make_app()
    assert client_for(app).post("/api/me/activation/otp").status_code == 401

    client, phone = register_owner(app, sms)
    res = client.post("/api/me/activation/otp")
    assert res.status_code == 200
    assert sms.messages[-1][0] == phone
    assert "CARTAG" in sms.messages[-1][1]
    assert client.post("/api/me/activation/otp").status_code == 429  # cooldown


# ---------- changing the mobile number ----------
def test_changing_the_mobile_number_needs_the_password_and_a_code_sent_to_the_new_number():
    app, sms = make_app()
    client, _ = register_owner(app, sms)
    other = client_for(app)
    other.post("/api/auth/login", json={"phone": PHONE_INPUT, "password": PASSWORD})

    bad = client.post("/api/me/phone/change/request", json={"phone": NEW_PHONE_INPUT, "password": "wrong password"})
    assert bad.status_code == 401
    assert sms.messages == []

    ok = client.post("/api/me/phone/change/request", json={"phone": NEW_PHONE_INPUT, "password": PASSWORD})
    assert ok.status_code == 200
    assert sms.messages[-1][0] == NEW_PHONE

    confirmed = client.post(
        "/api/me/phone/change/confirm", json={"phone": NEW_PHONE_INPUT, "otp": sms.last_code(NEW_PHONE)}
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["user"]["phone"] == NEW_PHONE
    assert confirmed.json()["user"]["phoneVerified"] is True

    # The session that made the change stays; every other one is ended.
    assert client.get("/api/auth/me").json()["user"]["phone"] == NEW_PHONE
    assert other.get("/api/auth/me").json()["user"] is None
    assert (
        client_for(app).post("/api/auth/login", json={"phone": NEW_PHONE_INPUT, "password": PASSWORD}).status_code
        == 200
    )
    assert client_for(app).post("/api/auth/login", json={"phone": PHONE_INPUT, "password": PASSWORD}).status_code == 401


def test_a_number_that_belongs_to_someone_else_is_not_texted_and_the_answer_does_not_say_so():
    app, sms = make_app()
    client, _ = register_owner(app, sms)
    register_owner(app, sms, NEW_PHONE_INPUT, "Sara Khan")
    sent_before = len(sms.messages)
    res = client.post("/api/me/phone/change/request", json={"phone": NEW_PHONE_INPUT, "password": PASSWORD})
    assert res.status_code == 200
    assert res.json() == {"ok": True, "resendAfterSeconds": 60}
    assert len(sms.messages) == sent_before


def test_changing_to_your_own_number_is_refused():
    app, sms = make_app()
    client, _ = register_owner(app, sms)
    res = client.post("/api/me/phone/change/request", json={"phone": PHONE_INPUT, "password": PASSWORD})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "SAME_PHONE"


def test_five_wrong_passwords_lock_sensitive_changes():
    app, sms = make_app()
    client, _ = register_owner(app, sms)
    for _ in range(5):
        assert (
            client.post(
                "/api/me/phone/change/request", json={"phone": NEW_PHONE_INPUT, "password": "nope nope"}
            ).status_code
            == 401
        )
    locked = client.post("/api/me/phone/change/request", json={"phone": NEW_PHONE_INPUT, "password": PASSWORD})
    assert locked.status_code == 429


# ---------- CSRF and request limits ----------
def test_state_changing_request_from_another_origin_is_blocked():
    app, _ = make_app()
    res = client_for(app).post("/api/auth/logout", json={}, headers={"Origin": "https://evil.example"})
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "BAD_ORIGIN"


def test_cross_site_fetch_without_an_origin_is_blocked():
    app, _ = make_app()
    res = client_for(app).post("/api/auth/logout", json={}, headers={"Sec-Fetch-Site": "cross-site"})
    assert res.status_code == 403


def test_our_own_origin_is_allowed():
    app, _ = make_app()
    res = client_for(app).post("/api/auth/logout", json={}, headers={"Origin": get_settings().public_origin})
    assert res.status_code == 200


def test_oversized_bodies_are_refused():
    app, _ = make_app()
    res = client_for(app).post("/api/auth/login", content=b"x" * 200_000, headers={"Content-Type": "application/json"})
    assert res.status_code == 413


def test_invalid_json_is_a_clean_400():
    app, _ = make_app()
    res = client_for(app).post("/api/auth/login", content=b"{not json", headers={"Content-Type": "application/json"})
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "BAD_JSON"


def test_unknown_api_paths_return_json_404():
    app, _ = make_app()
    res = client_for(app).get("/api/nothing/here")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_security_headers_are_on_every_response():
    app, _ = make_app()
    res = client_for(app).get("/api/auth/me")
    assert "default-src 'self'" in res.headers["content-security-policy"]
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "SAMEORIGIN"


# ---------- admin login ----------
def test_admin_login_and_an_owner_session_is_not_an_admin_session():
    app, sms = make_app()
    owner, _ = register_owner(app, sms)
    assert owner.get("/api/admin/stats").status_code == 401

    create_admin()
    admin = admin_client(app)
    assert admin.get("/api/admin/stats").status_code == 200
    assert admin.get("/api/admin/auth/me").json()["admin"]["email"] == "admin@example.com"
    # The admin cookie does not make the browser an owner either.
    assert admin.get("/api/me/tags").status_code == 401


def test_admin_bad_credentials_are_identical_and_five_failures_lock():
    app, _ = make_app()
    create_admin()
    client = client_for(app)
    wrong = client.post("/api/admin/auth/login", json={"email": "admin@example.com", "password": "nope nope nope"})
    unknown = client.post("/api/admin/auth/login", json={"email": "who@example.com", "password": "nope nope nope"})
    assert wrong.status_code == 401
    assert wrong.json() == unknown.json()

    for _ in range(4):
        client.post("/api/admin/auth/login", json={"email": "admin@example.com", "password": "nope nope nope"})
    locked = client.post("/api/admin/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"})
    assert locked.status_code == 429


def test_disabled_admin_cannot_log_in():
    app, _ = make_app()
    create_admin()
    run(update(Admin).values(disabled_at=datetime.now(UTC)))
    res = client_for(app).post(
        "/api/admin/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    assert res.status_code == 401


def test_admin_session_expires_after_two_idle_hours():
    app, _ = make_app()
    admin = admin_client(app)
    run(update(AdminSession).values(last_seen_at=ago(hours=3)))
    assert admin.get("/api/admin/stats").status_code == 401


def test_admin_email_with_a_dev_domain_is_accepted():
    app, _ = make_app()
    create_admin("admin@cartag.local", "admin-password-1")
    res = client_for(app).post(
        "/api/admin/auth/login", json={"email": "Admin@CARTAG.local", "password": "admin-password-1"}
    )
    assert res.status_code == 200
