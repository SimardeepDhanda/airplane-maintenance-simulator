"""Uniform error envelope: {"error": {"code", "message", "details"?}}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class APIError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def not_found(kind: str, identifier: str) -> APIError:
    return APIError(status.HTTP_404_NOT_FOUND, f"{kind}_not_found", f"No {kind} '{identifier}'")


def not_seeded() -> APIError:
    return APIError(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "not_seeded",
        "No demo data. Run `make seed` (needs `make data` and `make pipeline`).",
    )


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def _api_error(_: Request, exc: APIError) -> JSONResponse:
        body = ErrorResponse(error=ErrorBody(code=exc.code, message=exc.message))
        return JSONResponse(body.model_dump(exclude_none=True), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [
            {"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")}
            for e in exc.errors()
        ]
        body = ErrorResponse(
            error=ErrorBody(code="validation_error", message="Invalid request", details=details)
        )
        return JSONResponse(jsonable_encoder(body), status_code=422)
