from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


def error_detail(message: str, code: str, *, fields: list[dict[str, str]] | None = None, **extra: Any) -> dict[str, Any]:
    detail: dict[str, Any] = {"message": message, "code": code}
    if fields:
        detail["fields"] = fields
    if extra:
        detail.update(extra)
    return detail


def raise_api_error(status_code: int, message: str, code: str, *, fields: list[dict[str, str]] | None = None, **extra: Any) -> None:
    raise HTTPException(status_code=status_code, detail=error_detail(message, code, fields=fields, **extra))


def _coerce_detail(detail: Any) -> dict[str, Any]:
    if isinstance(detail, dict):
        message = detail.get("message")
        code = detail.get("code")
        if isinstance(message, str) and isinstance(code, str):
            normalized = dict(detail)
            fields = normalized.get("fields")
            if isinstance(fields, list):
                normalized["fields"] = [
                    {"field": str(item.get("field", "")), "message": str(item.get("message", ""))}
                    for item in fields
                    if isinstance(item, dict) and item.get("message")
                ]
            return normalized
    if isinstance(detail, str):
        return error_detail(detail, "REQUEST_FAILED")
    return error_detail("The request could not be completed.", "REQUEST_FAILED")


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": _coerce_detail(exc.detail)})


async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    fields: list[dict[str, str]] = []
    for issue in exc.errors():
        location = ".".join(str(part) for part in issue.get("loc", []) if part not in {"body"})
        fields.append(
            {
                "field": location or "request",
                "message": issue.get("msg", "Invalid value."),
            }
        )

    return JSONResponse(
        status_code=422,
        content={
            "detail": error_detail(
                "One or more inputs were invalid.",
                "VALIDATION_ERROR",
                fields=fields,
            )
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", extra={"path": str(request.url.path)})
    return JSONResponse(
        status_code=500,
        content={
            "detail": error_detail(
                "An unexpected server error occurred. Please try again.",
                "INTERNAL_SERVER_ERROR",
            )
        },
    )
