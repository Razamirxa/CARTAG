import logging
import mimetypes
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from cartag.config import Settings, get_settings
from cartag.db import SessionLocal
from cartag.deps import limit_api
from cartag.errors import install_error_handlers
from cartag.middleware import BodyLimitMiddleware, SameOriginMiddleware, SecurityHeadersMiddleware
from cartag.ratelimit import Limiters
from cartag.routers import admin, admin_auth, admin_shop, auth, me, payments, public, scan, shop
from cartag.services.payments import create_provider
from cartag.services.sessions import purge_expired
from cartag.services.sms import SmsProvider, create_sms_provider

log = logging.getLogger("cartag")

IMPORT_PATH = "/api/admin/batches/import"


def create_app(
    settings: Settings | None = None,
    sms: SmsProvider | None = None,
    enable_ip_rate_limits: bool = True,
    payment_provider: str | None = None,
) -> FastAPI:
    """Builds the application. Tests pass their own SMS provider and turn per-IP limits off."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # Remove expired sessions and old OTP rows each time the server starts.
        try:
            with SessionLocal() as db:
                purge_expired(db)
        except Exception:  # noqa: BLE001
            log.warning("Startup cleanup failed", exc_info=True)
        log.info("CARTAG server started (env=%s, base url=%s)", settings.app_env, settings.public_base_url)
        yield

    # The interactive docs are handy in development but would expose the whole API shape in production.
    docs_on = settings.api_docs and not settings.is_production
    app = FastAPI(
        title="CARTAG",
        lifespan=lifespan,
        docs_url="/api/docs" if docs_on else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs_on else None,
    )
    app.state.sms = sms or create_sms_provider(settings)
    # Online payment. The name "none" switches it off even when the settings turn it on (tests use this).
    app.state.payment_provider = create_provider(settings, payment_provider)
    app.state.limiters = Limiters(enabled=enable_ip_rate_limits)

    # The last middleware added runs first: security headers wrap everything, then the CSRF check,
    # then the body size limit.
    app.add_middleware(BodyLimitMiddleware, limit=100_000, exempt=lambda path: path == IMPORT_PATH)
    app.add_middleware(SameOriginMiddleware, settings=settings)
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    install_error_handlers(app)

    @app.get("/healthz", include_in_schema=False)
    def healthz():
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return {"ok": True}

    # The page people see after scanning a QR. Plain server-rendered HTML.
    app.include_router(scan.router)

    api = APIRouter(prefix="/api", dependencies=[Depends(limit_api)])
    for module in (public, auth, me, shop, payments, admin_auth, admin, admin_shop):
        api.include_router(module.router)

    @api.api_route("/{rest:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"], include_in_schema=False)
    def api_not_found(rest: str):
        return JSONResponse({"error": {"code": "NOT_FOUND", "message": "Not found"}}, status_code=404)

    app.include_router(api)

    # The React app, when it has been built. Everything that is not the API or a scan goes to it.
    dist = Path(settings.web_dist_dir).resolve()
    index = dist / "index.html"
    if index.exists():
        # Some systems have no entry for woff2, which would be served as a generic download.
        mimetypes.add_type("font/woff2", ".woff2")
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
        base_url = settings.public_base_url.rstrip("/")
        # The build turns the public pages into finished HTML: dist/index.html is Home, dist/shop/index.html
        # is Shop. Every other page gets the empty shell, app.html (older builds only have index.html).
        public_pages = ["/"] + sorted(f"/{page.parent.name}" for page in dist.glob("*/index.html"))
        shell = dist / "app.html" if (dist / "app.html").exists() else index

        def page(file: Path) -> HTMLResponse:
            html = file.read_text(encoding="utf-8").replace("__PUBLIC_BASE_URL__", base_url)
            return HTMLResponse(html, headers={"Cache-Control": "no-cache"})

        @app.get("/robots.txt", include_in_schema=False)
        def robots():
            # Pages behind a login, the API and the scan pages (which carry noindex too) are not for search engines.
            private = ["/admin", "/account", "/activate", "/cart", "/checkout", "/orders", "/pay", "/api/"]
            private += ["/t/", "/T/"]
            lines = ["User-agent: *", "Allow: /", *(f"Disallow: {path}" for path in private)]
            return PlainTextResponse("\n".join([*lines, "", f"Sitemap: {base_url}/sitemap.xml", ""]))

        @app.get("/sitemap.xml", include_in_schema=False)
        def sitemap():
            urls = "".join(f"<url><loc>{base_url}{path}</loc></url>" for path in public_pages)
            xml = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n'
            )
            return Response(xml, media_type="application/xml")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            candidate = (dist / path).resolve()
            if dist != candidate and dist not in candidate.parents:
                return page(shell)
            if path and candidate.is_file():
                return page(candidate) if candidate.suffix == ".html" else FileResponse(candidate)
            if (candidate / "index.html").is_file():
                return page(candidate / "index.html")
            return page(shell)

    return app


app = create_app()
