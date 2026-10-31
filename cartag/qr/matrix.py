from dataclasses import dataclass

import segno

QUIET_ZONE = 4


@dataclass(frozen=True)
class QrMatrix:
    size: int
    """Modules per side, not counting the quiet zone."""
    rows: tuple[bytes, ...]
    """Row-major, 1 = dark module."""
    version: int
    mode: str
    """"alphanumeric" gives the smallest symbol for an upper-case URL."""

    def is_dark(self, x: int, y: int) -> bool:
        return self.rows[y][x] == 1

    def dark_count(self) -> int:
        return sum(sum(row) for row in self.rows)

    def dark_runs(self) -> list[tuple[int, int, int]]:
        """Horizontal runs of dark modules as (x, y, width), so vector output stays small."""
        runs: list[tuple[int, int, int]] = []
        for y, row in enumerate(self.rows):
            x = 0
            while x < self.size:
                if row[x] != 1:
                    x += 1
                    continue
                start = x
                while x < self.size and row[x] == 1:
                    x += 1
                runs.append((start, y, x - start))
        return runs


def build_matrix(text: str) -> QrMatrix:
    """Builds the QR module matrix.

    Error correction level Q (about 25% recovery) tolerates scratches and wear on a vehicle tag
    while keeping the symbol small enough to scan from a distance.
    """
    qr = segno.make(text, error="q", boost_error=False, micro=False)
    rows = tuple(bytes(row) for row in qr.matrix)
    return QrMatrix(size=len(rows), rows=rows, version=int(qr.version), mode=str(qr.mode))


def tag_url(base_url: str, code: str) -> str:
    """The URL a scanner opens."""
    return f"{base_url.rstrip('/')}/t/{code}"


def qr_payload(url: str) -> str:
    """What is actually encoded in the QR.

    Upper-casing the URL lets the QR use alphanumeric mode, which is never bigger and often smaller
    than mixed case (the saving grows with the length of the domain). That is safe because the
    scheme and host are case-insensitive and the scan route upper-cases the tag code before lookup.
    """
    return url.upper()


def matrix_for_tag(base_url: str, code: str) -> QrMatrix:
    return build_matrix(qr_payload(tag_url(base_url, code)))


def describe_print(matrix: QrMatrix, physical_mm: float) -> dict:
    """What the printer needs to know: how big is one module on the physical tag."""
    total = matrix.size + 2 * QUIET_ZONE
    module_mm = physical_mm / total
    return {
        "version": matrix.version,
        "modulesPerSide": matrix.size,
        "mode": matrix.mode,
        "physicalMm": physical_mm,
        "moduleMm": round(module_mm, 3),
        # Below about 0.33 mm per module most printers and phone cameras struggle.
        "printable": module_mm >= 0.33,
    }


def csv_cell(value: str | int) -> str:
    text = str(value)
    if any(ch in text for ch in ('"', ",", "\r", "\n")):
        return '"' + text.replace('"', '""') + '"'
    return text
