from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .db import DATABASE_URL
from .errors import http_exception_handler, request_validation_exception_handler, unhandled_exception_handler
from .routers import ask, auth, search, uploads, viewer


def _run_startup_migrations():
    server_dir = Path(__file__).resolve().parents[1]
    alembic_cfg = Config(str(server_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(server_dir / "alembic"))
    if DATABASE_URL:
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(_: FastAPI):
    await asyncio.to_thread(_run_startup_migrations)
    yield


app = FastAPI(title="Lexmechanicus", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, request_validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
app.include_router(auth.router)
app.include_router(ask.router)
app.include_router(search.router)
app.include_router(uploads.router)
app.include_router(viewer.router)


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/robots.txt")
async def robots():
    return PlainTextResponse("User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")
