"""FastAPI analytics server for the CodeDrift dashboard."""

import time
from pathlib import Path
from typing import Optional

from .db import CodeDriftDB
from . import analytics

_db_path: Optional[Path] = None


def init_api(db_path: Path) -> None:
    global _db_path
    _db_path = db_path


def _get_db() -> CodeDriftDB:
    if _db_path is None:
        raise RuntimeError("API not initialised — call init_api() first")
    return CodeDriftDB(_db_path).connect()


def _make_app():
    try:
        from fastapi import FastAPI, Query, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.staticfiles import StaticFiles
    except ImportError as exc:
        raise RuntimeError("Install dashboard support: pip install codedrift[dashboard]") from exc

    app = FastAPI(title="CodeDrift Analytics API", version="1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:8421"],
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    # ── endpoints ─────────────────────────────────────────────────────────────

    @app.get("/api/health")
    def health():
        if _db_path is None:
            raise HTTPException(status_code=503, detail="No DB path configured")
        size = _db_path.stat().st_size if _db_path.exists() else 0
        return {"status": "ok", "db_path": str(_db_path), "db_size_bytes": size}

    @app.get("/api/stats")
    def stats():
        db = _get_db()
        try:
            s = db.stats()
            row = db.execute("SELECT MAX(last_indexed) AS last FROM file_meta")
            last_indexed = row[0]["last"] if row and row[0]["last"] else None
            index_age_hours = round((time.time() - last_indexed) / 3600, 1) if last_indexed else None
            return {
                "files": s["files"],
                "symbols": s["symbols"],
                "languages": s["languages"],
                "last_indexed": last_indexed,
                "index_age_hours": index_age_hours,
            }
        finally:
            db.close()

    @app.get("/api/tools/summary")
    def tools_summary():
        db = _get_db()
        try:
            return analytics.get_tool_summary(db)
        finally:
            db.close()

    @app.get("/api/tools/timeline")
    def tools_timeline(days: int = Query(default=30, ge=1, le=365)):
        db = _get_db()
        try:
            return analytics.get_tool_timeline(db, days)
        finally:
            db.close()

    @app.get("/api/tools/response-size")
    def tools_response_size():
        db = _get_db()
        try:
            return analytics.get_avg_response_size(db)
        finally:
            db.close()

    @app.get("/api/index/history")
    def index_history():
        db = _get_db()
        try:
            return analytics.get_index_history(db)
        finally:
            db.close()

    @app.get("/api/savings")
    def savings():
        db = _get_db()
        try:
            return analytics.get_savings_summary(db)
        finally:
            db.close()

    @app.get("/api/symbols/heatmap")
    def symbols_heatmap(limit: int = Query(default=20, ge=1, le=100)):
        db = _get_db()
        try:
            return analytics.get_symbol_heatmap(db, limit)
        finally:
            db.close()

    @app.get("/api/memory/hit-rate")
    def memory_hit_rate():
        db = _get_db()
        try:
            return analytics.get_memory_hit_rate(db)
        finally:
            db.close()

    # ── serve built dashboard in production ───────────────────────────────────
    _dist = Path(__file__).parent.parent / "dashboard" / "dist"
    if _dist.exists():
        app.mount("/", StaticFiles(directory=str(_dist), html=True), name="static")

    return app


app = _make_app()
