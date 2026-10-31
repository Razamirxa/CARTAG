import re
from typing import Any

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from cartag.db import get_db
from cartag.deps import require_admin
from cartag.domain import OrderStatus, PaymentMethod, PaymentStatus
from cartag.models import Admin, AuditLog, Order, User
from cartag.schemas import DeliveryUpdateIn, OrderStatusIn, UpdateProductIn
from cartag.services import shop as shop_service

router = APIRouter(prefix="/admin", tags=["admin-shop"], dependencies=[Depends(require_admin)])


# ---------- products ----------
@router.get("/products")
def products(db: Session = Depends(get_db)):
    return {"products": [shop_service.product_view(p) for p in shop_service.list_products(db, active_only=False)]}


@router.patch("/products/{sku}")
def patch_product(
    body: UpdateProductIn,
    sku: str = Path(..., max_length=40),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {"product": shop_service.product_view(shop_service.update_product(db, admin.id, sku, body))}


# ---------- orders ----------
def admin_order_view(order: Order) -> dict[str, Any]:
    view = shop_service.order_view(order)
    view["customer"] = {"id": str(order.user.id), "name": order.user.name, "phone": order.user.phone}
    view["payments"] = [
        {
            "id": str(p.id),
            "provider": p.provider,
            "status": p.status.value,
            "amount": p.amount,
            "reference": p.reference,
            "createdAt": p.created_at,
            "confirmedAt": p.confirmed_at,
        }
        for p in order.payments
    ]
    return view


@router.get("/orders")
def orders(
    status: OrderStatus | None = None,
    payment: PaymentStatus | None = None,
    method: PaymentMethod | None = None,
    q: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Order).join(User, Order.user_id == User.id)
    count_stmt = select(func.count()).select_from(Order).join(User, Order.user_id == User.id)
    conditions = []
    if status:
        conditions.append(Order.status == status)
    if payment:
        conditions.append(Order.payment_status == payment)
    if method:
        conditions.append(Order.payment_method == method)
    if q and q.strip():
        term = q.strip()
        digits = re.sub(r"\D", "", term)
        options = [
            Order.recipient_name.icontains(term, autoescape=True),
            User.name.icontains(term, autoescape=True),
            Order.tracking_number.icontains(term, autoescape=True),
        ]
        if digits:
            options.append(Order.recipient_phone.contains(digits, autoescape=True))
            options.append(User.phone.contains(digits, autoescape=True))
            if len(digits) <= 9:
                options.append(Order.number == int(digits))
        conditions.append(or_(*options))
    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.options(joinedload(Order.user))
        .order_by(Order.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = []
    for order in rows:
        view = shop_service.order_view(order, with_items=False)
        view["customer"] = {"name": order.user.name, "phone": order.user.phone}
        items.append(view)
    return {"total": total, "page": page, "pageSize": page_size, "items": items}


@router.get("/orders/{number}")
def order_detail(number: int, db: Session = Depends(get_db)):
    order = shop_service.get_order(db, number)
    history = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "Order", AuditLog.entity_id == str(order.id))
        .order_by(AuditLog.at.desc())
        .limit(40)
    ).all()
    return {
        "order": admin_order_view(order),
        "history": [
            {"id": str(h.id), "at": h.at, "actorType": h.actor_type.value, "action": h.action, "meta": h.meta}
            for h in history
        ],
    }


@router.post("/orders/{number}/status")
def order_status(
    number: int, body: OrderStatusIn, admin: Admin = Depends(require_admin), db: Session = Depends(get_db)
):
    return {"order": admin_order_view(shop_service.set_order_status(db, admin.id, number, body.status))}


@router.patch("/orders/{number}/delivery")
def order_delivery(
    number: int, body: DeliveryUpdateIn, admin: Admin = Depends(require_admin), db: Session = Depends(get_db)
):
    return {"order": admin_order_view(shop_service.update_delivery(db, admin.id, number, body))}


@router.post("/orders/{number}/payment/collected")
def order_cod_collected(number: int, admin: Admin = Depends(require_admin), db: Session = Depends(get_db)):
    return {"order": admin_order_view(shop_service.mark_cod_collected(db, admin.id, number))}


@router.post("/orders/{number}/payment/refunded")
def order_refunded(number: int, admin: Admin = Depends(require_admin), db: Session = Depends(get_db)):
    return {"order": admin_order_view(shop_service.mark_refunded(db, admin.id, number))}
