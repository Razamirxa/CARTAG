import re
import zipfile
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from sqlalchemy import func, select, update

from cartag.db import SessionLocal
from cartag.domain import TAG_CODE_ALPHABET, is_valid_tag_code
from cartag.models import (
    AuditLog,
    ContactCard,
    OtpChallenge,
    Tag,
    TagBatch,
)
from tests.helpers import (
    CARD,
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


# ---------- team panel is closed to everyone else ----------
def test_team_routes_are_closed_to_anyone_who_is_not_an_admin():
    app, _ = make_app()
    client = client_for(app)
    for path in ["stats", "batches", "tags", "users", "activity", "deletion-requests"]:
        assert client.get(f"/api/admin/{path}").status_code == 401
    assert client.post("/api/admin/batches/generate", json={"name": "x", "quantity": 1}).status_code == 401


# ---------- batch generation ----------
def test_generation_makes_unique_valid_random_codes_with_sequential_serials():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 200)

    assert len(codes) == len(set(codes)) == 200
    with SessionLocal() as db:
        tags = list(db.scalars(select(Tag).order_by(Tag.serial)))
    assert [t.serial for t in tags] == list(range(1, 201))
    for tag in tags:
        assert len(tag.code) == 10
        assert is_valid_tag_code(tag.code)
        assert all(ch in TAG_CODE_ALPHABET for ch in tag.code)
        assert tag.status == "NOT_ACTIVE"
        assert tag.stock_status == "IN_STOCK"
    assert tags[0].code != tags[1].code
    assert "000001" not in tags[0].code

    batch = one(select(TagBatch))
    assert batch.base_url == "http://localhost:5173"
    assert batch.quantity == 200
    assert str(batch.id) == batch_id


def test_generation_handles_ten_thousand_tags_in_one_go():
    app, _ = make_app()
    admin = admin_client(app)
    res = admin.post("/api/admin/batches/generate", json={"name": "Big", "quantity": 10_000})
    assert res.status_code == 201
    assert count(Tag) == 10_000
    assert one(select(func.count(func.distinct(Tag.code)))) == 10_000


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x", "quantity": 0},
        {"name": "Ok name", "quantity": 100_001},
        {"name": "Ok name", "quantity": 1.5},
        {"name": "Ok name", "quantity": "5"},
        {"name": "Ok name"},
    ],
)
def test_generation_validates_the_request(body):
    app, _ = make_app()
    admin = admin_client(app)
    assert admin.post("/api/admin/batches/generate", json=body).status_code == 400
    assert count(Tag) == 0


def test_generation_is_audited():
    app, _ = make_app()
    admin = admin_client(app)
    generate_batch(admin, 3)
    assert one(select(AuditLog.actor_type).where(AuditLog.action == "batch.generate")) == "ADMIN"


# ---------- batch import ----------
def test_import_reads_csv_normalising_case_and_skipping_the_header():
    app, _ = make_app()
    admin = admin_client(app)
    csv = 'code,note\r\nk7x9m2qp4a,first\r\n"B2C3D4E5F6",second\r\n\r\nZZZZZZ9999'
    res = admin.post("/api/admin/batches/import", json={"name": "Imported", "csv": csv})
    assert res.status_code == 201
    with SessionLocal() as db:
        codes = list(db.scalars(select(Tag.code).order_by(Tag.serial)))
    assert codes == ["K7X9M2QP4A", "B2C3D4E5F6", "ZZZZZZ9999"]
    assert res.json()["batch"]["source"] == "IMPORTED"


def test_import_rejects_the_whole_file_when_any_line_is_bad_or_repeated():
    app, _ = make_app()
    admin = admin_client(app)
    res = admin.post(
        "/api/admin/batches/import", json={"name": "Bad", "csv": "K7X9M2QP4A\nnot a code!\nK7X9M2QP4A\nSHORT"}
    )
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "IMPORT_INVALID"
    assert len(res.json()["error"]["details"]) == 3
    assert count(Tag) == 0
    assert count(TagBatch) == 0


def test_import_rejects_codes_that_already_exist():
    app, _ = make_app()
    admin = admin_client(app)
    _, codes = generate_batch(admin, 2)
    res = admin.post("/api/admin/batches/import", json={"name": "Clash", "csv": f"{codes[0]}\nAAAAAAAAAA"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "IMPORT_DUPLICATES"
    assert count(Tag) == 2


def test_import_accepts_a_file_larger_than_the_normal_request_limit():
    app, _ = make_app()
    admin = admin_client(app)
    lines = "\n".join(f"A{i:09d}" for i in range(20_000))
    assert len(lines) > 100_000
    assert admin.post("/api/admin/batches/import", json={"name": "Large", "csv": lines}).status_code == 201
    assert count(Tag) == 20_000


def test_import_body_is_never_read_for_someone_who_is_not_an_admin():
    app, _ = make_app()
    res = client_for(app).post("/api/admin/batches/import", json={"name": "Nope", "csv": "A" * 200_000})
    assert res.status_code == 401


def test_import_rejects_a_body_over_the_import_limit():
    app, _ = make_app()
    admin = admin_client(app)
    assert admin.post("/api/admin/batches/import", json={"name": "Huge", "csv": "A" * 6_100_000}).status_code == 413


# ---------- batch export ----------
def test_csv_export_lists_serial_code_and_url_for_the_printer_and_holds_no_secrets():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 5)

    res = admin.get(f"/api/admin/batches/{batch_id}/export?format=csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert res.headers["cache-control"] == "no-store"

    rows = res.text.strip().split("\r\n")
    assert rows[0] == "serial,code,url"
    assert len(rows) == 6
    assert rows[1].split(",") == ["000001", codes[0], f"http://localhost:5173/t/{codes[0]}"]


def test_export_uses_the_base_url_the_batch_was_printed_with_not_the_current_setting():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 1)
    run(update(TagBatch).values(base_url="https://old-domain.pk"))
    assert f"https://old-domain.pk/t/{codes[0]}" in admin.get(f"/api/admin/batches/{batch_id}/export?format=csv").text


def test_pdf_export_has_one_page_per_tag():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, _ = generate_batch(admin, 7)
    res = admin.get(f"/api/admin/batches/{batch_id}/export?format=pdf")
    assert res.status_code == 200
    assert res.content.startswith(b"%PDF-")
    assert len(re.findall(rb"/Type\s*/Page\b", res.content)) == 7


def test_svg_and_eps_come_as_a_zip_with_one_file_per_tag():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 3)

    for fmt in ("svg", "eps"):
        res = admin.get(f"/api/admin/batches/{batch_id}/export?format={fmt}")
        assert res.status_code == 200
        with zipfile.ZipFile(BytesIO(res.content)) as bundle:
            names = bundle.namelist()
            assert names == [f"{i + 1:06d}_{codes[i]}.{fmt}" for i in range(3)]
            first = bundle.read(names[0]).decode()
        assert first.startswith("<?xml") if fmt == "svg" else first.startswith("%!PS-Adobe")


def test_export_size_can_be_chosen_per_download_and_is_in_the_file_name():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 2)

    res = admin.get(f"/api/admin/batches/{batch_id}/export?format=svg&sizeMm=30")
    assert "-30mm-svg.zip" in res.headers["content-disposition"]
    with zipfile.ZipFile(BytesIO(res.content)) as bundle:
        assert 'width="30mm"' in bundle.read(bundle.namelist()[0]).decode()

    assert "-25mm-" in admin.get(f"/api/admin/batches/{batch_id}/export?format=svg").headers["content-disposition"]
    assert admin.get(f"/api/admin/batches/{batch_id}/export?format=svg&sizeMm=5").status_code == 400
    assert admin.get(f"/api/admin/batches/{batch_id}?sizeMm=33").json()["print"]["physicalMm"] == 33


def test_export_is_audited_rejects_bad_formats_and_unknown_batches_404():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, _ = generate_batch(admin, 1)
    admin.get(f"/api/admin/batches/{batch_id}/export?format=csv")
    assert count(AuditLog, AuditLog.action == "batch.export") == 1

    assert admin.get(f"/api/admin/batches/{batch_id}/export?format=docx").status_code == 400
    assert admin.get(f"/api/admin/batches/{batch_id}/export?format=pdf&part=2").status_code == 400
    unknown = "00000000-0000-4000-8000-000000000000"
    assert admin.get(f"/api/admin/batches/{unknown}/export?format=csv").status_code == 404
    assert admin.get("/api/admin/batches/not-a-uuid/export?format=csv").status_code == 400


def test_batch_detail_reports_the_print_size_check_and_stock():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, _ = generate_batch(admin, 4)
    body = admin.get(f"/api/admin/batches/{batch_id}").json()
    assert body["print"]["physicalMm"] == 25
    assert body["print"]["printable"] is True
    assert body["print"]["mode"] == "alphanumeric"
    assert body["byStatus"] == {"NOT_ACTIVE": 4}
    assert body["byStock"] == {"IN_STOCK": 4}
    assert body["pdfParts"] == 1


# ---------- stock: only a sold tag can be activated ----------
def test_marking_a_tag_sold_is_recorded_and_cannot_be_repeated():
    app, _ = make_app()
    admin = admin_client(app)
    _, codes = generate_batch(admin, 2)
    res = admin.post(f"/api/admin/tags/{codes[0]}/mark-sold")
    assert res.status_code == 200
    assert res.json()["tag"]["stockStatus"] == "SOLD"
    assert res.json()["tag"]["status"] == "NOT_ACTIVE"  # a sold tag is still not active
    assert admin.post(f"/api/admin/tags/{codes[0]}/mark-sold").status_code == 409
    assert count(AuditLog, AuditLog.action == "tag.mark_sold") == 1


def test_marking_a_whole_batch_sold_changes_only_what_is_in_stock():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 5)
    admin.post(f"/api/admin/tags/{codes[0]}/mark-sold")
    assert sell_batch(admin, batch_id) == 4
    assert sell_batch(admin, batch_id) == 0
    assert count(Tag, Tag.stock_status == "SOLD") == 5


# ---------- activation ----------
def test_activation_needs_a_logged_in_owner():
    app, _ = make_app()
    res = client_for(app).post("/api/me/tags/activate", json={"code": "ZZZZZZZZZZ", "otp": "123456", "card": CARD})
    assert res.status_code == 401


def test_a_tag_that_was_not_sold_cannot_be_activated_and_does_not_burn_the_code():
    app, sms = make_app()
    admin = admin_client(app)
    _, codes = generate_batch(admin, 1)
    owner, phone = register_owner(app, sms)

    res = activate(owner, sms, phone, codes[0])
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "TAG_NOT_READY"
    assert one(select(Tag.status).where(Tag.code == codes[0])) == "NOT_ACTIVE"
    # The one-time code was not used up, because the tag was refused first.
    assert count(OtpChallenge, OtpChallenge.consumed_at.is_(None)) == 1


def test_activation_confirms_the_mobile_with_a_code_and_saves_the_contact_card():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 1)
    sell_batch(admin, batch_id)
    owner, phone = register_owner(app, sms)

    res = activate(owner, sms, phone, codes[0].lower())
    assert res.status_code == 201
    tag = res.json()["tag"]
    assert tag["code"] == codes[0]
    assert tag["status"] == "ACTIVE"
    assert set(tag) == {"code", "serial", "status", "activatedAt"}

    me = owner.get("/api/auth/me").json()["user"]
    assert me["phoneVerified"] is True
    assert me["hasCard"] is True
    assert owner.get("/api/me/card").json()["card"]["displayName"] == "Ali Raza"
    assert len(owner.get("/api/me/tags").json()["tags"]) == 1
    assert one(select(AuditLog.action).where(AuditLog.action == "tag.activate")) == "tag.activate"


def test_activation_needs_the_right_one_time_code():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 1)
    sell_batch(admin, batch_id)
    owner, phone = register_owner(app, sms)

    owner.post("/api/me/activation/otp")
    real = sms.last_code(phone)
    wrong = "111111" if real == "000000" else "000000"
    bad = owner.post("/api/me/tags/activate", json={"code": codes[0], "otp": wrong, "card": CARD})
    assert bad.status_code == 400
    assert bad.json()["error"]["code"] == "INVALID_OTP"
    assert one(select(Tag.status).where(Tag.code == codes[0])) == "NOT_ACTIVE"

    good = owner.post("/api/me/tags/activate", json={"code": codes[0], "otp": real, "card": CARD})
    assert good.status_code == 201
    # A code works once.
    assert owner.post("/api/me/tags/activate", json={"code": codes[0], "otp": real, "card": CARD}).status_code in {
        400,
        409,
    }


def test_the_first_activation_must_bring_a_contact_card_and_later_ones_reuse_it():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 2)
    sell_batch(admin, batch_id)
    owner, phone = register_owner(app, sms)

    missing = activate(owner, sms, phone, codes[0], card=None)
    assert missing.status_code == 400
    assert missing.json()["error"]["code"] == "CARD_REQUIRED"

    assert activate(owner, sms, phone, codes[0], card=CARD).status_code == 201
    assert activate(owner, sms, phone, codes[1], card=None).status_code == 201  # same card, two tags
    assert count(ContactCard) == 1


def test_activation_of_a_code_that_does_not_exist_is_404():
    app, sms = make_app()
    owner, phone = register_owner(app, sms)
    assert activate(owner, sms, phone, "ZZZZZZZZZZ").status_code == 404


def test_only_one_of_two_owners_wins_when_they_activate_the_same_tag_at_the_same_moment():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 1)
    sell_batch(admin, batch_id)
    a, phone_a = register_owner(app, sms, "0300 1111111", "Owner A")
    b, phone_b = register_owner(app, sms, "0300 2222222", "Owner B")
    for client in (a, b):
        assert client.post("/api/me/activation/otp").status_code == 200

    def go(client, phone):
        return client.post("/api/me/tags/activate", json={"code": codes[0], "otp": sms.last_code(phone), "card": CARD})

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(go, a, phone_a), pool.submit(go, b, phone_b)]
        statuses = sorted(f.result().status_code for f in futures)
    assert statuses == [201, 409]
    assert count(Tag, Tag.status == "ACTIVE") == 1


def test_activating_a_tag_that_is_already_active_gives_nothing_away():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 1)
    sell_batch(admin, batch_id)
    a, phone_a = register_owner(app, sms, "0300 1111111", "Owner A")
    b, phone_b = register_owner(app, sms, "0300 2222222", "Owner B")
    activate(a, sms, phone_a, codes[0], {"displayName": "Owner A"})

    res = activate(b, sms, phone_b, codes[0], {"displayName": "Owner B"})
    assert res.status_code == 409
    assert "Owner A" not in res.text


def test_one_account_can_hold_at_most_25_tags():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 26)
    sell_batch(admin, batch_id)
    owner, phone = register_owner(app, sms)
    for code in codes[:25]:
        assert activate(owner, sms, phone, code).status_code == 201
    res = activate(owner, sms, phone, codes[25])
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "TAG_LIMIT"
