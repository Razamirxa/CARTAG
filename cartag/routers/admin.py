import json
import math
import re
import uuid
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response, StreamingResponse
from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from cartag.config import Settings
from cartag.db import SessionLocal, get_db
from cartag.deps import require_admin, settings_dep, tag_code_param
from cartag.domain import DeletionStatus, StockStatus, TagStatus, UserStatus, format_serial
from cartag.errors import AppError, bad_request, not_found
from cartag.models import AccountDeletionRequest, Admin, AuditLog, ScanEvent, Tag, TagBatch, User
from cartag.qr import (
    QrMatrix,
    csv_cell,
    describe_print,
    matrix_for_tag,
    render_eps,
    render_pdf,
    render_svg,
    tag_url,
)
from cartag.qr.tag_art import DESIGNS, describe_tag, render_tag_eps, render_tag_pdf, render_tag_svg
from cartag.schemas import DecisionIn, GenerateBatchIn, ImportBatchIn, RetireTagIn
from cartag.services import account as account_service
from cartag.services import tags as tag_service
from cartag.services.audit import Actor, audit
from cartag.services.batches import batch_view, generate_batch, import_batch, list_batches
from cartag.services.sessions import revoke_user_sessions

DesignKey = Literal["ivory", "glacier", "burgundy", "black"]

MAX_ZIP_TAGS = 20_000
PDF_PAGES_PER_FILE = 5000
IMPORT_BODY_LIMIT = 6_000_000

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


# ---------- helpers ----------
def admin_tag_view(tag: Tag) -> dict[str, Any]:
    owner = tag.owner
    return {
        "code": tag.code,
        "serial": format_serial(tag.serial),
        "status": tag.status.value,
        "stockStatus": tag.stock_status.value,
        "batch": {"id": str(tag.batch.id), "name": tag.batch.name},
        "owner": {"id": str(owner.id), "name": owner.name, "phone": owner.phone} if owner else None,
        "activatedAt": tag.activated_at,
        "retiredAt": tag.retired_at,
        "createdAt": tag.created_at,
    }


def _load_tag(db: Session, code: str) -> Tag:
    tag = db.scalar(
        select(Tag)
        .where(Tag.code == code)
        .options(joinedload(Tag.owner), joinedload(Tag.batch))
        .execution_options(populate_existing=True)
    )
    if tag is None:
        raise not_found("Tag not found", "TAG_NOT_FOUND")
    return tag


def _file_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40]
    return slug or "batch"


# ---------- overview ----------
@router.get("/stats")
def stats(db: Session = Depends(get_db)):
    now = datetime.now(UTC)
    day_ago, week_ago = now - timedelta(hours=24), now - timedelta(days=7)
    by_status = dict(db.execute(select(Tag.status, func.count()).group_by(Tag.status)).all())
    by_stock = dict(db.execute(select(Tag.stock_status, func.count()).group_by(Tag.stock_status)).all())

    def scalar(stmt):
        return db.scalar(stmt) or 0

    return {
        "tags": {
            "total": sum(by_status.values()),
            "notActive": by_status.get(TagStatus.NOT_ACTIVE, 0),
            "active": by_status.get(TagStatus.ACTIVE, 0),
            "turnedOff": by_status.get(TagStatus.TURNED_OFF, 0),
            "retired": by_status.get(TagStatus.RETIRED, 0),
        },
        "stock": {s.value: by_stock.get(s, 0) for s in StockStatus},
        "users": scalar(select(func.count()).select_from(User).where(User.status != UserStatus.DELETED)),
        "newUsers7d": scalar(select(func.count()).select_from(User).where(User.created_at >= week_ago)),
        "batches": scalar(select(func.count()).select_from(TagBatch)),
        "scans24h": scalar(select(func.count()).select_from(ScanEvent).where(ScanEvent.at >= day_ago)),
        "scans7d": scalar(select(func.count()).select_from(ScanEvent).where(ScanEvent.at >= week_ago)),
        "pendingDeletions": scalar(
            select(func.count())
            .select_from(AccountDeletionRequest)
            .where(AccountDeletionRequest.status == DeletionStatus.PENDING)
        ),
    }


@router.get("/activity")
def activity(
    type: Literal["audit", "scans"] = "audit",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    if type == "scans":
        total = db.scalar(select(func.count()).select_from(ScanEvent)) or 0
        rows = db.scalars(
            select(ScanEvent)
            .options(joinedload(ScanEvent.tag))
            .order_by(ScanEvent.at.desc(), ScanEvent.id.desc())
            .offset(offset)
            .limit(page_size)
        ).all()
        items = [
            {
                "id": str(r.id),
                "at": r.at,
                "outcome": r.outcome.value,
                "code": r.tag.code if r.tag else r.code_attempted,
            }
            for r in rows
        ]
    else:
        total = db.scalar(select(func.count()).select_from(AuditLog)) or 0
        rows = db.scalars(
            select(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id.desc()).offset(offset).limit(page_size)
        ).all()
        items = [
            {
                "id": str(r.id),
                "at": r.at,
                "actorType": r.actor_type.value,
                "actorId": r.actor_id,
                "action": r.action,
                "entityType": r.entity_type,
                "entityId": r.entity_id,
                "meta": r.meta,
            }
            for r in rows
        ]
    return {"total": total, "page": page, "pageSize": page_size, "items": items}


# ---------- batches ----------
@router.get("/batches")
def batches(db: Session = Depends(get_db)):
    return {"batches": list_batches(db)}


@router.post("/batches/generate", status_code=201)
def batches_generate(
    body: GenerateBatchIn,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    batch = generate_batch(db, admin.id, body.name, body.quantity, settings.public_base_url)
    return {"batch": batch_view(batch)}


async def _read_limited_json(request: Request, limit: int) -> Any:
    """Reads a JSON body up to `limit` bytes. Called only after the caller proved to be an admin."""
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        raise AppError(413, "PAYLOAD_TOO_LARGE", "Request is too large")
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise AppError(413, "PAYLOAD_TOO_LARGE", "Request is too large")
        chunks.append(chunk)
    try:
        return json.loads(b"".join(chunks))
    except ValueError:
        raise AppError(400, "BAD_JSON", "Request body is not valid JSON") from None


@router.post("/batches/import", status_code=201)
async def batches_import(
    request: Request,
    admin: Admin = Depends(require_admin),
    settings: Settings = Depends(settings_dep),
):
    # The big body is read here, after require_admin ran, so only a logged-in admin can send it.
    raw = await _read_limited_json(request, IMPORT_BODY_LIMIT)
    try:
        body = ImportBatchIn.model_validate(raw)
    except ValidationError as error:
        issues = [
            {"field": ".".join(str(p) for p in e["loc"]), "message": str(e["msg"]).removeprefix("Value error, ")}
            for e in error.errors()
        ]
        raise bad_request(issues[0]["message"], "VALIDATION_ERROR", issues) from None

    def work():
        with SessionLocal() as db:
            batch = import_batch(db, admin.id, body.name, body.csv, settings.public_base_url)
            return batch_view(batch)

    return {"batch": await run_in_threadpool(work)}


def _describe(batch: TagBatch, code: str, size_mm: float, design: DesignKey | None) -> dict[str, Any]:
    """Print facts for a sample tag. With a design the size is the whole tag, otherwise the QR file."""
    matrix = matrix_for_tag(batch.base_url, code)
    if design:
        return describe_tag(matrix, size_mm, DESIGNS[design])
    return describe_print(matrix, size_mm)


@router.get("/batches/{batch_id}")
def batch_detail(
    batch_id: uuid.UUID,
    size_mm: float | None = Query(None, alias="sizeMm", ge=10, le=200),
    design: DesignKey | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    batch = db.get(TagBatch, batch_id)
    if batch is None:
        raise not_found("Batch not found", "BATCH_NOT_FOUND")

    first_code = db.scalar(select(Tag.code).where(Tag.batch_id == batch_id).order_by(Tag.serial).limit(1))
    by_status = {
        status.value: count
        for status, count in db.execute(
            select(Tag.status, func.count()).where(Tag.batch_id == batch_id).group_by(Tag.status)
        )
    }
    by_stock = {
        status.value: count
        for status, count in db.execute(
            select(Tag.stock_status, func.count()).where(Tag.batch_id == batch_id).group_by(Tag.stock_status)
        )
    }
    return {
        "batch": batch_view(batch),
        "byStatus": by_status,
        "byStock": by_stock,
        "print": _describe(batch, first_code, size_mm or settings.qr_physical_size_mm, design) if first_code else None,
        "sampleUrl": tag_url(batch.base_url, first_code) if first_code else None,
        "pdfParts": max(1, math.ceil(batch.quantity / PDF_PAGES_PER_FILE)),
    }


@router.post("/batches/{batch_id}/mark-sold")
def batch_mark_sold(batch_id: uuid.UUID, admin: Admin = Depends(require_admin), db: Session = Depends(get_db)):
    """Marks every tag of the batch that is still in stock as sold (for example a batch handed to a seller)."""
    if db.get(TagBatch, batch_id) is None:
        raise not_found("Batch not found", "BATCH_NOT_FOUND")
    return {"changed": tag_service.mark_batch_sold(db, admin.id, batch_id)}


def _iter_batch_tags(batch_id: uuid.UUID, chunk: int = 1000) -> Iterator[tuple[int, str]]:
    """Walks a batch in serial order with its own session, so a long download never holds a request's session."""
    with SessionLocal() as session:
        last = 0
        while True:
            rows = session.execute(
                select(Tag.serial, Tag.code)
                .where(Tag.batch_id == batch_id, Tag.serial > last)
                .order_by(Tag.serial)
                .limit(chunk)
            ).all()
            if not rows:
                return
            yield from ((r.serial, r.code) for r in rows)
            last = rows[-1].serial


class _ChunkWriter:
    """A write-only file that hands back what was written, so a ZIP can be streamed instead of built in memory."""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []
        self._position = 0

    def write(self, data: bytes) -> int:
        self._chunks.append(bytes(data))
        self._position += len(data)
        return len(data)

    def tell(self) -> int:
        return self._position

    def flush(self) -> None:
        pass

    def drain(self) -> Iterator[bytes]:
        chunks, self._chunks = self._chunks, []
        yield from chunks


def _render_one(matrix: QrMatrix, format: str, mm: float, design: DesignKey | None, code: str) -> str:
    if design:
        art = DESIGNS[design]
        return render_tag_svg(matrix, art, mm) if format == "svg" else render_tag_eps(matrix, art, mm, f"Tag {code}")
    return render_svg(matrix, mm) if format == "svg" else render_eps(matrix, mm, f"Tag {code}")


@router.get("/batches/{batch_id}/export")
def batch_export(
    batch_id: uuid.UUID,
    format: Literal["csv", "svg", "eps", "pdf"],
    part: int = Query(1, ge=1),
    size_mm: float | None = Query(None, alias="sizeMm", ge=10, le=200),
    design: DesignKey | None = None,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
    settings: Settings = Depends(settings_dep),
):
    batch = db.get(TagBatch, batch_id)
    if batch is None:
        raise not_found("Batch not found", "BATCH_NOT_FOUND")
    if format in {"svg", "eps"} and batch.quantity > MAX_ZIP_TAGS:
        raise bad_request(
            f"A ZIP of single files is limited to {MAX_ZIP_TAGS:,} tags. Use the PDF or CSV export for this batch.",
            "EXPORT_TOO_LARGE",
        )
    parts = max(1, math.ceil(batch.quantity / PDF_PAGES_PER_FILE))
    if format == "pdf" and part > parts:
        raise bad_request(f"This batch has {parts} PDF part(s).", "EXPORT_BAD_PART")

    mm = size_mm or settings.qr_physical_size_mm
    details = {"format": format, "part": part, "sizeMm": mm, "design": design}
    audit(db, Actor.admin(admin.id), "batch.export", "TagBatch", batch.id, details)
    db.commit()

    # The size is in the name so the 27, 30 and 33 mm files of one batch cannot be mixed up.
    base = f"cartag-{_file_slug(batch.name)}-{design + '-' if design else ''}{mm:g}mm"
    headers = {"Cache-Control": "no-store"}

    if format == "csv":

        def rows() -> Iterator[str]:
            yield "serial,code,url\r\n"
            for serial, code in _iter_batch_tags(batch.id):
                yield ",".join(map(csv_cell, [format_serial(serial), code, tag_url(batch.base_url, code)])) + "\r\n"

        headers["Content-Disposition"] = f'attachment; filename="cartag-{_file_slug(batch.name)}.csv"'
        return StreamingResponse(rows(), media_type="text/csv; charset=utf-8", headers=headers)

    if format == "pdf":
        first_serial = (part - 1) * PDF_PAGES_PER_FILE
        with SessionLocal() as session:
            codes = session.scalars(
                select(Tag.code)
                .where(Tag.batch_id == batch.id)
                .order_by(Tag.serial)
                .offset(first_serial)
                .limit(PDF_PAGES_PER_FILE)
            ).all()
        matrices = (matrix_for_tag(batch.base_url, code) for code in codes)
        if design:
            pdf = render_tag_pdf(matrices, DESIGNS[design], mm, batch.name)
        else:
            pdf = render_pdf(matrices, mm, batch.name)
        suffix = f"-part-{part}-of-{parts}" if parts > 1 else ""
        headers["Content-Disposition"] = f'attachment; filename="{base}{suffix}.pdf"'
        return Response(pdf, media_type="application/pdf", headers=headers)

    # svg or eps: one file per tag, named so the printer can match it to the CSV.
    def archive() -> Iterator[bytes]:
        writer = _ChunkWriter()
        with zipfile.ZipFile(writer, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:  # type: ignore[arg-type]
            for serial, code in _iter_batch_tags(batch.id):
                matrix = matrix_for_tag(batch.base_url, code)
                content = _render_one(matrix, format, mm, design, code)
                bundle.writestr(f"{format_serial(serial)}_{code}.{format}", content.encode())
                yield from writer.drain()
        yield from writer.drain()

    headers["Content-Disposition"] = f'attachment; filename="{base}-{format}.zip"'
    return StreamingResponse(archive(), media_type="application/zip", headers=headers)


# ---------- tags ----------
@router.get("/tags")
def tags_list(
    q: str | None = Query(None, max_length=60),
    status: TagStatus | None = None,
    stock: StockStatus | None = None,
    batch_id: uuid.UUID | None = Query(None, alias="batchId"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(Tag).outerjoin(User, Tag.owner_id == User.id)
    count_stmt = select(func.count()).select_from(Tag).outerjoin(User, Tag.owner_id == User.id)

    conditions = []
    if status:
        conditions.append(Tag.status == status)
    if stock:
        conditions.append(Tag.stock_status == stock)
    if batch_id:
        conditions.append(Tag.batch_id == batch_id)
    if q and q.strip():
        term = q.strip()
        digits = re.sub(r"\D", "", term)
        options = [
            Tag.code.startswith(term.upper(), autoescape=True),
            User.name.icontains(term, autoescape=True),
        ]
        if len(digits) >= 3:
            options.append(User.phone.contains(digits, autoescape=True))
        if re.fullmatch(r"\d{1,9}", term):
            options.append(Tag.serial == int(term))
        conditions.append(or_(*options))

    for condition in conditions:
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = (
        db.scalars(
            stmt.options(joinedload(Tag.owner), joinedload(Tag.batch))
            .order_by(Tag.serial)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .unique()
        .all()
    )
    return {"total": total, "page": page, "pageSize": page_size, "items": [admin_tag_view(t) for t in rows]}


@router.get("/tags/{code}")
def tag_detail(code: str = Depends(tag_code_param), db: Session = Depends(get_db)):
    tag = _load_tag(db, code)
    scan_count = db.scalar(select(func.count()).select_from(ScanEvent).where(ScanEvent.tag_id == tag.id)) or 0
    scans = db.scalars(
        select(ScanEvent).where(ScanEvent.tag_id == tag.id).order_by(ScanEvent.at.desc()).limit(20)
    ).all()
    history = db.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "Tag", AuditLog.entity_id == str(tag.id))
        .order_by(AuditLog.at.desc())
        .limit(30)
    ).all()
    return {
        "tag": admin_tag_view(tag),
        "scanCount": scan_count,
        "recentScans": [{"id": str(s.id), "at": s.at, "outcome": s.outcome.value} for s in scans],
        "history": [
            {"id": str(h.id), "at": h.at, "actorType": h.actor_type.value, "action": h.action, "meta": h.meta}
            for h in history
        ],
    }


@router.post("/tags/{code}/mark-sold")
def tag_mark_sold(
    code: str = Depends(tag_code_param), admin: Admin = Depends(require_admin), db: Session = Depends(get_db)
):
    tag_service.mark_tag_sold(db, admin.id, code)
    return {"tag": admin_tag_view(_load_tag(db, code))}


@router.post("/tags/{code}/retire")
def tag_retire(
    body: RetireTagIn,
    code: str = Depends(tag_code_param),
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
):
    tag_service.retire_tag(db, admin.id, code, body.reason)
    return {"tag": admin_tag_view(_load_tag(db, code))}


# ---------- users ----------
@router.get("/users")
def users_list(
    q: str | None = Query(None, max_length=60),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    db: Session = Depends(get_db),
):
    condition = None
    if q and q.strip():
        term = q.strip()
        digits = re.sub(r"\D", "", term)
        options = [User.name.icontains(term, autoescape=True)]
        if len(digits) >= 3:
            options.append(User.phone.contains(digits, autoescape=True))
        condition = or_(*options)

    count_stmt = select(func.count()).select_from(User)
    stmt = select(User, func.count(Tag.id)).outerjoin(Tag, Tag.owner_id == User.id).group_by(User.id)
    if condition is not None:
        count_stmt = count_stmt.where(condition)
        stmt = stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    rows = db.execute(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": [
            {
                "id": str(u.id),
                "name": u.name,
                "phone": u.phone if u.status != UserStatus.DELETED else None,
                "phoneVerified": u.phone_verified_at is not None,
                "status": u.status.value,
                "createdAt": u.created_at,
                "lastLoginAt": u.last_login_at,
                "tagCount": tag_count,
            }
            for u, tag_count in rows
        ],
    }


def _set_user_status(db: Session, admin: Admin, user_id: uuid.UUID, status: UserStatus) -> dict[str, Any]:
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User not found", "USER_NOT_FOUND")
    if user.status == UserStatus.DELETED:
        raise bad_request("This account has been closed.", "USER_DELETED")
    user.status = status
    audit(db, Actor.admin(admin.id), "user.block" if status == UserStatus.BLOCKED else "user.unblock", "User", user.id)
    db.commit()
    # A blocked owner is logged out everywhere straight away.
    if status == UserStatus.BLOCKED:
        revoke_user_sessions(db, user.id)
    return {"ok": True, "status": status.value}


@router.post("/users/{user_id}/block")
def user_block(user_id: uuid.UUID, admin: Admin = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_user_status(db, admin, user_id, UserStatus.BLOCKED)


@router.post("/users/{user_id}/unblock")
def user_unblock(user_id: uuid.UUID, admin: Admin = Depends(require_admin), db: Session = Depends(get_db)):
    return _set_user_status(db, admin, user_id, UserStatus.ACTIVE)


# ---------- account deletion requests ----------
@router.get("/deletion-requests")
def deletion_requests(
    status: DeletionStatus | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, alias="pageSize", ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(AccountDeletionRequest).options(joinedload(AccountDeletionRequest.user))
    count_stmt = select(func.count()).select_from(AccountDeletionRequest)
    if status:
        stmt = stmt.where(AccountDeletionRequest.status == status)
        count_stmt = count_stmt.where(AccountDeletionRequest.status == status)
    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(AccountDeletionRequest.requested_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    tag_counts = dict(
        db.execute(
            select(Tag.owner_id, func.count()).where(Tag.owner_id.in_([r.user_id for r in rows])).group_by(Tag.owner_id)
        ).all()
    )
    return {
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": [
            {
                "id": str(r.id),
                "status": r.status.value,
                "reason": r.reason,
                "requestedAt": r.requested_at,
                "decidedAt": r.decided_at,
                "note": r.note,
                "user": {"id": str(r.user.id), "name": r.user.name, "phone": r.user.phone},
                "tagCount": tag_counts.get(r.user_id, 0),
            }
            for r in rows
        ],
    }


@router.post("/deletion-requests/{request_id}/approve")
def deletion_approve(
    request_id: uuid.UUID,
    body: DecisionIn,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
):
    request = account_service.decide_deletion(db, admin.id, request_id, True, body.note)
    return {"request": account_service.deletion_view(request)}


@router.post("/deletion-requests/{request_id}/reject")
def deletion_reject(
    request_id: uuid.UUID,
    body: DecisionIn,
    admin: Admin = Depends(require_admin),
    db: Session = Depends(get_db),
):
    request = account_service.decide_deletion(db, admin.id, request_id, False, body.note)
    return {"request": account_service.deletion_view(request)}
