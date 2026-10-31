import re
import zipfile
from io import BytesIO

import pytest
import zxingcpp
from PIL import Image, ImageDraw

from cartag.qr import matrix_for_tag
from cartag.qr.tag_art import (
    DESIGNS,
    QR_LEFT,
    QR_TOP,
    QR_WIDTH,
    describe_tag,
    render_tag_eps,
    render_tag_pdf,
    render_tag_svg,
)
from tests.helpers import admin_client, generate_batch, make_app

MATRIX = matrix_for_tag("https://cartag.pk", "K7X9M2QP4A")
PAYLOAD = "HTTPS://CARTAG.PK/T/K7X9M2QP4A"


def paint_svg(svg: str, design_key: str) -> Image.Image:
    """Draws the tag's background and QR path from the SVG text itself, as a camera would see them."""
    design = DESIGNS[design_key]
    scale = 10
    image = Image.new("RGB", (100 * scale, 100 * scale), design.background)
    draw = ImageDraw.Draw(image)
    left, top, module = map(
        float, re.search(r'translate\(([\d.]+) ([\d.]+)\) scale\(([\d.]+)\)', svg).groups()
    )
    for x, y, w in re.findall(r"M([\d.]+) ([\d.]+)h([\d.]+)v1", svg.split('id="qr"')[1]):
        x0, y0 = (left + float(x) * module) * scale, (top + float(y) * module) * scale
        draw.rectangle((x0, y0, x0 + float(w) * module * scale - 1, y0 + module * scale - 1), fill=design.ink)
    return image


@pytest.mark.parametrize("key", list(DESIGNS))
def test_every_design_svg_carries_a_scannable_qr_at_the_right_place(key):
    svg = render_tag_svg(MATRIX, DESIGNS[key], 30)
    assert 'width="30mm" height="30mm" viewBox="0 0 100 100"' in svg
    image = paint_svg(svg, key)
    results = zxingcpp.read_barcodes(image, try_invert=DESIGNS[key].inverted)
    assert [r.text for r in results] == [PAYLOAD]


def test_dark_designs_are_flagged_as_inverted_and_light_ones_are_not():
    assert {k for k, d in DESIGNS.items() if d.inverted} == {"burgundy", "black"}
    # A reader that does not try the opposite polarity cannot read them. This is the risk to tell the client.
    dark = paint_svg(render_tag_svg(MATRIX, DESIGNS["black"], 30), "black")
    assert zxingcpp.read_barcodes(dark, try_invert=False) == []


def test_corner_mark_only_on_designs_that_have_one():
    with_corner = {k for k, d in DESIGNS.items() if 'id="corner"' in render_tag_svg(MATRIX, d, 30)}
    assert with_corner == {"ivory", "black"}


def test_text_is_outlines_not_live_text():
    svg = render_tag_svg(MATRIX, DESIGNS["ivory"], 30)
    assert "<text" not in svg and "font-family" not in svg


def test_module_size_follows_the_whole_tag_size():
    ivory = DESIGNS["ivory"]
    assert describe_tag(MATRIX, 30, ivory)["qrMm"] == pytest.approx(QR_WIDTH / 100 * 30, abs=0.01)
    assert describe_tag(MATRIX, 30, ivory)["moduleMm"] == pytest.approx(0.424, abs=0.001)
    assert describe_tag(MATRIX, 27, ivory)["printable"] is True
    assert describe_tag(MATRIX, 15, ivory)["printable"] is False
    assert QR_LEFT + QR_WIDTH < 100 and QR_TOP + QR_WIDTH < 100


def test_pdf_has_one_tag_sized_page_per_tag_and_eps_has_its_bounding_box():
    pdf = render_tag_pdf([MATRIX, MATRIX, MATRIX], DESIGNS["burgundy"], 30, "Batch")
    assert pdf.startswith(b"%PDF")
    assert len(re.findall(rb"/Type\s*/Page\b", pdf)) == 3
    assert re.search(rb"/MediaBox\s*\[\s*0\s+0\s+85\.03\d*\s+85\.03\d*\s*\]", pdf)
    eps = render_tag_eps(MATRIX, DESIGNS["ivory"], 30)
    assert eps.startswith("%!PS-Adobe-3.0 EPSF-3.0")
    assert "%%BoundingBox: 0 0 86 86" in eps
    assert eps.count("rectfill") == len(MATRIX.dark_runs())


def test_export_with_a_design_names_the_file_after_it_and_is_audited():
    app, _ = make_app()
    admin = admin_client(app)
    batch_id, codes = generate_batch(admin, 2)

    res = admin.get(f"/api/admin/batches/{batch_id}/export?format=svg&sizeMm=30&design=ivory")
    assert res.status_code == 200
    assert "-ivory-30mm-svg.zip" in res.headers["content-disposition"]
    with zipfile.ZipFile(BytesIO(res.content)) as bundle:
        assert bundle.namelist() == [f"{i + 1:06d}_{codes[i]}.svg" for i in range(2)]
        assert 'id="corner"' in bundle.read(bundle.namelist()[0]).decode()

    pdf = admin.get(f"/api/admin/batches/{batch_id}/export?format=pdf&sizeMm=30&design=black")
    assert pdf.content.startswith(b"%PDF") and "-black-30mm" in pdf.headers["content-disposition"]
    assert admin.get(f"/api/admin/batches/{batch_id}/export?format=svg&design=plaid").status_code == 400

    detail = admin.get(f"/api/admin/batches/{batch_id}?sizeMm=30&design=ivory").json()["print"]
    assert detail["physicalMm"] == 30 and detail["qrMm"] == pytest.approx(12.3, abs=0.01)
    assert detail["inverted"] is False
    assert admin.get(f"/api/admin/batches/{batch_id}?sizeMm=30&design=black").json()["print"]["inverted"] is True
