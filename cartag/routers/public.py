from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from cartag.db import get_db
from cartag.deps import client_ip, ip_hash, limit_scan, limiters_dep, tag_code_param
from cartag.ratelimit import Limiters
from cartag.services.public_tag import ScanContext, lookup_public_tag

router = APIRouter(prefix="/public", tags=["public"])


@router.get("/tags/{code}", dependencies=[Depends(limit_scan)])
def public_tag(
    request: Request,
    response: Response,
    code: str = Depends(tag_code_param),
    db: Session = Depends(get_db),
    limiters: Limiters = Depends(limiters_dep),
):
    """JSON version of the scan page data. The HTML page at /t/{code} is what finders actually use."""
    result = lookup_public_tag(db, code, ScanContext(ip_hash(request), request.headers.get("user-agent")))
    if result["state"] == "not_found":
        limiters.scan_miss.record(client_ip(request) or "unknown")
        response.status_code = 404
    return result
