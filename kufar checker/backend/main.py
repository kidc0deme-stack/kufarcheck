from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from config import settings
from db import Database
from notifier import TelegramNotifier
from parser import KufarParser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

db = Database()
parser = KufarParser()
notifier = TelegramNotifier()

if settings.telegram_bot_token and settings.telegram_chat_id:
    notifier.configure(settings.telegram_bot_token, settings.telegram_chat_id)

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    scheduler.add_job(run_monitoring, "interval", seconds=settings.poll_interval)
    scheduler.start()
    logger.info(f"Monitoring started (poll interval: {settings.poll_interval}s)")
    yield
    scheduler.shutdown()


app = FastAPI(title="Kufar Checker", version="0.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve web UI
STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- Pydantic models ---


class AddFilterRequest(BaseModel):
    city: str
    category: str | None = None
    query: str | None = None


class ToggleFilterRequest(BaseModel):
    active: bool


# --- Routes ---


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cities")
def cities():
    from parser import CITIES
    return {"cities": CITIES}


@app.get("/categories")
def categories():
    from parser import CATEGORIES
    return {"categories": CATEGORIES}


@app.post("/filters")
def add_filter(req: AddFilterRequest):
    fid = db.add_filter(req.city, req.category, req.query)
    logger.info(f"Filter added: id={fid} city={req.city} cat={req.category} q={req.query}")
    return {"id": fid}


@app.get("/filters")
def get_filters():
    filters = db.get_active_filters()
    return [
        {
            "id": f.id,
            "city": f.city,
            "category": f.category,
            "query": f.query,
            "active": f.active,
        }
        for f in filters
    ]


@app.put("/filters/{fid}/toggle")
def toggle_filter(fid: int, req: ToggleFilterRequest):
    db.toggle_filter(fid, req.active)
    return {"ok": True}


@app.delete("/filters/{fid}")
def remove_filter(fid: int):
    db.remove_filter(fid)
    return {"ok": True}


@app.post("/monitor")
def manual_monitor():
    """Trigger immediate monitoring run."""
    return run_monitoring()


async def run_monitoring():
    """Core monitoring loop: scan all filters, notify on new listings."""
    filters = db.get_active_filters()
    if not filters:
        return

    all_new = []

    for f in filters:
        seen = db.get_seen_ids()
        first_run = len(seen) == 0
        new_items = await parser.check_new_listings(
            city=f.city,
            category=f.category,
            query=f.query,
            seen_ids=seen,
        )

        if new_items:
            db.add_seen_many(new_items)
            if not first_run:
                for item in new_items:
                    db.log_notification(item["id"], f.id)
                all_new.extend(new_items)
                logger.info(f"Found {len(new_items)} new listing(s) for filter id={f.id}")
            else:
                logger.info(f"Baseline: {len(new_items)} listings stored for filter id={f.id}")

    if all_new:
        await notifier.send_listings(all_new)


@app.get("/stats")
def stats():
    total_seen = len(db.get_seen_ids())
    filters = db.get_active_filters()
    return {
        "total_listings_seen": total_seen,
        "active_filters": len(filters),
        "filters": [
            {"id": f.id, "city": f.city, "category": f.category, "query": f.query}
            for f in filters
        ],
    }


@app.get("/")
def serve_ui():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=False)
