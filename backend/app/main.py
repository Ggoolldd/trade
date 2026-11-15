"""API lifecycle and process health; no external service readiness claimed yet."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Health(BaseModel):
    status: Literal["alive", "ready", "not_ready"]
    mode: Literal["PAPER"] = "PAPER"
    scope: Literal["process"] = "process"


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    application.state.ready = False
    logger.info("backend_starting mode=PAPER")
    try:
        # DB/queue dependencies are introduced by subsequent tasks.
        application.state.ready = True
        logger.info("backend_ready mode=PAPER scope=process")
        yield
    finally:
        application.state.ready = False
        logger.info("backend_stopped mode=PAPER")


def create_app() -> FastAPI:
    application = FastAPI(
        title="TRADING-AI",
        version="0.1.0",
        description="PAPER development only. Health readiness currently covers process lifecycle.",
        lifespan=lifespan,
    )
    application.state.ready = False

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
