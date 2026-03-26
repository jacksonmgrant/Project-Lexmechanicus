from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from .routers import ask, auth, search, uploads, viewer


app = FastAPI(title="Lexmechanicus")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
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
