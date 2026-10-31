import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic.alias_generators import to_camel
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("cartag")


class AppError(Exception):
    """An error we meant to raise. Its message is safe to show to the client."""

    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def bad_request(message: str, code: str = "BAD_REQUEST", details: Any = None) -> AppError:
    return AppError(400, code, message, details)


def unauthorized(message: str = "Please log in to continue", code: str = "UNAUTHORIZED") -> AppError:
    return AppError(401, code, message)


def forbidden(message: str = "You do not have access to this", code: str = "FORBIDDEN") -> AppError:
    return AppError(403, code, message)


def not_found(message: str = "Not found", code: str = "NOT_FOUND") -> AppError:
    return AppError(404, code, message)


def conflict(message: str, code: str = "CONFLICT") -> AppError:
    return AppError(409, code, message)


def too_many(
    message: str = "Too many attempts. Please try again later.",
    code: str = "RATE_LIMITED",
    details: Any = None,
) -> AppError:
    return AppError(429, code, message, details)


def error_response(status: int, code: str, message: str, details: Any = None, headers: dict | None = None):
    body: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return JSONResponse({"error": body}, status_code=status, headers=headers)


def _issue_field(loc: tuple) -> str:
    # ("body", "plate") -> "plate"; ("query", "page") -> "page"
    # Field names go to the browser in camelCase, like everything else in the API.
    parts = [to_camel(str(p)) for p in loc if p not in ("body", "query", "path")]
    return ".".join(parts)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        headers = None
        retry = exc.details.get("retryAfterSeconds") if isinstance(exc.details, dict) else None
        if exc.status == 429 and retry:
            headers = {"Retry-After": str(retry)}
        return error_response(exc.status, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = exc.errors()
        if any(e["type"] == "json_invalid" for e in errors):
            return error_response(400, "BAD_JSON", "Request body is not valid JSON")
        issues = [
            {"field": _issue_field(tuple(e["loc"])), "message": str(e["msg"]).removeprefix("Value error, ")}
            for e in errors
        ]
        first = issues[0]["message"] if issues else "Invalid input"
        return error_response(400, "VALIDATION_ERROR", first, issues)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "ERROR")
        message = "Not found" if exc.status_code == 404 else str(exc.detail)
        return error_response(exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
        return error_response(500, "INTERNAL", "Something went wrong. Please try again.")
