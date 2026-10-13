import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

logger = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class BadRequestError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"


class UpstreamError(AppError):
    status_code = 502
    code = "UPSTREAM_ERROR"


class UpstreamTimeout(UpstreamError):
    status_code = 504
    code = "UPSTREAM_TIMEOUT"


def error_body(code: str, message: str, **extra) -> dict:
    return {"error": {"code": code, "message": message, **extra}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message))

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [{"loc": [str(part) for part in err["loc"]], "msg": err["msg"]} for err in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "Invalid request parameters.", details=details),
        )

    @app.exception_handler(RateLimitExceeded)
    async def handle_rate_limit(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content=error_body(
                "RATE_LIMITED",
                f"Too many requests (limit: {exc.detail}). Please wait a minute and try again.",
            ),
            headers={"Retry-After": "60"},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content=error_body("INTERNAL_ERROR", "Something went wrong on our side."))
