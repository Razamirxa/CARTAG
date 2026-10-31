import re
from collections.abc import Iterable
from io import BytesIO

from reportlab.pdfgen import canvas

from cartag.qr.matrix import QUIET_ZONE, QrMatrix

MM_TO_PT = 72 / 25.4


def render_svg(matrix: QrMatrix, physical_mm: float) -> str:
    """One-path SVG, sized in millimetres so a print shop places it at the exact physical size."""
    total = matrix.size + 2 * QUIET_ZONE
    path = "".join(f"M{x + QUIET_ZONE} {y + QUIET_ZONE}h{w}v1h-{w}z" for x, y, w in matrix.dark_runs())
    mm = f"{physical_mm:g}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{mm}mm" height="{mm}mm" '
        f'viewBox="0 0 {total} {total}" shape-rendering="crispEdges">'
        f'<rect width="{total}" height="{total}" fill="#fff"/>'
        f'<path d="{path}" fill="#000"/>'
        "</svg>\n"
    )


def render_eps(matrix: QrMatrix, physical_mm: float, title: str = "CARTAG QR") -> str:
    """Encapsulated PostScript, written by hand: filled rectangles on a unit grid.

    No library needed and every printer RIP understands it.
    """
    import math

    total = matrix.size + 2 * QUIET_ZONE
    side_pt = physical_mm * MM_TO_PT
    scale = side_pt / total
    box = math.ceil(side_pt)
    rects = "\n".join(
        f"{x + QUIET_ZONE} {total - 1 - (y + QUIET_ZONE)} {w} 1 rectfill" for x, y, w in matrix.dark_runs()
    )
    safe_title = re.sub(r"[^\x20-\x7e]", "", title)
    return "\n".join(
        [
            "%!PS-Adobe-3.0 EPSF-3.0",
            f"%%BoundingBox: 0 0 {box} {box}",
            f"%%HiResBoundingBox: 0 0 {side_pt:.3f} {side_pt:.3f}",
            f"%%Title: {safe_title}",
            "%%Creator: CARTAG",
            "%%EndComments",
            "gsave",
            f"{scale:.6f} {scale:.6f} scale",
            "1 setgray",
            f"0 0 {total} {total} rectfill",
            "0 setgray",
            rects,
            "grestore",
            "%%EOF",
            "",
        ]
    )


def render_pdf(matrices: Iterable[QrMatrix], physical_mm: float, title: str) -> bytes:
    """A PDF with one page per tag, each page exactly the QR size, vector rectangles only."""
    side = physical_mm * MM_TO_PT
    out = BytesIO()
    pdf = canvas.Canvas(out, pagesize=(side, side), pageCompression=1)
    pdf.setTitle(title)
    pdf.setCreator("CARTAG")
    for matrix in matrices:
        total = matrix.size + 2 * QUIET_ZONE
        module = side / total
        pdf.setFillGray(1)
        pdf.rect(0, 0, side, side, stroke=0, fill=1)
        pdf.setFillGray(0)
        for x, y, w in matrix.dark_runs():
            # PDF's origin is the bottom-left corner, so the row is flipped.
            pdf.rect(
                (x + QUIET_ZONE) * module,
                side - (y + QUIET_ZONE + 1) * module,
                w * module,
                module,
                stroke=0,
                fill=1,
            )
        pdf.showPage()
    pdf.save()
    return out.getvalue()
