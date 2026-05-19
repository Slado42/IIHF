import os
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/render/project/src')

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, Base, SessionLocal
from .models import Match
from .routers import auth, players, matches, lineup, scores, admin

# Stats scraping runs locally via run_scraper.py — not on this server.

# Make web/backend/ importable so scraper_bridge can be imported
_backend_dir = str(Path(__file__).resolve().parent.parent)
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

app = FastAPI(title="IIHF Fantasy Hockey API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(players.router)
app.include_router(matches.router)
app.include_router(lineup.router)
app.include_router(scores.router)
app.include_router(admin.router)


async def _auto_lineup_loop():
    """Hourly task: refresh player rosters when a match is starting within 2 hours."""
    last_scraped: datetime | None = None
    while True:
        try:
            db = SessionLocal()
            try:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                next_match = (
                    db.query(Match)
                    .filter(Match.match_time >= now)
                    .order_by(Match.match_time)
                    .first()
                )
            finally:
                db.close()

            should_scrape = (
                next_match is not None
                and next_match.match_time - now <= timedelta(hours=2)
                and (last_scraped is None or now - last_scraped >= timedelta(hours=12))
            )
            if should_scrape:
                print("[auto-lineup] Refreshing player rosters before upcoming match...", flush=True)
                from scraper_bridge import import_players_to_db
                await asyncio.to_thread(import_players_to_db)
                last_scraped = datetime.now(timezone.utc).replace(tzinfo=None)
                print("[auto-lineup] Roster refresh complete.", flush=True)
        except Exception as e:
            print(f"[auto-lineup] Error: {e}", flush=True)
        await asyncio.sleep(3600)


@app.on_event("startup")
async def startup():
    import subprocess
    subprocess.run(
        ['python', '-m', 'playwright', 'install', 'chromium'],
        capture_output=True, check=False
    )
    Base.metadata.create_all(bind=engine)
    asyncio.create_task(_auto_lineup_loop())


@app.get("/health")
def health():
    return {"status": "ok"}
