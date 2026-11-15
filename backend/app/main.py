"""API lifecycle and process health; no external service readiness claimed yet."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from app.auth_api import router as auth_router
from app.authorization import router as authorization_router
from app.database import Database
from app.errors import ErrorResponse, install_errors
from app.jobs_api import router as jobs_router
from app.settings import Settings, load_settings

logger = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["alive", "ready", "not_ready"]
    mode: Literal["PAPER"] = "PAPER"
    scope: Literal["process"] = "process"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.ready = False
    logger.info("backend_starting mode=PAPER")
    database = Database(application.state.settings)
    application.state.database = database
    try:
        # Engine is lazy: no connectivity claim until a real dependency check exists.
        application.state.ready = True
        logger.info("backend_ready mode=PAPER scope=process")
        yield
    finally:
        application.state.ready = False
        database.close()
        logger.info("backend_stopped mode=PAPER")


def create_app(settings: Settings | None = None) -> FastAPI:
    validated_settings = settings if settings is not None else load_settings()
    application = FastAPI(
        title="TRADING-AI",
        version="0.1.0",
        description="PAPER development only. Health readiness currently covers process lifecycle.",
        lifespan=lifespan,
        responses={422: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
    )
    application.state.ready = False
    application.state.settings = validated_settings
    install_errors(application)
    application.include_router(auth_router)
    application.include_router(authorization_router)
    application.include_router(jobs_router)

    @application.get("/health/live", response_model=Health, tags=["health"])
    def live() -> Health:
        return Health(status="alive")

    @application.get(
        "/health/ready",
        response_model=Health,
        responses={503: {"model": Health, "description": "Process lifecycle not ready"}},
        tags=["health"],
    )
    def ready(request: Request, response: Response) -> Health:
        if not request.app.state.ready:
            response.status_code = 503
            return Health(status="not_ready")
        return Health(status="ready")

    return application


app = create_app()
