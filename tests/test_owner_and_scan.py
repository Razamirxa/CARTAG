import re

import pytest
from sqlalchemy import func, select, update

from cartag.db import SessionLocal
from cartag.models import AuditLog, ContactCard, ScanEvent, Tag, User
from tests.helpers import (
    CARD,
    EMERGENCY_CARD,
    PASSWORD,
    activate,
    admin_client,
    client_for,
    generate_batch,
    make_app,
    register_owner,
    sell_batch,
)


def count(model, *where) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def one(statement):
    with SessionLocal() as db:
        return db.scalar(statement)


def run(statement):
    with SessionLocal() as db:
        db.execute(statement)
        db.commit()


@pytest.fixture
def world():
    """An admin, an owner with one active tag, and one more tag that is sold but not active."""
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 3)
    admin.post(f"/api/admin/tags/{codes[0]}/mark-sold")
    admin.post(f"/api/admin/tags/{codes[1]}/mark-sold")
    owner, phone = register_owner(app, sms)
    assert activate(owner, sms, phone, codes[0]).status_code == 201
    return {
        "app": app,
        "sms": sms,
        "admin": admin,
        "owner": owner,
        "phone": phone,
        "active": codes[0],
        "sold": codes[1],
        "in_stock": codes[2],
    }


# ---------- contact card ----------
def test_owner_reads_and_edits_the_contact_card(world):
    owner = world["owner"]
    assert owner.get("/api/me/card").json()["card"] == {
        "displayName": "Ali Raza",
        "emergencyEnabled": False,
        "bloodGroup": None,
        "emergencyName": None,
        "emergencyRelationship": None,
        "emergencyPhone": None,
    }

    res = owner.put("/api/me/card", json=EMERGENCY_CARD)
    assert res.status_code == 200
    card = res.json()["card"]
    assert card["emergencyEnabled"] is True
    assert card["bloodGroup"] == "O+"
    assert card["emergencyPhone"] == "+923457654321"
    assert count(ContactCard) == 1
    assert count(AuditLog, AuditLog.action == "card.update") == 1


def test_emergency_mode_needs_a_contact_when_it_is_on(world):
    owner = world["owner"]
    bad = owner.put("/api/me/card", json={"displayName": "Ali Raza", "emergencyEnabled": True, "bloodGroup": "A+"})
    assert bad.status_code == 400
    fields = {i["field"] for i in bad.json()["error"]["details"]}
    assert fields == {"emergencyName", "emergencyRelationship", "emergencyPhone"}

    # Blood group is optional, and nothing is needed while emergency mode is off.
    assert owner.put("/api/me/card", json={**EMERGENCY_CARD, "bloodGroup": None}).status_code == 200
    assert owner.put("/api/me/card", json={"displayName": "Ali Raza", "emergencyEnabled": False}).status_code == 200


@pytest.mark.parametrize(
    "bad",
    [
        {"displayName": ""},
        {"displayName": "A"},
        {"bloodGroup": "Z+"},
        {"emergencyEnabled": "yes"},
        {"emergencyEnabled": True, "emergencyName": "X", "emergencyRelationship": "Y", "emergencyPhone": "123"},
    ],
)
def test_contact_card_rejects_bad_data(world, bad):
    assert world["owner"].put("/api/me/card", json={**CARD, **bad}).status_code == 400


def test_contact_card_needs_a_login(world):
    assert client_for(world["app"]).get("/api/me/card").status_code == 401
    assert client_for(world["app"]).put("/api/me/card", json=CARD).status_code == 401


# ---------- owner turns a tag off and on ----------
def test_owner_turns_a_tag_off_and_on_and_it_is_recorded(world):
    owner, code = world["owner"], world["active"]
    off = owner.post(f"/api/me/tags/{code}/turn-off")
    assert off.json()["tag"]["status"] == "TURNED_OFF"
    assert owner.post(f"/api/me/tags/{code}/turn-off").status_code == 409
    assert owner.post(f"/api/me/tags/{code}/turn-on").json()["tag"]["status"] == "ACTIVE"
    assert count(AuditLog, AuditLog.action == "tag.turn_off") == 1
    assert count(AuditLog, AuditLog.action == "tag.turn_on") == 1


def test_owners_only_ever_see_their_own_tags_and_strangers_get_not_found(world):
    stranger, _ = register_owner(world["app"], world["sms"], "0300 9999999", "Stranger")
    code = world["active"]
    assert stranger.get(f"/api/me/tags/{code}").status_code == 404
    assert stranger.post(f"/api/me/tags/{code}/turn-off").status_code == 404
    assert one(select(Tag.status).where(Tag.code == code)) == "ACTIVE"
    assert stranger.get("/api/me/tags").json()["tags"] == []


def test_a_retired_tag_can_never_be_turned_on_again(world):
    owner, admin, code = world["owner"], world["admin"], world["active"]
    assert admin.post(f"/api/admin/tags/{code}/retire", json={"reason": "Damaged"}).status_code == 200
    on = owner.post(f"/api/me/tags/{code}/turn-on")
    assert on.status_code == 403
    assert on.json()["error"]["code"] == "TAG_RETIRED"
    assert owner.post(f"/api/me/tags/{code}/turn-off").status_code == 403
    assert admin.post(f"/api/admin/tags/{code}/retire", json={}).status_code == 409  # already retired
    assert one(select(Tag.retired_at).where(Tag.code == code)) is not None


def test_there_is_no_way_to_move_a_tag_to_another_owner(world):
    admin, code = world["admin"], world["active"]
    for action in ("reassign", "unlink", "enable", "disable"):
        assert admin.post(f"/api/admin/tags/{code}/{action}", json={"phone": "0345 7654321"}).status_code == 404


# ---------- scan page ----------
def scan(world, code, **kwargs):
    return client_for(world["app"]).get(f"/t/{code}", **kwargs)


def test_the_link_exactly_as_the_qr_holds_it_opens_the_scan_page(world):
    """The QR stores the link in upper case, so a phone opens /T/CODE. A lower-case-only route misses it."""
    from urllib.parse import urlsplit

    from cartag.qr.matrix import qr_payload, tag_url

    path = urlsplit(qr_payload(tag_url("https://cartag.pk", world["active"]))).path
    assert path.startswith("/T/")
    res = client_for(world["app"]).get(path)
    assert res.status_code == 200
    assert "Contact the owner" in res.text


def test_scan_page_shows_name_and_two_buttons_but_never_the_number_as_text(world):
    res = scan(world, world["active"])
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert res.headers["cache-control"] == "no-store"
    assert res.headers["referrer-policy"] == "no-referrer"
    text = res.text
    assert "Ali Raza" in text
    assert "Call Owner" in text
    assert "WhatsApp Owner" in text
    assert 'href="tel:+923001234567"' in text
    assert "https://wa.me/923001234567?text=" in text

    # The number is only inside the two links, never printed where a person reads it.
    visible = re.sub(r"<[^>]+>", " ", text)
    for number in ("0300 1234567", "03001234567", "+923001234567", "923001234567", "300 1234567"):
        assert number not in visible
    # No vehicle details in this version.
    assert "plate" not in text.lower()
    assert len(res.content) < 12_000
    assert "<script" not in text


def test_scan_page_is_case_insensitive_because_the_qr_holds_an_upper_case_url(world):
    assert "Ali Raza" in scan(world, world["active"].lower()).text


def test_emergency_details_are_hidden_until_the_owner_turns_emergency_mode_on(world):
    owner, code = world["owner"], world["active"]
    assert "Emergency" not in scan(world, code).text
    assert "tel:+923457654321" not in scan(world, code).text

    owner.put("/api/me/card", json=EMERGENCY_CARD)
    text = scan(world, code).text
    assert "Emergency information" in text
    assert "O+" in text
    assert "Sara Khan (Wife)" in text
    assert 'href="tel:+923457654321"' in text
    assert "check them before you use them" in text
    visible = re.sub(r"<[^>]+>", " ", text)
    assert "0345 7654321" not in visible
    assert "923457654321" not in visible

    owner.put("/api/me/card", json={**EMERGENCY_CARD, "emergencyEnabled": False})
    after = scan(world, code).text
    assert "Emergency information" not in after
    assert "tel:+923457654321" not in after
    assert "Sara Khan" not in after


def test_emergency_mode_without_a_blood_group_still_shows_the_contact(world):
    world["owner"].put("/api/me/card", json={**EMERGENCY_CARD, "bloodGroup": None})
    text = scan(world, world["active"]).text
    assert "Blood group" not in text
    assert "Sara Khan" in text


def test_scan_page_says_not_active_and_shows_no_owner_details_before_the_owner_turns_it_on(world):
    for code in (world["sold"], world["in_stock"]):
        res = scan(world, code)
        assert res.status_code == 200
        assert "not active yet" in res.text
        assert f"/activate/{code}" in res.text
        assert "tel:" not in res.text
        assert "Ali Raza" not in res.text


def test_turned_off_and_retired_tags_show_no_owner_details_and_say_which_it_is(world):
    owner, admin, code = world["owner"], world["admin"], world["active"]
    owner.post(f"/api/me/tags/{code}/turn-off")
    off = scan(world, code)
    assert off.status_code == 200
    assert "turned off" in off.text
    for private in ("Ali Raza", "tel:", "wa.me"):
        assert private not in off.text

    admin.post(f"/api/admin/tags/{code}/retire", json={})
    retired = scan(world, code)
    assert retired.status_code == 200
    assert "retired" in retired.text
    for private in ("Ali Raza", "tel:", "wa.me", "turned off"):
        assert private not in retired.text


def test_scan_page_no_longer_shows_a_blocked_owners_details(world):
    run(update(User).values(status="BLOCKED"))
    text = scan(world, world["active"]).text
    assert "Ali Raza" not in text
    assert "turned off" in text


def test_unknown_malformed_and_probing_codes_all_get_the_same_generic_404(world):
    bodies = set()
    for code in ["ZZZZZZZZZZ", "short", "ABC%20DEF", "A" * 80, "..%2f..%2fetc", "a/b/c"]:
        res = scan(world, code)
        assert res.status_code == 404, code
        bodies.add(res.text)
    assert len(bodies) == 1


def test_scan_page_escapes_anything_an_owner_typed():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 1)
    sell_batch(admin, batch_id)
    owner, phone = register_owner(app, sms)
    evil = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    card = {**EMERGENCY_CARD, "displayName": evil, "emergencyName": evil, "emergencyRelationship": "<b>x</b>"}
    assert activate(owner, sms, phone, codes[0], card).status_code == 201

    text = client_for(app).get(f"/t/{codes[0]}").text
    assert "<script>alert(1)" not in text
    assert "<img src=x" not in text
    assert "<b>x</b>" not in text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in text


def test_scan_page_switches_to_urdu_right_to_left_on_request_or_from_the_browser_language(world):
    code = world["active"]
    ur = scan(world, code, params={"lang": "ur"})
    assert 'lang="ur" dir="rtl"' in ur.text
    assert "مالک سے رابطہ کریں" in ur.text
    assert "مالک کو کال کریں" in ur.text

    from_header = scan(world, code, headers={"Accept-Language": "ur-PK,ur;q=0.9,en;q=0.5"})
    assert 'dir="rtl"' in from_header.text
    assert 'lang="en" dir="ltr"' in scan(world, code, headers={"Accept-Language": "en-US,en;q=0.9"}).text
    assert 'lang="en"' in scan(world, code, headers={"Accept-Language": ""}).text

    world["owner"].put("/api/me/card", json=EMERGENCY_CARD)
    assert "ہنگامی معلومات" in scan(world, code, params={"lang": "ur"}).text


def test_every_scan_is_recorded_with_a_hashed_address(world):
    scan(world, world["active"])
    scan(world, world["sold"])
    scan(world, "ZZZZZZZZZZ")
    world["admin"].post(f"/api/admin/tags/{world['sold']}/retire", json={})
    scan(world, world["sold"])

    with SessionLocal() as db:
        scans = list(db.scalars(select(ScanEvent).order_by(ScanEvent.id)))
    assert [s.outcome.value for s in scans] == ["ACTIVE_PAGE", "NOT_ACTIVE_PAGE", "NOT_FOUND", "RETIRED_PAGE"]
    for entry in scans:
        assert re.fullmatch(r"[0-9a-f]{32}", entry.ip_hash)
        assert "testclient" not in entry.ip_hash


def test_the_json_endpoint_follows_the_same_privacy_rules(world):
    client = client_for(world["app"])
    active = client.get(f"/api/public/tags/{world['active']}").json()
    assert active["state"] == "active"
    assert active["owner"]["name"] == "Ali Raza"
    assert active["emergency"] is None
    assert "passwordHash" not in str(active)

    assert client.get(f"/api/public/tags/{world['sold']}").json() == {
        "state": "not_active",
        "code": world["sold"],
        "ready": True,
    }
    assert client.get(f"/api/public/tags/{world['in_stock']}").json()["ready"] is False
    assert client.get("/api/public/tags/ZZZZZZZZZZ").status_code == 404


def test_someone_who_keeps_trying_codes_that_do_not_exist_gets_slowed_down():
    app, _ = make_app(rate_limits=True)
    client = client_for(app)
    blocked_at = 0
    for i in range(1, 41):
        if client.get(f"/t/NOPE{i:06d}").status_code == 429:
            blocked_at = i
            break
    assert 0 < blocked_at <= 31


def test_real_scans_from_the_same_address_are_still_fine_in_normal_use():
    app, _ = make_app(rate_limits=True)
    admin = admin_client(app)
    _, codes = generate_batch(admin, 1)
    client = client_for(app)
    for _ in range(20):
        assert client.get(f"/t/{codes[0]}").status_code == 200


# ---------- closing the account ----------
def test_account_deletion_needs_the_password_and_waits_for_staff(world):
    owner = world["owner"]
    assert owner.post("/api/me/delete-request", json={"password": "wrong password"}).status_code == 401
    assert owner.get("/api/me/delete-request").json()["request"] is None

    res = owner.post("/api/me/delete-request", json={"password": PASSWORD, "reason": "Sold the car"})
    assert res.status_code == 201
    assert res.json()["request"]["status"] == "PENDING"
    assert owner.post("/api/me/delete-request", json={"password": PASSWORD}).status_code == 409
    # Nothing changes until staff approve it.
    assert "Ali Raza" in scan(world, world["active"]).text
    assert owner.get("/api/auth/me").json()["user"] is not None


def test_approving_a_deletion_removes_public_details_retires_tags_and_keeps_only_what_is_needed(world):
    owner, admin, app = world["owner"], world["admin"], world["app"]
    owner.put("/api/me/card", json=EMERGENCY_CARD)
    owner.post("/api/me/delete-request", json={"password": PASSWORD, "reason": "Closing"})

    pending = admin.get("/api/admin/deletion-requests?status=PENDING").json()
    assert pending["total"] == 1
    item = pending["items"][0]
    assert item["user"]["name"] == "Ali Raza"
    assert item["tagCount"] == 1
    assert admin.get("/api/admin/stats").json()["pendingDeletions"] == 1

    res = admin.post(f"/api/admin/deletion-requests/{item['id']}/approve", json={"note": "Verified by phone"})
    assert res.status_code == 200
    assert res.json()["request"]["status"] == "APPROVED"

    # Public details are gone and the tag is stopped for good.
    page = scan(world, world["active"]).text
    assert "retired" in page
    for private in ("Ali Raza", "Sara Khan", "tel:", "O+"):
        assert private not in page
    assert count(ContactCard) == 0
    assert one(select(Tag.status).where(Tag.code == world["active"])) == "RETIRED"

    # The account row stays for orders and records, but identifies nobody and cannot be used.
    user = one(select(User))
    assert user.status == "DELETED"
    assert user.name == "Deleted customer"
    assert user.phone.startswith("deleted:")
    assert user.deleted_at is not None
    assert owner.get("/api/auth/me").json()["user"] is None
    assert (
        client_for(app).post("/api/auth/login", json={"phone": "0300 1234567", "password": PASSWORD}).status_code == 401
    )
    assert count(AuditLog, AuditLog.action == "account.deletion_approved") == 1

    # The number can be registered again by a new account.
    assert (
        client_for(app)
        .post("/api/auth/register", json={"phone": "0300 1234567", "name": "New", "password": PASSWORD})
        .status_code
        == 201
    )


def test_rejecting_a_deletion_changes_nothing_and_a_decided_request_cannot_be_decided_again(world):
    owner, admin = world["owner"], world["admin"]
    owner.post("/api/me/delete-request", json={"password": PASSWORD})
    request_id = admin.get("/api/admin/deletion-requests").json()["items"][0]["id"]

    assert (
        admin.post(f"/api/admin/deletion-requests/{request_id}/reject", json={"note": "Not verified"}).status_code
        == 200
    )
    assert admin.post(f"/api/admin/deletion-requests/{request_id}/approve", json={}).status_code == 409
    assert "Ali Raza" in scan(world, world["active"]).text
    assert owner.get("/api/auth/me").json()["user"] is not None
    # After a rejection the owner may ask again.
    assert owner.post("/api/me/delete-request", json={"password": PASSWORD}).status_code == 201
