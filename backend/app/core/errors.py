"""One error shape for the whole API, and no stack traces on the wire."""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger("obaidi")


class AppError(Exception):
    """Expected, client-facing failure. Anything else is a 500."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "error",
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, code="not_found", status_code=status.HTTP_404_NOT_FOUND)


class ConflictError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict", status_code=status.HTTP_409_CONFLICT)


class AuthError(AppError):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            message, code="unauthorized", status_code=status.HTTP_401_UNAUTHORIZED
        )


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many attempts. Try again later.") -> None:
        super().__init__(
            message,
            code="rate_limited",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


def _body(code: str, message: str, details: object | None = None) -> dict:
    payload: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        payload["error"]["details"] = details
    return payload


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code, content=_body(exc.code, exc.message)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "message": err["msg"]}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_body("validation_error", "Invalid request data", details),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        message = (
            "Internal server error"
            if settings.is_production
            else f"Internal server error: {exc!r}"
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_body("internal_error", message),
        )
