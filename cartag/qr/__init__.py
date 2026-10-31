"""QR codes for tags: one module matrix, rendered as SVG, EPS and PDF so print files never disagree."""

from cartag.qr.matrix import (
    QUIET_ZONE,
    QrMatrix,
    build_matrix,
    csv_cell,
    describe_print,
    matrix_for_tag,
    qr_payload,
    tag_url,
)
from cartag.qr.render import MM_TO_PT, render_eps, render_pdf, render_svg

__all__ = [
    "MM_TO_PT",
    "QUIET_ZONE",
    "QrMatrix",
    "build_matrix",
    "csv_cell",
    "describe_print",
    "matrix_for_tag",
    "qr_payload",
    "render_eps",
    "render_pdf",
    "render_svg",
    "tag_url",
]
