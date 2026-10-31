import re

import zxingcpp
from PIL import Image

from cartag.domain import TAG_CODE_ALPHABET
from cartag.qr import (
    QUIET_ZONE,
    QrMatrix,
    build_matrix,
    csv_cell,
    describe_print,
    matrix_for_tag,
    qr_payload,
    render_eps,
    render_svg,
    tag_url,
)
from cartag.security import new_tag_code


def decode(matrix: QrMatrix) -> str | None:
    """Draws the matrix as pixels, the way a camera would see a printed tag, and decodes it."""
    scale = 6
    total = matrix.size + 2 * QUIET_ZONE
    image = Image.new("L", (total * scale, total * scale), 255)
    pixels = image.load()
    for y in range(matrix.size):
        for x in range(matrix.size):
            if matrix.is_dark(x, y):
                for dy in range(scale):
                    for dx in range(scale):
                        pixels[(x + QUIET_ZONE) * scale + dx, (y + QUIET_ZONE) * scale + dy] = 0
    results = zxingcpp.read_barcodes(image)
    return results[0].text if results else None


def test_tag_codes_are_random_safe_and_unique():
    seen = set()
    for _ in range(20_000):
        code = new_tag_code()
        assert len(code) == 10
        assert all(ch in TAG_CODE_ALPHABET for ch in code)
        seen.add(code)
    assert len(seen) == 20_000


def test_payload_is_the_scan_url_in_upper_case():
    base = "https://cartag.pk"
    assert tag_url(f"{base}/", "K7X9M2QP4A") == "https://cartag.pk/t/K7X9M2QP4A"
    assert qr_payload("https://cartag.pk/t/K7X9M2QP4A") == "HTTPS://CARTAG.PK/T/K7X9M2QP4A"
    assert matrix_for_tag(base, "K7X9M2QP4A").mode == "alphanumeric"


def test_upper_case_is_never_a_bigger_symbol_than_mixed_case():
    for domain in ("https://cartag.pk", "https://cartag.com.pk", "https://tags.example-company.com.pk"):
        upper = matrix_for_tag(domain, "K7X9M2QP4A")
        mixed = build_matrix(tag_url(domain, "K7X9M2QP4A"))
        assert upper.size <= mixed.size


def test_round_trip_decodes_to_exactly_the_url_for_many_random_tags():
    for _ in range(40):
        code = new_tag_code()
        assert decode(matrix_for_tag("https://cartag.pk", code)) == f"HTTPS://CARTAG.PK/T/{code}"


def test_round_trip_with_a_longer_domain():
    code = new_tag_code()
    matrix = matrix_for_tag("https://tags.example-company.com.pk", code)
    assert decode(matrix) == f"HTTPS://TAGS.EXAMPLE-COMPANY.COM.PK/T/{code}"


def test_two_tags_never_share_a_pattern():
    a = matrix_for_tag("https://cartag.pk", "AAAAAAAAAA")
    b = matrix_for_tag("https://cartag.pk", "AAAAAAAAAB")
    assert a.rows != b.rows


def test_error_correction_survives_damage():
    """Level Q should still decode after blanking a small patch, like a scratch on a tag."""
    matrix = matrix_for_tag("https://cartag.pk", "K7X9M2QP4A")
    damaged = list(map(bytearray, matrix.rows))
    for y in range(12, 15):
        for x in range(12, 15):
            damaged[y][x] ^= 1
    worn = QrMatrix(matrix.size, tuple(bytes(r) for r in damaged), matrix.version, matrix.mode)
    assert decode(worn) == "HTTPS://CARTAG.PK/T/K7X9M2QP4A"


MATRIX = matrix_for_tag("https://cartag.pk", "K7X9M2QP4A")


def test_svg_is_sized_in_millimetres_with_a_single_path():
    svg = render_svg(MATRIX, 25)
    total = MATRIX.size + 2 * QUIET_ZONE
    assert 'width="25mm"' in svg
    assert f'viewBox="0 0 {total} {total}"' in svg
    assert svg.count("<path ") == 1
    assert "<image" not in svg


def test_svg_path_covers_exactly_the_dark_modules():
    svg = render_svg(MATRIX, 25)
    d = re.search(r'<path d="([^"]+)"', svg).group(1)
    area = sum(int(width) for width in re.findall(r"h(\d+)v1", d))
    assert area == MATRIX.dark_count()


def test_eps_is_valid_postscript_with_the_right_bounding_box():
    eps = render_eps(MATRIX, 25)
    assert eps.startswith("%!PS-Adobe-3.0 EPSF-3.0")
    # 25 mm is 70.87 pt, so the integer box is 71.
    assert "%%BoundingBox: 0 0 71 71" in eps
    assert "rectfill" in eps
    assert eps.rstrip().endswith("%%EOF")


def test_print_description_flags_sizes_that_are_too_small():
    assert describe_print(MATRIX, 25)["printable"] is True
    assert describe_print(MATRIX, 10)["printable"] is False
    assert describe_print(MATRIX, 25)["mode"] == "alphanumeric"


def test_csv_cells_are_quoted_when_needed():
    assert csv_cell("plain") == "plain"
    assert csv_cell('a,"b"') == '"a,""b"""'
