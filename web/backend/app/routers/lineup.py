from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from ..database import get_db
from ..models import DailyLineup, Player, Match, User
from ..auth import get_current_user
from ..schemas import LineupSaveRequest, LineupResponse, LineupEntryOut

router = APIRouter(prefix="/lineup", tags=["lineup"])

POSITION_LIMITS = {"Forward": 3, "Defender": 2, "Goalkeeper": 1}


def _check_player_locked(player: Player, db: Session) -> bool:
    """Return True if the player's next match has already started."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for SQLite compat
    match = (
        db.query(Match)
        .filter(
            Match.status != "completed",
            (Match.home_team == player.team_abbr) | (Match.away_team == player.team_abbr),
            Match.match_time <= now,
        )
        .first()
    )
    return match is not None


@router.get("/me", response_model=LineupResponse)
def get_my_lineup(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    day: int = Query(...),
):
    entries = (
        db.query(DailyLineup)
        .options(joinedload(DailyLineup.player))
        .filter(DailyLineup.user_id == current_user.id, DailyLineup.day == day)
        .all()
    )
    return LineupResponse(day=day, lineup=entries)


@router.post("/me", response_model=LineupResponse)
def save_lineup(
    body: LineupSaveRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    if not body.players:
        raise HTTPException(status_code=422, detail="No players submitted")

    # Validate captain count
    captains = [p for p in body.players if p.is_captain]
    if len(captains) != 1:
        raise HTTPException(status_code=422, detail="Exactly one captain must be selected")

    # Fetch player objects and validate positions
    position_counts: dict[str, int] = {}
    player_objects: dict[int, Player] = {}
    for lp in body.players:
        player = db.query(Player).filter(Player.id == lp.player_id).first()
        if not player:
            raise HTTPException(status_code=404, detail=f"Player {lp.player_id} not found")
        player_objects[lp.player_id] = player
        position_counts[player.position] = position_counts.get(player.position, 0) + 1

    for position, limit in POSITION_LIMITS.items():
        if position_counts.get(position, 0) > limit:
            raise HTTPException(
                status_code=422,
                detail=f"Too many {position}s: max {limit}, got {position_counts[position]}",
            )

    # Check lock status and player usage limits
    for lp in body.players:
        player = player_objects[lp.player_id]
        if _check_player_locked(player, db):
            raise HTTPException(
                status_code=422,
                detail=f"Player {player.name}'s match has already started and cannot be added",
            )

        # Determine stage from today's match for this player's team
        today_match = db.query(Match).filter(
            Match.day == body.day,
            (Match.home_team == player.team_abbr) | (Match.away_team == player.team_abbr),
        ).first()
        stage = today_match.stage if today_match else "group"
        usage_limit = 3 if stage == "group" else 1

        # Count prior days this player was used in the same stage (exclude today to allow re-saves)
        prior_uses = (
            db.query(DailyLineup)
            .join(
                Match,
                and_(
                    Match.day == DailyLineup.day,
                    Match.stage == stage,
                    (Match.home_team == player.team_abbr) | (Match.away_team == player.team_abbr),
                ),
            )
            .filter(
                DailyLineup.user_id == current_user.id,
                DailyLineup.player_id == player.id,
                DailyLineup.day != body.day,
            )
            .count()
        )
        if prior_uses >= usage_limit:
            raise HTTPException(
                status_code=422,
                detail=f"{player.name} has already been used {prior_uses}× "
                       f"(limit: {usage_limit} in {stage} stage)",
            )

    # Upsert lineup entries
    for lp in body.players:
        existing = (
            db.query(DailyLineup)
            .filter(
                DailyLineup.user_id == current_user.id,
                DailyLineup.day == body.day,
                DailyLineup.player_id == lp.player_id,
            )
            .first()
        )
        if existing:
            if not existing.locked:
                existing.is_captain = lp.is_captain
        else:
            db.add(DailyLineup(
                user_id=current_user.id,
                day=body.day,
                player_id=lp.player_id,
                is_captain=lp.is_captain,
                locked=False,
            ))

    db.commit()

    entries = (
        db.query(DailyLineup)
        .options(joinedload(DailyLineup.player))
        .filter(DailyLineup.user_id == current_user.id, DailyLineup.day == body.day)
        .all()
    )
    return LineupResponse(day=body.day, lineup=entries)


@router.get("/all", response_model=list[LineupResponse])
def get_all_lineups(
    db: Annotated[Session, Depends(get_db)],
    day: int = Query(...),
):
    from ..models import User as UserModel
    users = db.query(UserModel).all()
    result = []
    for user in users:
        entries = (
            db.query(DailyLineup)
            .options(joinedload(DailyLineup.player))
            .filter(DailyLineup.user_id == user.id, DailyLineup.day == day)
            .all()
        )
        result.append(LineupResponse(day=day, lineup=entries))
    return result
