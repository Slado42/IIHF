import uuid
from datetime import datetime, date
from sqlalchemy import (
    String, Integer, Float, Boolean, Date, DateTime,
    ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    lineups: Mapped[list["DailyLineup"]] = relationship(back_populates="user")
    day_scores: Mapped[list["UserDayScore"]] = relationship(back_populates="user")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    position: Mapped[str] = mapped_column(String, nullable=False)  # Forward/Defender/Goalkeeper
    team_abbr: Mapped[str] = mapped_column(String, nullable=False)
    championship_year: Mapped[int] = mapped_column(Integer, nullable=False)

    stats: Mapped[list["PlayerStat"]] = relationship(back_populates="player")
    lineups: Mapped[list["DailyLineup"]] = relationship(back_populates="player")


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    match_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC
    home_team: Mapped[str] = mapped_column(String, nullable=False)
    away_team: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="upcoming")  # upcoming/live/completed
    url_playbyplay: Mapped[str | None] = mapped_column(String)
    url_statistics: Mapped[str | None] = mapped_column(String)

    player_stats: Mapped[list["PlayerStat"]] = relationship(back_populates="match")


class PlayerStat(Base):
    __tablename__ = "player_stats"
    __table_args__ = (UniqueConstraint("player_id", "match_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    match_id: Mapped[int] = mapped_column(Integer, ForeignKey("matches.id"), nullable=False)
    goals: Mapped[int] = mapped_column(Integer, default=0)
    assists: Mapped[int] = mapped_column(Integer, default=0)
    ppg: Mapped[int] = mapped_column(Integer, default=0)
    shg: Mapped[int] = mapped_column(Integer, default=0)
    gwg: Mapped[int] = mapped_column(Integer, default=0)
    pim: Mapped[int] = mapped_column(Integer, default=0)
    plus_minus: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    goals_against: Mapped[int] = mapped_column(Integer, default=0)
    win: Mapped[bool] = mapped_column(Boolean, default=False)
    fantasy_points: Mapped[float] = mapped_column(Float, default=0.0)

    player: Mapped["Player"] = relationship(back_populates="stats")
    match: Mapped["Match"] = relationship(back_populates="player_stats")


class DailyLineup(Base):
    __tablename__ = "daily_lineups"
    __table_args__ = (UniqueConstraint("user_id", "day", "player_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    player_id: Mapped[int] = mapped_column(Integer, ForeignKey("players.id"), nullable=False)
    is_captain: Mapped[bool] = mapped_column(Boolean, default=False)
    locked: Mapped[bool] = mapped_column(Boolean, default=False)

    user: Mapped["User"] = relationship(back_populates="lineups")
    player: Mapped["Player"] = relationship(back_populates="lineups")


class UserDayScore(Base):
    __tablename__ = "user_day_scores"
    __table_args__ = (UniqueConstraint("user_id", "day"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id"), nullable=False)
    day: Mapped[int] = mapped_column(Integer, nullable=False)
    total_points: Mapped[float] = mapped_column(Float, default=0.0)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime)

    user: Mapped["User"] = relationship(back_populates="day_scores")
