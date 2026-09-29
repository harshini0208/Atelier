"""FastAPI entry point: /api, /media, and the built React app (one Cloud Run service)."""
from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import models as m
from .api import router
from .db import engine
from .settings import get_settings
from .storage import content_type, storage

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

app = FastAPI(title="Walk-In Wardrobe", version="0.1.0")
app.include_router(router)

for extra in ("api_stylist", "api_wardrobe", "api_commerce", "api_insights"):
    try:
        mod = __import__(f"wiw.{extra}", fromlist=["router"])
        app.include_router(mod.router)
    except ModuleNotFoundError as e:
        if e.name != f"wiw.{extra}":
            raise


@app.on_event("startup")
def _startup() -> None:
    m.Base.metadata.create_all(engine())


@app.get("/media/{path:path}")
def media(path: str) -> Response:
    data = storage().get(path)
    if data is None:
        raise HTTPException(404, "Not found")
    return Response(data, media_type=content_type(path), headers={"Cache-Control": "public, max-age=3600"})


dist = get_settings().frontend_dist
if dist.exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        f = dist / full_path
        if full_path and f.is_file() and dist.resolve() in f.resolve().parents:
            return FileResponse(f)
        return FileResponse(dist / "index.html")
