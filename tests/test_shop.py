import json

import pytest
from sqlalchemy import func, select

from cartag.db import SessionLocal
from cartag.main import create_app
from cartag.models import AuditLog, Order, OrderItem, Payment, Product
from tests.helpers import admin_client, client_for, make_app, register_owner

ADDRESS = {
    "recipientName": "Ali Raza",
    "recipientPhone": "0300 1234567",
    "address": "House 12, Street 4, Model Town",
    "city": "Lahore",
}


def one(statement):
    with SessionLocal() as db:
        return db.scalar(statement)


def count(model, *where) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0


def place(client, items=(("COMPACT-BLACK", 2),), method="COD", **overrides):
    body = {
        "items": [{"sku": sku, "quantity": quantity} for sku, quantity in items],
        "paymentMethod": method,
        **ADDRESS,
        **overrides,
    }
    return client.post("/api/shop/orders", json=body)


@pytest.fixture
def shop():
    app, sms = make_app()
    owner, _ = register_owner(app, sms)
    return app, sms, owner, admin_client(app)


# ---------- catalogue ----------
def test_the_shop_has_twelve_products_with_placeholder_prices_and_a_premium_flag(shop):
    app, _, _, _ = shop
    products = client_for(app).get("/api/shop/products").json()["products"]
    assert len(products) == 12
    by_sku = {p["sku"]: p for p in products}
    assert by_sku["COMPACT-BLACK"]["price"] == 800
    assert by_sku["STANDARD-IVORY"]["price"] == 900
    assert by_sku["LARGE-GLACIER"]["price"] == 1100
    assert by_sku["COMPACT-BURGUNDY"]["premium"] is True
    assert by_sku["COMPACT-BLACK"]["premium"] is False
    assert {p["size"] for p in products} == {"COMPACT", "STANDARD", "LARGE"}
    assert {p["colour"] for p in products} == {"BLACK", "IVORY", "BURGUNDY", "GLACIER"}


def test_checkout_config_says_whether_online_payment_is_on_and_what_delivery_costs(shop):
    app, _, _, _ = shop
    assert client_for(app).get("/api/shop/config").json() == {"paymentEnabled": True, "shippingFee": 200}
    app_off = create_app(payment_provider="none", enable_ip_rate_limits=False)
    assert client_for(app_off).get("/api/shop/config").json()["paymentEnabled"] is False


# ---------- placing an order ----------
def test_ordering_needs_a_login(shop):
    app, _, _, _ = shop
    assert place(client_for(app)).status_code == 401


def test_a_cash_on_delivery_order_is_priced_from_the_database_and_recorded(shop):
    _, _, owner, _ = shop
    res = place(owner, items=(("COMPACT-BLACK", 2), ("LARGE-BURGUNDY", 1)), notes="Call before arriving")
    assert res.status_code == 201
    body = res.json()
    order = body["order"]
    assert body["checkoutUrl"] is None
    assert order["label"] == f"CT-{order['number']:06d}"
    assert order["status"] == "PLACED"
    assert order["paymentMethod"] == "COD"
    assert order["paymentStatus"] == "COD_PENDING"
    assert order["subtotal"] == 2 * 800 + 1100
    assert order["shippingFee"] == 200
    assert order["total"] == 2 * 800 + 1100 + 200
    assert order["recipient"] == {
        "name": "Ali Raza",
        "phone": "+923001234567",
        "address": "House 12, Street 4, Model Town",
        "city": "Lahore",
        "notes": "Call before arriving",
    }
    assert [i["sku"] for i in order["items"]] == ["COMPACT-BLACK", "LARGE-BURGUNDY"]
    assert order["items"][0]["lineTotal"] == 1600
    assert one(select(AuditLog.action).where(AuditLog.action == "order.place")) == "order.place"


def test_a_price_sent_by_the_browser_is_ignored(shop):
    _, _, owner, _ = shop
    body = {
        "items": [{"sku": "COMPACT-BLACK", "quantity": 1, "price": 1, "unitPrice": 1}],
        "paymentMethod": "COD",
        "total": 1,
        **ADDRESS,
    }
    order = owner.post("/api/shop/orders", json=body).json()["order"]
    assert order["subtotal"] == 800
    assert order["total"] == 1000


@pytest.mark.parametrize(
    "overrides",
    [
        {"items": []},
        {"items": [{"sku": "COMPACT-BLACK", "quantity": 0}]},
        {"items": [{"sku": "COMPACT-BLACK", "quantity": 21}]},
        {"items": [{"sku": "COMPACT-BLACK", "quantity": 1.5}]},
        {"items": [{"sku": "COMPACT-BLACK", "quantity": 1}, {"sku": "compact-black", "quantity": 2}]},
        {"recipientPhone": "123"},
        {"recipientName": ""},
        {"address": "Home"},
        {"city": ""},
        {"paymentMethod": "BARTER"},
    ],
)
def test_order_validation(shop, overrides):
    _, _, owner, _ = shop
    body = {"items": [{"sku": "COMPACT-BLACK", "quantity": 1}], "paymentMethod": "COD", **ADDRESS, **overrides}
    assert owner.post("/api/shop/orders", json=body).status_code == 400
    assert count(Order) == 0


def test_unknown_and_switched_off_products_cannot_be_ordered(shop):
    app, _, owner, admin = shop
    res = place(owner, items=(("NOPE-NOPE", 1),))
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "PRODUCT_UNAVAILABLE"
    assert res.json()["error"]["details"]["skus"] == ["NOPE-NOPE"]

    admin.patch("/api/admin/products/COMPACT-BLACK", json={"active": False})
    assert place(owner, items=(("COMPACT-BLACK", 1),)).status_code == 400
    assert "COMPACT-BLACK" not in [p["sku"] for p in client_for(app).get("/api/shop/products").json()["products"]]
    assert count(Order) == 0


def test_a_price_change_never_rewrites_an_old_order(shop):
    _, _, owner, admin = shop
    old = place(owner, items=(("COMPACT-BLACK", 1),)).json()["order"]
    assert admin.patch("/api/admin/products/COMPACT-BLACK", json={"price": 950}).status_code == 200

    again = owner.get(f"/api/shop/orders/{old['number']}").json()["order"]
    assert again["items"][0]["unitPrice"] == 800
    assert again["total"] == old["total"]
    new = place(owner, items=(("COMPACT-BLACK", 1),)).json()["order"]
    assert new["items"][0]["unitPrice"] == 950


def test_online_payment_is_refused_while_it_is_switched_off():
    app = create_app(payment_provider="none", enable_ip_rate_limits=False)
    owner, _ = register_owner(app, None)
    res = place(owner, method="PREPAID")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "PAYMENT_UNAVAILABLE"
    assert place(owner, method="COD").status_code == 201


def test_there_is_a_daily_order_limit(shop):
    _, _, owner, _ = shop
    for _ in range(10):
        assert place(owner).status_code == 201
    res = place(owner)
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "ORDER_LIMIT"


# ---------- a customer's own orders ----------
def test_customers_see_only_their_own_orders(shop):
    app, sms, owner, _ = shop
    mine = place(owner).json()["order"]
    other, _ = register_owner(app, sms, "0345 7654321", "Sara Khan")

    assert [o["number"] for o in owner.get("/api/shop/orders").json()["orders"]] == [mine["number"]]
    assert other.get("/api/shop/orders").json()["orders"] == []
    assert other.get(f"/api/shop/orders/{mine['number']}").status_code == 404
    assert other.post(f"/api/shop/orders/{mine['number']}/cancel").status_code == 404
    assert client_for(app).get("/api/shop/orders").status_code == 401


def test_a_customer_can_cancel_an_order_until_the_team_starts_preparing_it(shop):
    _, _, owner, admin = shop
    first = place(owner).json()["order"]
    res = owner.post(f"/api/shop/orders/{first['number']}/cancel")
    assert res.status_code == 200
    assert res.json()["order"]["status"] == "CANCELLED"
    assert res.json()["order"]["paymentStatus"] == "CANCELLED"
    assert owner.post(f"/api/shop/orders/{first['number']}/cancel").status_code == 409

    second = place(owner).json()["order"]
    admin.post(f"/api/admin/orders/{second['number']}/status", json={"status": "PROCESSING"})
    assert owner.post(f"/api/shop/orders/{second['number']}/cancel").status_code == 409


# ---------- online payment ----------
def test_a_prepaid_order_is_paid_only_when_the_provider_confirms(shop):
    app, _, owner, _ = shop
    res = place(owner, method="PREPAID")
    assert res.status_code == 201
    order = res.json()["order"]
    assert order["paymentStatus"] == "DUE"
    url = res.json()["checkoutUrl"]
    payment_id = url.rsplit("/", 1)[1]
    assert url == f"http://localhost:5173/pay/mock/{payment_id}"

    # Nothing the browser can ask for marks it paid. Only the provider's confirmation does.
    assert owner.get(f"/api/shop/orders/{order['number']}").json()["order"]["paymentStatus"] == "DUE"
    info = owner.get(f"/api/payments/mock/{payment_id}").json()
    assert info == {"orderNumber": order["number"], "amount": order["total"], "status": "INITIATED"}

    assert owner.post(f"/api/payments/mock/{payment_id}/complete", json={"outcome": "success"}).status_code == 200
    paid = owner.get(f"/api/shop/orders/{order['number']}").json()["order"]
    assert paid["paymentStatus"] == "PAID"
    assert paid["paidAt"] is not None
    assert one(select(Payment.reference)).startswith("MOCK-")
    assert one(select(AuditLog.actor_type).where(AuditLog.action == "payment.paid")) == "SYSTEM"


def test_a_confirmation_that_arrives_twice_changes_nothing(shop):
    _, _, owner, _ = shop
    payment_id = place(owner, method="PREPAID").json()["checkoutUrl"].rsplit("/", 1)[1]
    for _ in range(3):
        assert owner.post(f"/api/payments/mock/{payment_id}/complete", json={"outcome": "success"}).status_code == 200
    assert count(Payment, Payment.status == "SUCCEEDED") == 1
    assert count(AuditLog, AuditLog.action == "payment.paid") == 1


def test_a_failed_payment_can_be_tried_again(shop):
    _, _, owner, _ = shop
    first = place(owner, method="PREPAID").json()
    number = first["order"]["number"]
    payment_id = first["checkoutUrl"].rsplit("/", 1)[1]
    owner.post(f"/api/payments/mock/{payment_id}/complete", json={"outcome": "failure"})
    assert owner.get(f"/api/shop/orders/{number}").json()["order"]["paymentStatus"] == "FAILED"

    retry = owner.post(f"/api/shop/orders/{number}/pay")
    assert retry.status_code == 200
    second_id = retry.json()["checkoutUrl"].rsplit("/", 1)[1]
    assert second_id != payment_id
    owner.post(f"/api/payments/mock/{second_id}/complete", json={"outcome": "success"})
    assert owner.get(f"/api/shop/orders/{number}").json()["order"]["paymentStatus"] == "PAID"
    assert count(Payment) == 2

    # Once paid, there is nothing more to pay and the customer cannot cancel it themselves.
    assert owner.post(f"/api/shop/orders/{number}/pay").status_code == 409
    assert owner.post(f"/api/shop/orders/{number}/cancel").status_code == 409


def test_the_webhook_checks_the_signature_and_the_amount(shop):
    app, _, owner, _ = shop
    data = place(owner, method="PREPAID").json()
    payment_id = data["checkoutUrl"].rsplit("/", 1)[1]
    provider = app.state.payment_provider
    client = client_for(app)

    with SessionLocal() as db:
        payment = db.scalar(select(Payment))
        message, headers = provider.build_message(payment, succeeded=True)

    forged = client.post(
        "/api/payments/webhook/mock", content=message, headers={**headers, "x-cartag-mock-signature": "0" * 64}
    )
    assert forged.status_code == 400
    assert forged.json()["error"]["code"] == "BAD_SIGNATURE"
    assert client.post("/api/payments/webhook/mock", content=message).status_code == 400
    assert client.post("/api/payments/webhook/other", content=message, headers=headers).status_code == 404
    assert owner.get(f"/api/shop/orders/{data['order']['number']}").json()["order"]["paymentStatus"] == "DUE"

    # A genuine message for the wrong amount is not accepted as payment.
    wrong = json.dumps({"paymentId": payment_id, "status": "succeeded", "amount": 1, "reference": "X"}).encode()
    bad_amount = client.post(
        "/api/payments/webhook/mock", content=wrong, headers={"x-cartag-mock-signature": provider.sign(wrong)}
    )
    assert bad_amount.status_code == 200
    assert owner.get(f"/api/shop/orders/{data['order']['number']}").json()["order"]["paymentStatus"] == "FAILED"
    assert count(AuditLog, AuditLog.action == "payment.amount_mismatch") == 1

    # The real one, signed correctly, for the right amount.
    data2 = place(owner, method="PREPAID").json()
    with SessionLocal() as db:
        payment2 = db.scalar(select(Payment).where(Payment.status == "INITIATED"))
        message2, headers2 = provider.build_message(payment2, succeeded=True)
    assert client.post("/api/payments/webhook/mock", content=message2, headers=headers2).status_code == 200
    assert owner.get(f"/api/shop/orders/{data2['order']['number']}").json()["order"]["paymentStatus"] == "PAID"


def test_the_pretend_checkout_belongs_to_the_customer_who_ordered(shop):
    app, sms, owner, _ = shop
    payment_id = place(owner, method="PREPAID").json()["checkoutUrl"].rsplit("/", 1)[1]
    other, _ = register_owner(app, sms, "0345 7654321", "Sara Khan")
    assert other.get(f"/api/payments/mock/{payment_id}").status_code == 404
    assert other.post(f"/api/payments/mock/{payment_id}/complete", json={"outcome": "success"}).status_code == 404
    assert client_for(app).get(f"/api/payments/mock/{payment_id}").status_code == 401


def test_money_that_arrives_after_a_cancellation_is_kept_visible_for_a_refund(shop):
    _, _, owner, admin = shop
    data = place(owner, method="PREPAID").json()
    number = data["order"]["number"]
    payment_id = data["checkoutUrl"].rsplit("/", 1)[1]

    assert owner.post(f"/api/shop/orders/{number}/cancel").json()["order"]["status"] == "CANCELLED"
    owner.post(f"/api/payments/mock/{payment_id}/complete", json={"outcome": "success"})

    order = admin.get(f"/api/admin/orders/{number}").json()["order"]
    assert order["status"] == "CANCELLED"
    assert order["paymentStatus"] == "PAID"
    assert count(AuditLog, AuditLog.action == "payment.paid_after_cancel") == 1

    refunded = admin.post(f"/api/admin/orders/{number}/payment/refunded")
    assert refunded.json()["order"]["paymentStatus"] == "REFUNDED"
    assert admin.post(f"/api/admin/orders/{number}/payment/refunded").status_code == 409


# ---------- the team ----------
def test_team_routes_for_the_shop_are_closed_to_customers(shop):
    app, _, owner, _ = shop
    number = place(owner).json()["order"]["number"]
    for client in (owner, client_for(app)):
        assert client.get("/api/admin/orders").status_code == 401
        assert client.get(f"/api/admin/orders/{number}").status_code == 401
        assert client.get("/api/admin/products").status_code == 401
        assert client.patch("/api/admin/products/COMPACT-BLACK", json={"price": 1}).status_code == 401
        assert client.post(f"/api/admin/orders/{number}/status", json={"status": "SHIPPED"}).status_code == 401


def test_team_lists_filters_and_searches_orders(shop):
    app, sms, owner, admin = shop
    other, _ = register_owner(app, sms, "0345 7654321", "Sara Khan")
    a = place(owner).json()["order"]
    b = place(other, method="PREPAID", recipientName="Sara Khan", recipientPhone="0345 7654321").json()["order"]

    assert admin.get("/api/admin/orders").json()["total"] == 2
    assert admin.get("/api/admin/orders?method=PREPAID").json()["items"][0]["number"] == b["number"]
    assert admin.get("/api/admin/orders?payment=COD_PENDING").json()["items"][0]["number"] == a["number"]
    assert admin.get("/api/admin/orders?status=SHIPPED").json()["total"] == 0
    for q in ["sara", "7654321", str(b["number"]), "ali"]:
        assert admin.get("/api/admin/orders", params={"q": q}).json()["total"] >= 1, q
    assert admin.get("/api/admin/orders?q=nomatchhere").json()["total"] == 0
    assert admin.get("/api/admin/orders?status=BOGUS").status_code == 400

    detail = admin.get(f"/api/admin/orders/{a['number']}").json()
    assert detail["order"]["customer"]["name"] == "Ali Raza"
    assert detail["order"]["items"][0]["sku"] == "COMPACT-BLACK"
    assert "order.place" in [h["action"] for h in detail["history"]]
    assert admin.get("/api/admin/orders/999999").status_code == 404


def test_the_team_moves_an_order_through_its_steps_and_cannot_skip_or_go_back(shop):
    _, _, owner, admin = shop
    number = place(owner).json()["order"]["number"]
    url = f"/api/admin/orders/{number}/status"

    assert admin.post(url, json={"status": "SHIPPED"}).status_code == 409  # cannot skip packing
    assert admin.post(url, json={"status": "PROCESSING"}).json()["order"]["status"] == "PROCESSING"
    shipped = admin.post(url, json={"status": "SHIPPED"}).json()["order"]
    assert shipped["status"] == "SHIPPED"
    assert shipped["shippedAt"] is not None
    assert admin.post(url, json={"status": "PROCESSING"}).status_code == 409  # cannot go back
    assert admin.post(url, json={"status": "CANCELLED"}).status_code == 409  # already on its way
    delivered = admin.post(url, json={"status": "DELIVERED"}).json()["order"]
    assert delivered["deliveredAt"] is not None
    assert delivered["delivery"]["status"] == "DELIVERED"
    assert admin.post(url, json={"status": "BOGUS"}).status_code == 400


def test_the_team_records_the_courier_and_tracking_number_and_the_customer_sees_them(shop):
    _, _, owner, admin = shop
    number = place(owner).json()["order"]["number"]
    admin.post(f"/api/admin/orders/{number}/status", json={"status": "PROCESSING"})
    admin.post(f"/api/admin/orders/{number}/status", json={"status": "SHIPPED"})

    res = admin.patch(
        f"/api/admin/orders/{number}/delivery",
        json={"courier": "TCS", "trackingNumber": "TCS123456", "deliveryStatus": "IN_TRANSIT"},
    )
    assert res.status_code == 200
    seen = owner.get(f"/api/shop/orders/{number}").json()["order"]["delivery"]
    assert seen == {"courier": "TCS", "trackingNumber": "TCS123456", "status": "IN_TRANSIT"}

    # A courier marking it delivered also closes the order.
    done = admin.patch(f"/api/admin/orders/{number}/delivery", json={"deliveryStatus": "DELIVERED"}).json()["order"]
    assert done["status"] == "DELIVERED"
    assert admin.patch(f"/api/admin/orders/{number}/delivery", json={}).status_code == 400


def test_cash_collected_by_the_courier_is_recorded_only_after_shipping(shop):
    _, _, owner, admin = shop
    number = place(owner).json()["order"]["number"]
    collected = f"/api/admin/orders/{number}/payment/collected"
    assert admin.post(collected).status_code == 409  # not shipped yet

    admin.post(f"/api/admin/orders/{number}/status", json={"status": "PROCESSING"})
    admin.post(f"/api/admin/orders/{number}/status", json={"status": "SHIPPED"})
    res = admin.post(collected)
    assert res.status_code == 200
    assert res.json()["order"]["paymentStatus"] == "COD_COLLECTED"
    assert res.json()["order"]["paidAt"] is not None
    assert admin.post(collected).status_code == 409
    assert admin.post(f"/api/admin/orders/{number}/payment/refunded").json()["order"]["paymentStatus"] == "REFUNDED"


def test_cancelling_an_unpaid_order_cancels_its_payment_but_a_paid_one_stays_paid_until_refunded(shop):
    _, _, owner, admin = shop
    unpaid = place(owner).json()["order"]["number"]
    cancelled = admin.post(f"/api/admin/orders/{unpaid}/status", json={"status": "CANCELLED"}).json()["order"]
    assert cancelled["paymentStatus"] == "CANCELLED"
    assert cancelled["cancelledAt"] is not None

    prepaid = place(owner, method="PREPAID").json()
    payment_id = prepaid["checkoutUrl"].rsplit("/", 1)[1]
    owner.post(f"/api/payments/mock/{payment_id}/complete", json={"outcome": "success"})
    number = prepaid["order"]["number"]
    result = admin.post(f"/api/admin/orders/{number}/status", json={"status": "CANCELLED"}).json()["order"]
    assert result["status"] == "CANCELLED"
    assert result["paymentStatus"] == "PAID"
    assert admin.post(f"/api/admin/orders/{number}/payment/refunded").json()["order"]["paymentStatus"] == "REFUNDED"


def test_the_team_edits_prices_and_availability_and_every_change_is_recorded(shop):
    _, _, _, admin = shop
    assert len(admin.get("/api/admin/products").json()["products"]) == 12
    res = admin.patch("/api/admin/products/standard-ivory", json={"price": 1234, "description": "Matte finish"})
    assert res.status_code == 200
    assert res.json()["product"]["price"] == 1234
    assert res.json()["product"]["description"] == "Matte finish"
    entry = one(select(AuditLog).where(AuditLog.action == "product.update"))
    assert entry.meta["from"]["price"] == 900
    assert entry.meta["to"]["price"] == 1234

    for bad in ({}, {"price": -1}, {"price": 2_000_000}, {"price": 1.5}, {"active": "no"}):
        assert admin.patch("/api/admin/products/STANDARD-IVORY", json=bad).status_code == 400
    assert admin.patch("/api/admin/products/NOPE-NOPE", json={"price": 1}).status_code == 404
    assert one(select(Product.price).where(Product.sku == "STANDARD-IVORY")) == 1234
    assert count(OrderItem) == 0
