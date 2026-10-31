from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from cartag.db import get_db
from cartag.deps import client_ip, ip_hash, limit_scan, limiters_dep
from cartag.domain import normalize_tag_code
from cartag.ratelimit import Limiters
from cartag.scan.i18n import LANGUAGES, Language
from cartag.scan.page import render_scan_page
from cartag.services.public_tag import ScanContext, lookup_public_tag

router = APIRouter(tags=["scan"])


def pick_language(request: Request) -> Language:
    asked = request.query_params.get("lang")
    if asked in LANGUAGES:
        return asked  # type: ignore[return-value]
    # English is shown first; Urdu only when the browser asks for it first.
    header = request.headers.get("accept-language", "")
    for part in header.split(","):
        tag = part.split(";")[0].strip().lower()
        if tag.startswith("ur"):
            return "ur"
        if tag.startswith("en"):
            return "en"
    return "en"


# {code:path} so odd input such as "a/b" gets the same generic "not found" page as any unknown code.
# The QR holds the whole link in upper case (alphanumeric mode), so a phone opens /T/CODE, not /t/CODE.
# Both must work, or every printed tag would show "page not found".
@router.get("/T/{code:path}", response_class=HTMLResponse, include_in_schema=False, dependencies=[Depends(limit_scan)])
@router.get("/t/{code:path}", response_class=HTMLResponse, dependencies=[Depends(limit_scan)])
def scan_page(
    code: str,
    request: Request,
    db: Session = Depends(get_db),
    limiters: Limiters = Depends(limiters_dep),
):
    """The page a finder sees after scanning a QR. Server-rendered so it loads fast on weak mobile data."""
    code = normalize_tag_code(code)
    result = lookup_public_tag(db, code, ScanContext(ip_hash(request), request.headers.get("user-agent")))
    status, html = render_scan_page(result, pick_language(request), code)
    if result["state"] == "not_found":
        limiters.scan_miss.record(client_ip(request) or "unknown")

    return HTMLResponse(
        html,
        status_code=status,
        headers={
            # The owner can change what is shown at any moment, and the page holds personal data.
            "Cache-Control": "no-store",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )
