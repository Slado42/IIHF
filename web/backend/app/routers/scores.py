from datetime import datetime, timezone
from typing import Annotated
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import DailyLineup, PlayerStat, UserDayScore, User, Match
from ..auth import get_current_user
from ..scoring import calculate_player_points
from ..schemas import StandingEntry, UserDayScoreOut, PlayerScoreDetail

router = APIRouter(prefix="/scores", tags=["scores"])


def _calculate_day_scores(day: int, db: Session):
    """Core logic: compute & persist fantasy points for all users on a given day."""
    users = db.query(User).all()
    for user in users:
        lineups = (
            db.query(DailyLineup)
            .filter(DailyLineup.user_id == user.id, DailyLineup.day == day)
            .all()
        )
        total = 0.0
        for entry in lineups:
            # Find the match stat for this player on this day
            match_ids = [
                m.id for m in db.query(Match).filter(Match.day == day).all()
            ]
            stat = (
                db.query(PlayerStat)
                .filter(
                    PlayerStat.player_id == entry.player_id,
                    PlayerStat.match_id.in_(match_ids),
                )
                .first()
            )
            if stat:
                pts = calculate_player_points(stat, entry.player.position, entry.is_captain)
                stat.fantasy_points = pts
                total += pts

        # Upsert user_day_scores
        score_row = (
            db.query(UserDayScore)
            .filter(UserDayScore.user_id == user.id, UserDayScore.day == day)
            .first()
        )
        if score_row:
            score_row.total_points = total
            score_row.calculated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        else:
            db.add(UserDayScore(
                user_id=user.id,
                day=day,
                total_points=total,
                calculated_at=datetime.now(timezone.utc).replace(tzinfo=None),
            ))
    db.commit()


@router.post("/calculate")
def calculate_scores(day: int = Query(...), db: Session = Depends(get_db)):
    _calculate_day_scores(day, db)
    return {"status": "calculated", "day": day}


@router.get("/standings", response_model=list[StandingEntry])
def get_standings(db: Annotated[Session, Depends(get_db)]):
    users = db.query(User).all()
    entries = []
    for user in users:
        scores = db.query(UserDayScore).filter(UserDayScore.user_id == user.id).all()
        total = sum(s.total_points for s in scores)
        by_day = {s.day: s.total_points for s in scores}
        entries.append(
            StandingEntry(
                rank=0,
                username=user.username,
                user_id=user.id,
                total_points=total,
                scores_by_day=by_day,
            )
        )
    entries.sort(key=lambda e: e.total_points, reverse=True)
    for i, entry in enumerate(entries):
        entry.rank = i + 1
    return entries


def _build_user_day_scores(user_id: str, db: Session) -> list[UserDayScoreOut]:
    """Build score history for any user — shared by /me and /user/{user_id}."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    day_scores = (
        db.query(UserDayScore)
        .filter(UserDayScore.user_id == user_id)
        .order_by(UserDayScore.day)
        .all()
    )
    result = []
    for ds in day_scores:
        lineups = (
            db.query(DailyLineup)
            .filter(DailyLineup.user_id == user_id, DailyLineup.day == ds.day)
            .all()
        )
        matches = db.query(Match).filter(Match.day == ds.day).all()
        match_ids = [m.id for m in matches]
        started_teams = {
            team
            for m in matches
            if m.match_time <= now
            for team in (m.home_team, m.away_team)
        }
        player_details = []
        for entry in lineups:
            if entry.player.team_abbr not in started_teams:
                continue
            stat = (
                db.query(PlayerStat)
                .filter(
                    PlayerStat.player_id == entry.player_id,
                    PlayerStat.match_id.in_(match_ids),
                )
                .first()
            )
            # Recompute per-user so captain multiplier is applied correctly.
            # stat.fantasy_points is shared across users and reflects the last
            # user processed, so we can't use it for per-player display.
            player_pts = calculate_player_points(stat, entry.player.position, entry.is_captain) if stat else 0.0
            player_details.append(PlayerScoreDetail(
                player_id=entry.player_id,
                name=entry.player.name,
                team_abbr=entry.player.team_abbr,
                position=entry.player.position,
                is_captain=entry.is_captain,
                fantasy_points=player_pts,
                goals=stat.goals if stat else None,
                assists=stat.assists if stat else None,
                ppg=stat.ppg if stat else None,
                shg=stat.shg if stat else None,
                gwg=stat.gwg if stat else None,
                pim=stat.pim if stat else None,
                plus_minus=stat.plus_minus if stat else None,
                saves=stat.saves if stat else None,
                goals_against=stat.goals_against if stat else None,
                win=stat.win if stat else None,
            ))
        result.append(UserDayScoreOut(day=ds.day, total_points=ds.total_points, players=player_details))
    return result


@router.get("/user/{user_id}", response_model=list[UserDayScoreOut])
def get_user_scores(user_id: str, db: Annotated[Session, Depends(get_db)]):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _build_user_day_scores(user_id, db)


@router.get("/me", response_model=list[UserDayScoreOut])
def get_my_scores(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return _build_user_day_scores(current_user.id, db)


@router.get("", response_model=list[StandingEntry])
def get_scores_for_day(day: int = Query(...), db: Session = Depends(get_db)):
    users = db.query(User).all()
    entries = []
    for user in users:
        score = (
            db.query(UserDayScore)
            .filter(UserDayScore.user_id == user.id, UserDayScore.day == day)
            .first()
        )
        total = score.total_points if score else 0.0
        entries.append(
            StandingEntry(
                rank=0,
                username=user.username,
                user_id=user.id,
                total_points=total,
                scores_by_day={day: total},
            )
        )
    entries.sort(key=lambda e: e.total_points, reverse=True)
    for i, entry in enumerate(entries):
        entry.rank = i + 1
    return entries
