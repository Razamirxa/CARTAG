import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from cartag.domain import (
    MAX_BATCH_SIZE,
    BatchSource,
    TagStatus,
    is_valid_tag_code,
    normalize_tag_code,
)
from cartag.errors import bad_request, conflict
from cartag.models import Tag, TagBatch
from cartag.security import new_tag_code
from cartag.services.audit import Actor, audit

CHUNK = 5000
MAX_GENERATE_ROUNDS = 5


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def batch_view(batch: TagBatch, by_status: dict[str, int] | None = None) -> dict[str, Any]:
    view: dict[str, Any] = {
        "id": str(batch.id),
        "name": batch.name,
        "quantity": batch.quantity,
        "source": batch.source.value,
        "baseUrl": batch.base_url,
        "createdByAdminId": str(batch.created_by_admin_id) if batch.created_by_admin_id else None,
        "createdAt": batch.created_at,
    }
    if by_status is not None:
        view["byStatus"] = by_status
    return view


def _count_in_batch(db: Session, batch_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(Tag).where(Tag.batch_id == batch_id)) or 0


def generate_batch(db: Session, admin_id: uuid.UUID, name: str, quantity: int, base_url: str) -> TagBatch:
    """Creates a batch with `quantity` brand new random tag codes.

    Everything happens in one transaction: either the whole batch exists or none of it does.
    """
    batch = TagBatch(
        name=name,
        quantity=quantity,
        source=BatchSource.GENERATED,
        base_url=base_url,
        created_by_admin_id=admin_id,
    )
    db.add(batch)
    db.flush()

    have = 0
    for round_number in range(MAX_GENERATE_ROUNDS + 1):
        if have >= quantity:
            break
        if round_number >= MAX_GENERATE_ROUNDS:
            db.rollback()
            raise RuntimeError("Could not generate enough unique tag codes")
        fresh: set[str] = set()
        while len(fresh) < quantity - have:
            fresh.add(new_tag_code())
        for part in _chunks(sorted(fresh), CHUNK):
            # A collision with an existing code is astronomically unlikely, but the unique
            # constraint is the real guarantee: DO NOTHING drops it and the next round tops up.
            stmt = pg_insert(Tag).on_conflict_do_nothing(index_elements=["code"])
            db.execute(
                stmt,
                [
                    {"id": uuid.uuid4(), "code": code, "batch_id": batch.id, "status": TagStatus.NOT_ACTIVE}
                    for code in part
                ],
            )
        have = _count_in_batch(db, batch.id)

    audit(
        db,
        Actor.admin(admin_id),
        "batch.generate",
        "TagBatch",
        batch.id,
        {"name": name, "quantity": quantity},
    )
    db.commit()
    return batch


def parse_codes(csv: str) -> tuple[list[str], list[str]]:
    """Reads codes from pasted text or CSV: first column of each line, header row ignored."""
    import re

    codes: list[str] = []
    problems: list[str] = []
    seen: dict[str, int] = {}

    for index, raw_line in enumerate(csv.splitlines()):
        line = raw_line.strip()
        if not line:
            continue
        first = line.split(",")[0].strip().strip('"')
        code = normalize_tag_code(first)

        if index == 0 and re.fullmatch(r"(code|tag_?code|id)", first, re.IGNORECASE):
            continue  # header
        if not is_valid_tag_code(code):
            problems.append(f'Line {index + 1}: "{first[:30]}" is not a valid tag code')
            continue
        if code in seen:
            problems.append(f"Line {index + 1}: {code} repeats line {seen[code]}")
            continue
        seen[code] = index + 1
        codes.append(code)
    return codes, problems


def import_batch(db: Session, admin_id: uuid.UUID, name: str, csv: str, base_url: str) -> TagBatch:
    codes, problems = parse_codes(csv)
    if problems:
        raise bad_request(
            f"The file has {len(problems)} problem(s). Nothing was imported.", "IMPORT_INVALID", problems[:20]
        )
    if not codes:
        raise bad_request("The file has no tag codes.", "IMPORT_EMPTY")
    if len(codes) > MAX_BATCH_SIZE:
        raise bad_request("A batch can hold at most 100,000 codes.", "IMPORT_TOO_LARGE")

    clashes: list[str] = []
    for part in _chunks(codes, CHUNK):
        clashes.extend(db.scalars(select(Tag.code).where(Tag.code.in_(part))))
    if clashes:
        raise conflict(
            f"{len(clashes)} code(s) already exist. Nothing was imported. First few: {', '.join(clashes[:5])}",
            "IMPORT_DUPLICATES",
        )

    batch = TagBatch(
        name=name,
        quantity=len(codes),
        source=BatchSource.IMPORTED,
        base_url=base_url,
        created_by_admin_id=admin_id,
    )
    db.add(batch)
    db.flush()
    for part in _chunks(codes, CHUNK):
        db.execute(
            pg_insert(Tag),
            [{"id": uuid.uuid4(), "code": code, "batch_id": batch.id, "status": TagStatus.NOT_ACTIVE} for code in part],
        )
    audit(
        db,
        Actor.admin(admin_id),
        "batch.import",
        "TagBatch",
        batch.id,
        {"name": name, "quantity": len(codes)},
    )
    db.commit()
    return batch


def list_batches(db: Session) -> list[dict[str, Any]]:
    batches = list(db.scalars(select(TagBatch).order_by(TagBatch.created_at.desc()).limit(200)))
    counts = db.execute(select(Tag.batch_id, Tag.status, func.count()).group_by(Tag.batch_id, Tag.status)).all()
    out = []
    for batch in batches:
        by_status = {status.value: count for batch_id, status, count in counts if batch_id == batch.id}
        out.append(batch_view(batch, by_status))
    return out
