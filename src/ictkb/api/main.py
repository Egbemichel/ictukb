"""FastAPI application. Run with: uvicorn ictkb.api.main:app"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .. import __version__
from ..config import get_settings
from ..db import close_pool, open_pool
from .routers import admin, documents, feedback, health, search


@asynccontextmanager
async def lifespan(_: FastAPI):
    open_pool()
    yield
    close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ICT University Knowledge Base API",
        version=__version__,
        description="Retrieval API used by student chatbots. Content is read-only through this API.",
        lifespan=lifespan,
    )
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["X-API-Key", "X-Admin-Token", "Content-Type"],
    )
    for module in (health, search, documents, feedback, admin):
        app.include_router(module.router)
    return app


app = create_app()
