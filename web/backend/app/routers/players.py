from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Player
from ..schemas import PlayerOut

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def get_players(
    db: Annotated[Session, Depends(get_db)],
    position: str | None = Query(None),
    team: str | None = Query(None),
):
    query = db.query(Player)
    if position:
        query = query.filter(Player.position == position)
    if team:
        query = query.filter(Player.team_abbr == team)
    return query.order_by(Player.team_abbr, Player.name).all()
