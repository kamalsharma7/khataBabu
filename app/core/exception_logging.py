from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import (
    http_exception_handler as default_http_exception_handler,
    request_validation_exception_handler as default_validation_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger("app.errors")


def register_exception_logging(application: FastAPI) -> None:
    @application.exception_handler(HTTPException)
    async def log_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        if exc.status_code >= 500:
            logger.error(
                "http_exception",
                status_code=exc.status_code,
                detail=exc.detail,
                path=request.url.path,
                method=request.method,
            )
        elif exc.status_code >= 400:
            logger.warning(
                "http_exception",
                status_code=exc.status_code,
                detail=exc.detail,
                path=request.url.path,
                method=request.method,
            )
        return await default_http_exception_handler(request, exc)

    @application.exception_handler(RequestValidationError)
    async def log_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.warning(
            "request_validation_error",
            path=request.url.path,
            method=request.method,
            errors=exc.errors(),
        )
        return await default_validation_handler(request, exc)

    @application.exception_handler(Exception)
    async def log_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_exception",
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )
