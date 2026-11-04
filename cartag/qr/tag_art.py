"""The finished tag: the approved artwork with this tag's own QR, as SVG, EPS and PDF.

Everything is drawn on a 100 x 100 tag and scaled to the physical size, so the three formats agree.
The text is already outlines (tag_text.py), so a print shop needs no font.

The look follows the client's mockups, lit from above: a thin dark line round the edge (a wider one
along the bottom for the tag's thickness), a thin bright bevel just inside it, a face that is a little
lighter at the top, and a shaded corner mark (polished silver on Burgundy). The shading sits under the
text and the QR, which stay flat and solid so a camera sees full contrast.
"""

import colorsys
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.pdfgen.canvas import FILL_NON_ZERO

from cartag.qr import tag_text
from cartag.qr.matrix import QrMatrix
from cartag.qr.render import MM_TO_PT

RADIUS = 13.5
"""Corner radius of the tag."""
QR_WIDTH = 41.0
QR_TOP = 32.3
"""The QR (without its quiet zone) is 41% of the tag, centred, as in the approved designs."""
QR_LEFT = (100 - QR_WIDTH) / 2
ACCENT_INSET = 3.0
"""The corner mark sits this far in from the top and right edges, with a rim of the tag colour around it."""
ACCENT_FROM_X = 81.6
ACCENT_TO_Y = 20.0
"""Its straight side runs from (81.6, 3) on the top to (97, 20) on the right."""
ACCENT_END = 1.4
"""How far the two sharp ends are rounded off."""
KAPPA = 0.5522847498
"""Control-point distance that makes a cubic curve a good quarter circle."""
EDGE = 0.8
"""Width of the dark band along the bottom that shows the tag's thickness."""
BEVEL = 0.7
"""Width of the bright bevel that runs round the edge of the face."""
DOWN = (50.0, 0.0, 50.0, 100.0)
"""Light comes from above: the body shading runs straight down the tag."""
ACCENT_SHINE = (97.0, 3.0, 88.5, 12.2)
"""The corner mark's shading runs from the tag's corner to the middle of the mark's straight side."""

TEXT_PATHS = (tag_text.LOGO_CAR, tag_text.LOGO_TAG, tag_text.CONTACT, tag_text.SCAN)

WHITE, BLACK = "#FFFFFF", "#000000"


@dataclass(frozen=True)
class Gradient:
    """A straight shading in tag units (y down) from (x0, y0) to (x1, y1), through (offset, colour) stops."""

    coords: tuple[float, float, float, float]
    stops: tuple[tuple[float, str], ...]


Paint = str | Gradient


def _rgb(color: str) -> tuple[float, float, float]:
    return tuple(int(color[i : i + 2], 16) / 255 for i in (1, 3, 5))  # type: ignore[return-value]


def _hex(rgb: Iterable[float]) -> str:
    return "#" + "".join(f"{round(c * 255):02X}" for c in rgb)


def _mix(color: str, toward: str, amount: float) -> str:
    """`color` moved `amount` (0 to 1) of the way to `toward`, as #RRGGBB."""
    return _hex(a + (b - a) * amount for a, b in zip(_rgb(color), _rgb(toward), strict=True))


def _lighten(color: str, amount: float) -> str:
    """`color` with its lightness raised by `amount` (0 to 1) and its hue kept, so a lit edge of a burgundy
    tag stays burgundy instead of turning pink-grey. Some saturation goes, as on a real lit edge."""
    h, lightness, s = colorsys.rgb_to_hls(*_rgb(color))
    return _hex(colorsys.hls_to_rgb(h, min(1.0, lightness + amount), s * 0.6))


@dataclass(frozen=True)
class TagDesign:
    key: str
    label: str
    background: str
    ink: str
    """Colour of the text and the QR modules."""
    accent: str | None
    """Colour of the corner mark, if the design has one."""
    edge_dark: float
    """How far the thickness band along the bottom is mixed towards black."""
    bevel_light: float
    """How much lighter the bevel is at the top edge (it fades to half of that at the bottom)."""
    face_light: float
    """How far the top of the face is mixed towards white."""
    face_dark: float
    """How far the bottom of the face is mixed towards black."""
    metallic: bool = False
    """The corner mark is polished silver rather than a flat colour."""

    @property
    def inverted(self) -> bool:
        """Light QR modules on a dark tag. Many phone cameras read it, some scanners do not."""
        return sum(_rgb(self.background)) < sum(_rgb(self.ink))

    @property
    def edge(self) -> str:
        return _mix(self.background, BLACK, self.edge_dark)

    @property
    def bevel(self) -> Gradient:
        top, bottom = (_lighten(self.background, amount) for amount in (self.bevel_light, self.bevel_light / 2))
        return Gradient(DOWN, ((0.0, top), (1.0, bottom)))

    @property
    def face(self) -> Gradient:
        """The client's colour across the middle, a little lighter at the top and darker at the bottom."""
        top, bottom = _mix(self.background, WHITE, self.face_light), _mix(self.background, BLACK, self.face_dark)
        return Gradient(DOWN, ((0.0, top), (0.5, self.background), (1.0, bottom)))

    @property
    def accent_paint(self) -> Gradient | None:
        if not self.accent:
            return None
        if self.metallic:
            stops = ((0.0, "#9C9C9E"), (0.35, "#E2E2E4"), (0.55, "#FFFFFF"), (0.75, self.accent), (1.0, "#B9B9BB"))
        else:
            stops = ((0.0, _mix(self.accent, BLACK, 0.18)), (0.6, self.accent), (1.0, self.accent))
        return Gradient(ACCENT_SHINE, stops)


# The four approved designs. Tag and corner colours are the client's own codes for the tags (the tag
# burgundy is darker than the website's #74152B). The edge, bevel and face shading were measured from
# the client's mockups. Burgundy's corner is drawn as polished silver; a metallic ink or foil is the
# printer's call.
DESIGNS: dict[str, TagDesign] = {
    design.key: design
    for design in (
        TagDesign("ivory", "Ivory", "#F9F6F1", "#0A0A0A", "#D20C1E", 0.06, 0.04, 0.0, 0.02),
        TagDesign("glacier", "Glacier", "#BBD0E3", "#0A0A0A", "#7194B2", 0.3, 0.12, 0.3, 0.02),
        TagDesign("burgundy", "Burgundy", "#47031C", "#FAFAFA", "#F7F7F7", 0.75, 0.2, 0.05, 0.13, metallic=True),
        TagDesign("black", "Black", "#0D0D0D", "#FAFAFA", "#C4FA1C", 0.45, 0.2, 0.03, 0.15),
    )
}


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
    ]
    shading = _shaded_shapes(design)
    parts.append("<defs>")
    for name, paint, _ in shading:
        if isinstance(paint, Gradient):
            parts.append(_svg_gradient(f"{name}-shade", paint))
    parts.append("</defs>")
    for name, paint, steps in shading:
        fill = f"url(#{name}-shade)" if isinstance(paint, Gradient) else paint
        parts.append(f'<path id="{name}" d="{_svg_path(steps)}" fill="{fill}"/>')
    parts.append(f'<g id="text" fill="{design.ink}">')
    parts.extend(f'<path d="{d}"/>' for d in TEXT_PATHS)
    parts.append("</g>")
    parts.append(
        f'<g id="qr" transform="translate({_num(QR_LEFT)} {_num(QR_TOP)}) scale({module:.6f})" '
        f'shape-rendering="crispEdges"><path d="{qr_path}" fill="{design.ink}"/></g>'
    )
    parts.append("</svg>\n")
    return "".join(parts)


def _svg_gradient(gradient_id: str, gradient: Gradient) -> str:
    stops = "".join(f'<stop offset="{_num(offset)}" stop-color="{color}"/>' for offset, color in gradient.stops)
    x1, y1, x2, y2 = (_num(n) for n in gradient.coords)
    return (
        f'<linearGradient id="{gradient_id}" gradientUnits="userSpaceOnUse" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">'
        f"{stops}</linearGradient>"
    )


_COMMAND = re.compile(r"([MLCZ])([^MLCZ]*)")


def _commands(path: str) -> list[tuple[str, list[float]]]:
    """Reads the M, L, C, Z paths that tag_text.py holds."""
    return [(cmd, [float(n) for n in args.split()]) for cmd, args in _COMMAND.findall(path)]


Steps = list[tuple[str, tuple[float, ...]]]


def _outline_ops(inset: float = 0.0, bottom_inset: float | None = None) -> Steps:
    """The tag outline (y down, 100 units): straight edges joined by quarter-circle corners.

    `inset` moves the edges in (the corners keep their centres), which gives the bevel and the face inside
    the dark edge; `bottom_inset` moves the bottom edge by a different amount.
    """
    lo, hi, b = inset, 100 - inset, 100 - (inset if bottom_inset is None else bottom_inset)
    r = RADIUS - inset
    k = r * KAPPA
    return [
        ("M", (lo + r, lo)),
        ("L", (hi - r, lo)),
        ("C", (hi - r + k, lo, hi, lo + r - k, hi, lo + r)),
        ("L", (hi, b - r)),
        ("C", (hi, b - r + k, hi - r + k, b, hi - r, b)),
        ("L", (lo + r, b)),
        ("C", (lo + r - k, b, lo, b - r + k, lo, b - r)),
        ("L", (lo, lo + r)),
        ("C", (lo, lo + r - k, lo + r - k, lo, lo + r, lo)),
        ("Z", ()),
    ]


def _round_corner(
    before: tuple[float, float], corner: tuple[float, float], after: tuple[float, float]
) -> tuple[str, tuple[float, ...]]:
    """A cubic that rounds a sharp corner, from a point on the incoming edge to one on the outgoing edge."""
    c1 = (before[0] + 2 / 3 * (corner[0] - before[0]), before[1] + 2 / 3 * (corner[1] - before[1]))
    c2 = (after[0] + 2 / 3 * (corner[0] - after[0]), after[1] + 2 / 3 * (corner[1] - after[1]))
    return ("C", (*c1, *c2, *after))


def _accent_ops() -> Steps:
    """The corner mark: the tag's top-right corner, inset by a rim, cut off by a straight line, ends rounded."""
    g, e = ACCENT_INSET, ACCENT_END
    r = RADIUS - g
    k = r * KAPPA
    top_end = (ACCENT_FROM_X, g)
    side_end = (100 - g, ACCENT_TO_Y)
    dx, dy = top_end[0] - side_end[0], top_end[1] - side_end[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    on_side = (side_end[0], side_end[1] - e)
    near_side = (side_end[0] + ux * e, side_end[1] + uy * e)
    near_top = (top_end[0] - ux * e, top_end[1] - uy * e)
    on_top = (top_end[0] + e, g)
    return [
        ("M", on_top),
        ("L", (100 - RADIUS, g)),
        ("C", (100 - RADIUS + k, g, 100 - g, RADIUS - k, 100 - g, RADIUS)),
        ("L", on_side),
        _round_corner(on_side, side_end, near_side),
        ("L", near_top),
        _round_corner(near_top, top_end, on_top),
        ("Z", ()),
    ]


def _svg_path(steps: Steps) -> str:
    return "".join(cmd + " ".join(_num(n) for n in args) for cmd, args in steps)


def _shaded_shapes(design: TagDesign) -> list[tuple[str, Paint, Steps]]:
    """The tag body and corner mark as (name, paint, steps), from back to front."""
    shapes: list[tuple[str, Paint, Steps]] = [
        ("tag", design.edge, _outline_ops()),
        ("bevel", design.bevel, _outline_ops(0.0, EDGE)),
        ("face", design.face, _outline_ops(BEVEL, EDGE + BEVEL)),
    ]
    if design.accent_paint:
        shapes.append(("corner", design.accent_paint, _accent_ops()))
    return shapes


def _all_shapes(design: TagDesign) -> list[tuple[Paint, Steps]]:
    """Every filled shape except the QR, as (paint, steps) from back to front."""
    shapes = [(paint, steps) for _, paint, steps in _shaded_shapes(design)]
    for d in TEXT_PATHS:
        shapes.append((design.ink, [(cmd, tuple(args)) for cmd, args in _commands(d)]))
    return shapes


def _ps_function(stops: tuple[tuple[float, str], ...]) -> str:
    """A PostScript function from 0..1 to RGB through the stops (a stitching function for more than two)."""

    def segment(c0: str, c1: str) -> str:
        a, b = (" ".join(f"{v:.4f}" for v in _rgb(c)) for c in (c0, c1))
        return f"<< /FunctionType 2 /Domain [0 1] /C0 [{a}] /C1 [{b}] /N 1 >>"

    parts = [segment(stops[i][1], stops[i + 1][1]) for i in range(len(stops) - 1)]
    if len(parts) == 1:
        return parts[0]
    bounds = " ".join(_num(offset) for offset, _ in stops[1:-1])
    encode = " ".join("0 1" for _ in parts)
    return f"<< /FunctionType 3 /Domain [0 1] /Functions [{' '.join(parts)}] /Bounds [{bounds}] /Encode [{encode}] >>"


def render_tag_eps(matrix: QrMatrix, design: TagDesign, tag_mm: float, title: str = "CARTAG tag") -> str:
    """Encapsulated PostScript: filled paths and smooth shadings (PostScript 3), in RGB, y pointing up."""
    side = tag_mm * MM_TO_PT
    scale = side / 100
    lines = [
        "%!PS-Adobe-3.0 EPSF-3.0",
        f"%%BoundingBox: 0 0 {math.ceil(side)} {math.ceil(side)}",
        f"%%HiResBoundingBox: 0 0 {side:.3f} {side:.3f}",
        f"%%Title: {re.sub(r'[^\x20-\x7e]', '', title)}",
        "%%Creator: CARTAG",
        "%%LanguageLevel: 3",
        "%%EndComments",
        "gsave",
        f"{scale:.6f} {scale:.6f} scale",
    ]

    def flip(y: float) -> str:
        return _num(100 - y)

    def emit(paint: Paint, steps: Steps) -> None:
        if isinstance(paint, str):
            r, g, b = _rgb(paint)
            lines.append(f"{r:.4f} {g:.4f} {b:.4f} setrgbcolor")
        else:
            lines.append("gsave")
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
        if isinstance(paint, str):
            lines.append("fill")
            return
        x0, y0, x1, y1 = paint.coords
        lines.append("clip")
        lines.append(
            f"<< /ShadingType 2 /ColorSpace /DeviceRGB /Coords [{_num(x0)} {flip(y0)} {_num(x1)} {flip(y1)}] "
            f"/Extend [true true] /Function {_ps_function(paint.stops)} >> shfill"
        )
        lines.append("grestore")

    for paint, steps in _all_shapes(design):
        emit(paint, steps)
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
        for paint, steps in shapes:
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
            if isinstance(paint, str):
                pdf.setFillColorRGB(*_rgb(paint))
                pdf.drawPath(path, stroke=0, fill=1, fillMode=FILL_NON_ZERO)
                continue
            pdf.saveState()
            pdf.clipPath(path, stroke=0, fill=0, fillMode=FILL_NON_ZERO)
            colors = [HexColor(color) for _, color in paint.stops]
            positions = [offset for offset, _ in paint.stops]
            x0, y0, x1, y1 = paint.coords
            pdf.linearGradient(px(x0), py(y0), px(x1), py(y1), colors, positions)
            pdf.restoreState()
        pdf.setFillColorRGB(*_rgb(design.ink))
        module = QR_WIDTH / matrix.size
        for x, y, w in _qr_rects(matrix):
            pdf.rect(px(x), py(y + module), px(w), px(module), stroke=0, fill=1)
        pdf.showPage()
    pdf.save()
    return out.getvalue()
