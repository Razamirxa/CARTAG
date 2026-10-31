"""The finished tag: the approved artwork with this tag's own QR, as SVG, EPS and PDF.

Everything is drawn on a 100 x 100 tag and scaled to the physical size, so the three formats agree.
The text is already outlines (tag_text.py), so a print shop needs no font.
"""

import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO

from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import FILL_NON_ZERO

from cartag.qr import tag_text
from cartag.qr.matrix import QrMatrix
from cartag.qr.render import MM_TO_PT

RADIUS = 15.0
"""Corner radius of the tag."""
QR_WIDTH = 41.0
QR_TOP = 32.3
"""The QR (without its quiet zone) is 41% of the tag, centred, as in the approved designs."""
QR_LEFT = (100 - QR_WIDTH) / 2
ACCENT = ((81.0, 0.0), (85.0, 0.0), (100.0, 15.0), (100.0, 20.0))
"""The coloured corner: a straight cut from (81, 0) to (100, 20), following the tag's rounded corner."""
KAPPA = 0.5522847498
"""Control-point distance that makes a cubic curve a good quarter circle."""

TEXT_PATHS = (tag_text.LOGO_CAR, tag_text.LOGO_TAG, tag_text.CONTACT, tag_text.SCAN)


@dataclass(frozen=True)
class TagDesign:
    key: str
    label: str
    background: str
    ink: str
    """Colour of the text and the QR modules."""
    accent: str | None
    """Colour of the corner mark, if the design has one."""

    @property
    def inverted(self) -> bool:
        """Light QR modules on a dark tag. Many phone cameras read it, some scanners do not."""
        return self.background in {"#74152B", "#0A0A0A"}


# The four approved designs. Black, Ivory and Burgundy are the client's locked palette. Glacier and the
# two corner colours were sampled from the approved artwork, so they need confirming against the
# manufacturer's colour reference.
DESIGNS: dict[str, TagDesign] = {
    design.key: design
    for design in (
        TagDesign("ivory", "Ivory", "#F5F1E8", "#0A0A0A", "#D10A1D"),
        TagDesign("glacier", "Glacier", "#C0D0E0", "#0A0A0A", None),
        TagDesign("burgundy", "Burgundy", "#74152B", "#F5F1E8", None),
        TagDesign("black", "Black", "#0A0A0A", "#F5F1E8", "#C4F818"),
    )
}


def _rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _qr_rects(matrix: QrMatrix) -> list[tuple[float, float, float]]:
    """Dark runs as (x, y, width) in tag units; every run is one module high."""
    module = QR_WIDTH / matrix.size
    return [(QR_LEFT + x * module, QR_TOP + y * module, w * module) for x, y, w in matrix.dark_runs()]


def describe_tag(matrix: QrMatrix, tag_mm: float, design: TagDesign) -> dict:
    """What the printer needs to know: how big is one module on this tag."""
    module_mm = QR_WIDTH / 100 * tag_mm / matrix.size
    return {
        "version": matrix.version,
        "modulesPerSide": matrix.size,
        "mode": matrix.mode,
        "physicalMm": tag_mm,
        "qrMm": round(QR_WIDTH / 100 * tag_mm, 2),
        "moduleMm": round(module_mm, 3),
        "inverted": design.inverted,
        # Below about 0.33 mm per module most printers and phone cameras struggle.
        "printable": module_mm >= 0.33,
    }


def _num(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def render_tag_svg(matrix: QrMatrix, design: TagDesign, tag_mm: float) -> str:
    """One tag as SVG, sized in millimetres. The QR is a single path of horizontal runs."""
    module = QR_WIDTH / matrix.size
    qr_path = "".join(f"M{x} {y}h{w}v1h-{w}z" for x, y, w in matrix.dark_runs())
    mm = f"{tag_mm:g}"
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{mm}mm" height="{mm}mm" viewBox="0 0 100 100">',
        f'<path id="tag" d="{_svg_path(_outline_ops())}" fill="{design.background}"/>',
    ]
    if design.accent:
        parts.append(f'<path id="corner" d="{_svg_path(_accent_ops())}" fill="{design.accent}"/>')
    parts.append(f'<g id="text" fill="{design.ink}">')
    parts.extend(f'<path d="{d}"/>' for d in TEXT_PATHS)
    parts.append("</g>")
    parts.append(
        f'<g id="qr" transform="translate({_num(QR_LEFT)} {_num(QR_TOP)}) scale({module:.6f})" '
        f'shape-rendering="crispEdges"><path d="{qr_path}" fill="{design.ink}"/></g>'
    )
    parts.append("</svg>\n")
    return "".join(parts)


_COMMAND = re.compile(r"([MLCZ])([^MLCZ]*)")


def _commands(path: str) -> list[tuple[str, list[float]]]:
    """Reads the M, L, C, Z paths that tag_text.py holds."""
    return [(cmd, [float(n) for n in args.split()]) for cmd, args in _COMMAND.findall(path)]


Steps = list[tuple[str, tuple[float, ...]]]


def _outline_ops() -> Steps:
    """The tag outline (y down, 100 units): straight edges joined by quarter-circle corners."""
    r, k = RADIUS, RADIUS * KAPPA
    return [
        ("M", (r, 0.0)),
        ("L", (100 - r, 0.0)),
        ("C", (100 - r + k, 0.0, 100.0, r - k, 100.0, r)),
        ("L", (100.0, 100 - r)),
        ("C", (100.0, 100 - r + k, 100 - r + k, 100.0, 100 - r, 100.0)),
        ("L", (r, 100.0)),
        ("C", (r - k, 100.0, 0.0, 100 - r + k, 0.0, 100 - r)),
        ("L", (0.0, r)),
        ("C", (0.0, r - k, r - k, 0.0, r, 0.0)),
        ("Z", ()),
    ]


def _accent_ops() -> Steps:
    """The corner mark: the tag's own top-right corner, cut off by a straight line."""
    k = RADIUS * KAPPA
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = ACCENT
    return [
        ("M", (x0, y0)),
        ("L", (x1, y1)),
        ("C", (x1 + k, y1, x2, y2 - k, x2, y2)),
        ("L", (x3, y3)),
        ("Z", ()),
    ]


def _svg_path(steps: Steps) -> str:
    return "".join(cmd + " ".join(_num(n) for n in args) for cmd, args in steps)


def _all_shapes(design: TagDesign) -> list[tuple[str, Steps]]:
    """Every filled shape except the QR, as (colour, steps) from back to front."""
    shapes = [(design.background, _outline_ops())]
    if design.accent:
        shapes.append((design.accent, _accent_ops()))
    for d in TEXT_PATHS:
        shapes.append((design.ink, [(cmd, tuple(args)) for cmd, args in _commands(d)]))
    return shapes


def render_tag_eps(matrix: QrMatrix, design: TagDesign, tag_mm: float, title: str = "CARTAG tag") -> str:
    """Encapsulated PostScript: filled paths only, in RGB, y pointing up."""
    side = tag_mm * MM_TO_PT
    scale = side / 100
    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        f"%%BoundingBox: 0 0 {math.ceil(side)} {math.ceil(side)}",
        f"%%HiResBoundingBox: 0 0 {side:.3f} {side:.3f}",
        f"%%Title: {re.sub(r'[^\x20-\x7e]', '', title)}",
        "%%Creator: CARTAG",
        "%%EndComments",
        "gsave",
        f"{scale:.6f} {scale:.6f} scale",
    ]

    def flip(y: float) -> str:
        return _num(100 - y)

    def emit(color: str, steps: Steps) -> None:
        r, g, b = _rgb(color)
        lines.append(f"{r:.4f} {g:.4f} {b:.4f} setrgbcolor")
        lines.append("newpath")
        for cmd, a in steps:
            if cmd == "M":
                lines.append(f"{_num(a[0])} {flip(a[1])} moveto")
            elif cmd == "L":
                lines.append(f"{_num(a[0])} {flip(a[1])} lineto")
            elif cmd == "C":
                lines.append(
                    f"{_num(a[0])} {flip(a[1])} {_num(a[2])} {flip(a[3])} {_num(a[4])} {flip(a[5])} curveto"
                )
            else:
                lines.append("closepath")
        lines.append("fill")

    for color, steps in _all_shapes(design):
        emit(color, steps)
    r, g, b = _rgb(design.ink)
    lines.append(f"{r:.4f} {g:.4f} {b:.4f} setrgbcolor")
    module = QR_WIDTH / matrix.size
    for x, y, w in _qr_rects(matrix):
        lines.append(f"{_num(x)} {flip(y + module)} {_num(w)} {_num(module)} rectfill")
    lines += ["grestore", "%%EOF", ""]
    return "\n".join(lines)


def render_tag_pdf(matrices: Iterable[QrMatrix], design: TagDesign, tag_mm: float, title: str) -> bytes:
    """A PDF with one page per tag, each page exactly the tag size, vector shapes only."""
    side = tag_mm * MM_TO_PT
    scale = side / 100
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=(side, side), pageCompression=1)
    pdf.setTitle(title)
    pdf.setCreator("CARTAG")

    def px(x: float) -> float:
        return x * scale

    def py(y: float) -> float:
        return side - y * scale

    shapes = _all_shapes(design)
    for matrix in matrices:
        for color, steps in shapes:
            pdf.setFillColorRGB(*_rgb(color))
            path = pdf.beginPath()
            for cmd, a in steps:
                if cmd == "M":
                    path.moveTo(px(a[0]), py(a[1]))
                elif cmd == "L":
                    path.lineTo(px(a[0]), py(a[1]))
                elif cmd == "C":
                    path.curveTo(px(a[0]), py(a[1]), px(a[2]), py(a[3]), px(a[4]), py(a[5]))
                else:
                    path.close()
            pdf.drawPath(path, stroke=0, fill=1, fillMode=FILL_NON_ZERO)
        pdf.setFillColorRGB(*_rgb(design.ink))
        module = QR_WIDTH / matrix.size
        for x, y, w in _qr_rects(matrix):
            pdf.rect(px(x), py(y + module), px(w), px(module), stroke=0, fill=1)
        pdf.showPage()
    pdf.save()
    return out.getvalue()
