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


async def _auto_score_loop():
    """Hourly background task: scrape stats and recalculate scores for matches 5+ hours old."""
    while True:
        try:
            from scraper_bridge import import_match_stats_to_db
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            cutoff = now - timedelta(hours=5)

            # Phase 1: get unprocessed match IDs in a short-lived session
            db = SessionLocal()
            try:
                unprocessed = (
                    db.query(Match)
                    .filter(
                        Match.match_time <= cutoff,
                        Match.status != "completed",
                        Match.url_playbyplay.isnot(None),
                        Match.url_statistics.isnot(None),
                    )
                    .all()
                )
                match_ids = [(m.id, m.day) for m in unprocessed]
            finally:
                db.close()

            # Phase 2: scrape each match (no DB connection held during Playwright)
            for match_id, match_day in match_ids:
                try:
                    print(f"[auto-score] Scraping stats for match {match_id} (day {match_day})", flush=True)
                    await asyncio.to_thread(import_match_stats_to_db, match_id)
                except Exception as e:
                    print(f"[auto-score] Failed to scrape match {match_id}: {e}", flush=True)
                if len(match_ids) > 1:
                    await asyncio.sleep(45)

            # Phase 3: recalculate scores in a fresh session
            db = SessionLocal()
            try:
                days = {
                    m.day
                    for m in db.query(Match).filter(Match.match_time <= cutoff).all()
                }
                for day in sorted(days):
                    scores._calculate_day_scores(day, db)
                    print(f"[auto-score] Recalculated scores for day {day}", flush=True)
            except Exception as e:
                print(f"[auto-score] Error in score calculation: {e}", flush=True)
            finally:
                db.close()

        except Exception as e:
            print(f"[auto-score] Unexpected error: {e}", flush=True)
        await asyncio.sleep(3600)  # run every hour


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
    asyncio.create_task(_auto_score_loop())
    asyncio.create_task(_auto_lineup_loop())


@app.get("/health")
def health():
    return {"status": "ok"}
