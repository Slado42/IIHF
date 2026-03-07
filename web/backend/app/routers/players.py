from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Player, Match
from ..schemas import PlayerOut

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def get_players(
    db: Annotated[Session, Depends(get_db)],
    position: str | None = Query(None),
    team: str | None = Query(None),
    day: int | None = Query(None),
):
    query = db.query(Player)
    if position:
        query = query.filter(Player.position == position)
    if team:
        query = query.filter(Player.team_abbr == team)

    locked_teams: set[str] = set()
    if day is not None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for m in db.query(Match).filter(Match.day == day, Match.match_time <= now).all():
            locked_teams.add(m.home_team)
            locked_teams.add(m.away_team)

    result = []
    for p in query.order_by(Player.team_abbr, Player.name).all():
        out = PlayerOut.model_validate(p)
        out.is_locked = p.team_abbr in locked_teams
        result.append(out)
    return result
