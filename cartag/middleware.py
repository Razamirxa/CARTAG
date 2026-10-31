"""Small ASGI middlewares. Written as plain ASGI (not BaseHTTPMiddleware) so streamed exports work."""

from collections.abc import Callable

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from cartag.config import Settings

UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _json_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


class SecurityHeadersMiddleware:
    """Browser hardening headers on every response (the equivalent of helmet)."""

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        csp = "; ".join(
            [
                "default-src 'self'",
                "base-uri 'self'",
                "font-src 'self' https: data:",
                "form-action 'self'",
                "frame-ancestors 'self'",
                "img-src 'self' data:",
                "object-src 'none'",
                "script-src 'self'",
                "script-src-attr 'none'",
                "style-src 'self' https: 'unsafe-inline'",
            ]
        )
        headers = {
            b"content-security-policy": csp,
            b"x-content-type-options": "nosniff",
            b"x-frame-options": "SAMEORIGIN",
            b"cross-origin-opener-policy": "same-origin",
            b"cross-origin-resource-policy": "same-origin",
            b"x-dns-prefetch-control": "off",
        }
        if settings.is_production:
            headers[b"strict-transport-security"] = "max-age=15552000; includeSubDomains"
        self.headers = [(k, v.encode()) for k, v in headers.items()]

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    (k, v) for k, v in self.headers if k not in existing
                ]
            await send(message)

        await self.app(scope, receive, send_with_headers)


class SameOriginMiddleware:
    """CSRF defence for cookie sessions, on top of SameSite=Lax.

    State-changing requests from a browser must come from our own origin.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.origin = settings.public_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS or not scope["path"].startswith("/api"):
            await self.app(scope, receive, send)
            return

        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        origin = headers.get("origin")
        blocked = False
        if origin:
            blocked = origin != self.origin
        else:
            # No Origin header: browsers always send Origin or Sec-Fetch-Site on cross-site requests.
            fetch_site = headers.get("sec-fetch-site")
            blocked = bool(fetch_site) and fetch_site not in {"same-origin", "none"}

        if blocked:
            await _json_error(403, "BAD_ORIGIN", "Cross-site request blocked")(scope, receive, send)
            return
        await self.app(scope, receive, send)


class _BodyTooLarge(Exception):
    pass


class BodyLimitMiddleware:
    """Rejects request bodies over a limit. The CSV import route reads its own (larger) body after
    checking that the caller is an admin, so it is exempt here."""

    def __init__(self, app: ASGIApp, limit: int = 100_000, exempt: Callable[[str], bool] | None = None):
        self.app = app
        self.limit = limit
        self.exempt = exempt or (lambda _path: False)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in UNSAFE_METHODS or self.exempt(scope["path"]):
            await self.app(scope, receive, send)
            return

        too_large = _json_error(413, "PAYLOAD_TOO_LARGE", "Request is too large")
        headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
        declared = headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > self.limit:
            await too_large(scope, receive, send)
            return

        received = 0
        started = False

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.limit:
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _BodyTooLarge:
            if not started:
                await too_large(scope, receive, send)
