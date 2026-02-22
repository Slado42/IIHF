from datetime import datetime, date
from pydantic import BaseModel, EmailStr, ConfigDict


# ── Auth ─────────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    username: str
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str
    email: str
    created_at: datetime


# ── Players ──────────────────────────────────────────────────────────────────

class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    position: str
    team_abbr: str
    championship_year: int


# ── Matches ──────────────────────────────────────────────────────────────────

class MatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    day: int
    date: date
    match_time: datetime
    home_team: str
    away_team: str
    status: str


# ── Lineup ───────────────────────────────────────────────────────────────────

class LineupPlayerIn(BaseModel):
    player_id: int
    is_captain: bool = False

class LineupSaveRequest(BaseModel):
    day: int
    players: list[LineupPlayerIn]

class LineupEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    player_id: int
    is_captain: bool
    locked: bool
    player: PlayerOut

class LineupResponse(BaseModel):
    day: int
    lineup: list[LineupEntryOut]


# ── Scores ───────────────────────────────────────────────────────────────────

class PlayerScoreDetail(BaseModel):
    player_id: int
    name: str
    team_abbr: str
    position: str
    is_captain: bool
    fantasy_points: float

class UserDayScoreOut(BaseModel):
    day: int
    total_points: float
    players: list[PlayerScoreDetail]

class StandingEntry(BaseModel):
    rank: int
    username: str
    user_id: str
    total_points: float
    scores_by_day: dict[int, float]
