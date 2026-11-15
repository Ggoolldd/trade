"""Request IDs and sanitized canonical errors; no request payloads in logs."""

import logging
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: UUID


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request.state.request_id)
    )
    return JSONResponse(body.model_dump(mode="json"), status_code=status)


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        supplied = Headers(scope=scope).getlist("x-request-id")
        try:
            if len(supplied) != 1 or len(supplied[0]) != 36:
                raise ValueError
            request_id = UUID(supplied[0])
        except ValueError:
            request_id = uuid4()
        scope.setdefault("state", {})["request_id"] = request_id
        response_started = False

        async def send_with_id(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                MutableHeaders(scope=message)["X-Request-ID"] = str(request_id)
                if scope.get("path", "").startswith("/api/v1/"):
                    MutableHeaders(scope=message)["Cache-Control"] = "no-store"
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        except Exception:
            logger.error("request_failed request_id=%s", request_id)
            if response_started:
                raise RuntimeError("response stream failed") from None
            response = error_response(
                Request(scope), 500, "internal_error", "Internal server error"
            )
            await response(scope, receive, send_with_id)


def install_errors(application: FastAPI) -> None:
    application.add_middleware(RequestIdMiddleware)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        # Never expose arbitrary detail strings, which can contain credentials.
        response = error_response(
            request,
            exc.status_code,
            "validation_error" if exc.status_code == 422 else f"http_{exc.status_code}",
            "Request validation failed" if exc.status_code == 422 else "Request rejected",
        )
        for name, value in (exc.headers or {}).items():
            if name.lower() in {"www-authenticate", "retry-after", "allow"}:
                response.headers[name] = value
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(request, 422, "validation_error", "Request validation failed")
