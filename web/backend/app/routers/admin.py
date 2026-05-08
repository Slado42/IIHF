from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import User
from ..auth import get_current_user

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/scrape-players")
def scrape_players(current_user: User = Depends(get_current_user)):
    """Trigger a fresh scrape of IIHF team rosters into the players table."""
    from scraper_bridge import import_players_to_db
    import_players_to_db()
    return {"status": "ok", "message": "Player scrape completed"}
