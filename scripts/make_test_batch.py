"""Makes a small local test batch whose QR codes point at this laptop on the Wi-Fi, so a phone can scan them.

    $env:PYTHONPATH = "."
    uv run python scripts/make_test_batch.py "http://<laptop-ip>:4000" test-qr
"""

import html
import sys
from pathlib import Path

from sqlalchemy import select

from cartag.db import SessionLocal
from cartag.models import Admin, Tag
from cartag.qr import matrix_for_tag, render_svg
from cartag.qr.matrix import tag_url
from cartag.services.batches import generate_batch
from cartag.services.tags import mark_tag_sold

base_url, out_dir = sys.argv[1], Path(sys.argv[2])
out_dir.mkdir(exist_ok=True)

with SessionLocal() as db:
    admin = db.scalar(select(Admin).where(Admin.disabled_at.is_(None)).order_by(Admin.created_at))
    if admin is None:
        sys.exit("No admin in the dev database. Create one with: python -m cartag.cli create-admin")
    batch = generate_batch(db, admin.id, "Local phone test", 3, base_url)
    tags = db.scalars(select(Tag).where(Tag.batch_id == batch.id).order_by(Tag.serial)).all()
    codes = [(t.serial, t.code) for t in tags]
    # Two tags are sold (can be turned on). The third stays in stock, to see that it cannot be activated.
    for _, code in codes[:2]:
        mark_tag_sold(db, admin.id, code)

cards = []
for serial, code in codes:
    url = tag_url(base_url, code)
    svg = render_svg(matrix_for_tag(base_url, code), 60)
    (out_dir / f"{serial:06d}_{code}.svg").write_text(svg, encoding="utf-8")
    note = "sold, can be activated" if serial <= codes[1][0] else "still in stock, cannot be activated"
    cards.append(
        f'<figure><div class="qr">{svg.split("?>", 1)[1]}</div>'
        f"<figcaption><b>{serial:06d}</b> ({note})<br><code>{html.escape(url)}</code></figcaption></figure>"
    )

page = f"""<!doctype html><meta charset="utf-8"><title>CARTAG test QR codes</title>
<style>body{{font:16px system-ui;margin:2rem;background:#fff;color:#000}}.row{{display:flex;gap:2rem;flex-wrap:wrap}}
figure{{margin:0;max-width:300px}}.qr svg{{width:300px;height:300px;display:block}}
code{{word-break:break-all;font-size:12px}}</style>
<h1>CARTAG test QR codes</h1><p>Phone and laptop must be on the same Wi-Fi. Server: {html.escape(base_url)}</p>
<div class="row">{"".join(cards)}</div>"""
(out_dir / "index.html").write_text(page, encoding="utf-8")
for _, code in codes:
    print(tag_url(base_url, code))
