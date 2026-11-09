from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import system, videos
from app.core.config import get_settings
from app.core.errors import VidAskError
from app.core.logging import configure_logging, get_logger
from app.services.container import get_store
from app.services.jobs import get_queue

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level, settings.log_json)
    store = get_store()
    if get_queue().backend == "thread":
        # In-process jobs cannot survive a restart; don't leave them "processing" forever.
        stale = store.fail_stale_jobs()
        if stale:
            log.warning("startup.stale_jobs_failed", count=stale)
    log.info(
        "startup",
        llm=f"{settings.llm_provider}:{settings.llm_model}",
        embedding=settings.embedding_model,
        data_dir=str(settings.data_dir),
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="VidAsk API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(VidAskError)
    async def _vidask_error(_: Request, exc: VidAskError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    app.include_router(videos.router)
    app.include_router(system.router)
    return app


app = create_app()
