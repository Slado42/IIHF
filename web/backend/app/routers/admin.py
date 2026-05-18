from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db, SessionLocal
from ..models import User, Match
from ..auth import get_current_user
from . import scores

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/scrape-players")
def scrape_players(current_user: User = Depends(get_current_user)):
    """Trigger a fresh scrape of IIHF team rosters into the players table."""
    from scraper_bridge import import_players_to_db
    import_players_to_db()
    return {"status": "ok", "message": "Player scrape completed"}


@router.post("/reimport-all-stats")
def reimport_all_stats(current_user: User = Depends(get_current_user)):
    """
    Re-import stats for every match whose start time is in the past,
    regardless of current status. Also recalculates all day scores.
    Use this to rebuild player_stats and user_day_scores from scratch.
    """
    from scraper_bridge import import_match_stats_to_db

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db = SessionLocal()
    try:
        finished = (
            db.query(Match)
            .filter(Match.match_time <= now)
            .order_by(Match.id)
            .all()
        )
        match_ids = [(m.id, m.day) for m in finished]
    finally:
        db.close()

    results = []
    for match_id, day in match_ids:
        try:
            import_match_stats_to_db(match_id)
            results.append({"match_id": match_id, "day": day, "status": "ok"})
        except Exception as e:
            results.append({"match_id": match_id, "day": day, "status": "error", "error": str(e)})

    db = SessionLocal()
    try:
        all_days = sorted({r["day"] for r in results if r["status"] == "ok"})
        for day in all_days:
            scores._calculate_day_scores(day, db)
    finally:
        db.close()

    return {"status": "ok", "matches": results, "days_rescored": all_days}
