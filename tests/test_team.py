from sqlalchemy import func, select

from cartag.db import SessionLocal
from cartag.models import AuditLog, Tag, User
from tests.helpers import (
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


def build():
    app, sms = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 4)
    admin.post(f"/api/admin/tags/{codes[0]}/mark-sold")
    owner, phone = register_owner(app, sms, "0300 1234567", "Ali Raza")
    activate(owner, sms, phone, codes[0])
    return app, sms, admin, owner, batch_id, codes


def test_team_lists_filters_and_searches_tags():
    _, _, admin, _, batch_id, codes = build()
    assert admin.get("/api/admin/tags").json()["total"] == 4
    assert admin.get("/api/admin/tags?status=ACTIVE").json()["total"] == 1
    assert admin.get("/api/admin/tags?status=NOT_ACTIVE").json()["total"] == 3
    assert admin.get("/api/admin/tags?stock=SOLD").json()["total"] == 1
    assert admin.get("/api/admin/tags?stock=IN_STOCK").json()["total"] == 3
    assert admin.get(f"/api/admin/tags?batchId={batch_id}").json()["total"] == 4

    for q in ["ali", "1234567", codes[0][:5], "1"]:
        items = admin.get("/api/admin/tags", params={"q": q}).json()["items"]
        assert any(t["code"] == codes[0] for t in items), q
    assert admin.get("/api/admin/tags?q=nomatchhere").json()["total"] == 0

    page = admin.get("/api/admin/tags?pageSize=2&page=2").json()
    assert len(page["items"]) == 2
    assert page["items"][0]["serial"] == "000003"
    assert admin.get("/api/admin/tags?status=BOGUS").status_code == 400
    assert admin.get("/api/admin/tags?stock=BOGUS").status_code == 400


def test_team_sees_a_tag_with_owner_scans_and_history_but_no_secrets():
    app, _, admin, _, _, codes = build()
    client_for(app).get(f"/t/{codes[0]}")
    body = admin.get(f"/api/admin/tags/{codes[0]}").json()
    assert body["tag"]["owner"]["name"] == "Ali Raza"
    assert body["tag"]["owner"]["phone"] == "+923001234567"
    assert body["tag"]["stockStatus"] == "SOLD"
    assert body["scanCount"] == 1
    actions = [h["action"] for h in body["history"]]
    assert "tag.activate" in actions
    assert "tag.mark_sold" in actions
    assert "passwordHash" not in str(body)


def test_retiring_records_who_did_it_and_why():
    _, _, admin, _, _, codes = build()
    res = admin.post(f"/api/admin/tags/{codes[0]}/retire", json={"reason": "Lost in the mail"})
    assert res.status_code == 200
    assert res.json()["tag"]["status"] == "RETIRED"
    entry = one(select(AuditLog).where(AuditLog.action == "tag.retire"))
    assert entry.actor_type == "ADMIN"
    assert entry.meta["reason"] == "Lost in the mail"
    assert entry.meta["from"] == "ACTIVE"


def test_a_retired_tag_cannot_be_sold_again_and_its_code_stays_taken():
    _, _, admin, _, batch_id, codes = build()
    admin.post(f"/api/admin/tags/{codes[2]}/retire", json={})
    assert admin.post(f"/api/admin/tags/{codes[2]}/mark-sold").status_code == 409
    # Marking the whole batch sold skips retired tags.
    assert sell_batch(admin, batch_id) == 2
    assert one(select(Tag.stock_status).where(Tag.code == codes[2])) == "IN_STOCK"
    # The retired code still exists, so it can never be handed to anybody else.
    assert admin.post("/api/admin/batches/import", json={"name": "Reuse", "csv": codes[2]}).status_code == 409


def test_blocking_an_owner_logs_them_out_and_hides_their_tags_and_unblocking_restores_access():
    app, _, admin, owner, _, codes = build()
    user_id = str(one(select(User.id)))
    assert admin.post(f"/api/admin/users/{user_id}/block").status_code == 200
    assert owner.get("/api/me/tags").status_code == 401
    assert "Ali Raza" not in client_for(app).get(f"/t/{codes[0]}").text

    admin.post(f"/api/admin/users/{user_id}/unblock")
    assert (
        client_for(app).post("/api/auth/login", json={"phone": "0300 1234567", "password": PASSWORD}).status_code == 200
    )


def test_team_lists_users_stats_and_activity():
    app, _, admin, _, _, codes = build()
    users = admin.get("/api/admin/users?q=ali").json()
    assert users["items"][0]["name"] == "Ali Raza"
    assert users["items"][0]["tagCount"] == 1
    assert users["items"][0]["phoneVerified"] is True
    assert "passwordHash" not in str(users)

    stats = admin.get("/api/admin/stats").json()
    assert stats["tags"] == {"total": 4, "notActive": 3, "active": 1, "turnedOff": 0, "retired": 0}
    assert stats["stock"]["SOLD"] == 1
    assert stats["stock"]["IN_STOCK"] == 3
    assert stats["users"] == 1
    assert stats["pendingDeletions"] == 0

    assert len(admin.get("/api/admin/activity").json()["items"]) > 0
    client_for(app).get(f"/t/{codes[0]}")
    scans = admin.get("/api/admin/activity?type=scans").json()["items"]
    assert len(scans) == 1
    assert scans[0]["code"] == codes[0]
