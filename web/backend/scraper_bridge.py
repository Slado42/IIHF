"""
Bridge between the existing IIHF scraper scripts and the web app database.

Usage (CLI):
    python scraper_bridge.py players      # import players into DB
    python scraper_bridge.py matches      # import match schedule into DB
    python scraper_bridge.py stats <match_id>  # import stats for a match
"""
import sys
import os
from pathlib import Path
from datetime import datetime, timezone

# Add the root IIHF directory to sys.path so scraper modules are importable
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import Player, Match, PlayerStat


def import_players_to_db():
    """Scrape team rosters and write to the players table."""
    from lineups_scraper import scrape_and_process
    import pandas as pd

    df = scrape_and_process()  # returns DataFrame with name/position/country/team_abbr
    db = SessionLocal()
    try:
        year = datetime.now().year
        for _, row in df.iterrows():
            existing = (
                db.query(Player)
                .filter(
                    Player.name == row["name"],
                    Player.team_abbr == row["team_abbr"],
                    Player.championship_year == year,
                )
                .first()
            )
            if not existing:
                # Map IIHF position strings to our canonical values
                pos_map = {
                    "Forward": "Forward",
                    "Defender": "Defender",
                    "Goalkeeper": "Goalkeeper",
                    "Goalie": "Goalkeeper",
                    "Defence": "Defender",
                    "Defenceman": "Defender",
                }
                position = pos_map.get(row.get("position", "Forward"), "Forward")
                db.add(Player(
                    name=row["name"],
                    position=position,
                    team_abbr=row["team_abbr"],
                    championship_year=year,
                ))
        db.commit()
        print(f"Imported {len(df)} players into database")
    finally:
        db.close()


def import_matches_to_db():
    """Scrape the championship schedule and write to the matches table."""
    import pandas as pd
    import subprocess
    import importlib.util
    import os

    # Run url_scraper to generate match_urls.csv
    spec = importlib.util.spec_from_file_location("url_scraper", ROOT / "url_scraper.py")
    # Just import the CSV that url_scraper generates
    csv_path = ROOT / "match_urls.csv"
    if not csv_path.exists():
        print("match_urls.csv not found — run url_scraper.py first")
        return

    df = pd.read_csv(csv_path)
    db = SessionLocal()
    try:
        year = datetime.now().year
        for _, row in df.iterrows():
            existing = db.query(Match).filter(
                Match.home_team == row["home_team"],
                Match.away_team == row["away_team"],
                Match.day == row["Day"],
            ).first()
            if not existing:
                # Parse date and time
                try:
                    match_dt = datetime.strptime(
                        f"{row['date']} {row['time']} {year}", "%d %b %H:%M %Y"
                    )
                except Exception:
                    match_dt = datetime.now()
                db.add(Match(
                    day=int(row["Day"]),
                    date=match_dt.date(),
                    match_time=match_dt,
                    home_team=row["home_team"],
                    away_team=row["away_team"],
                    status="upcoming",
                    url_playbyplay=row.get("url_playbyplay"),
                    url_statistics=row.get("url_statistics"),
                ))
        db.commit()
        print(f"Imported {len(df)} matches into database")
    finally:
        db.close()


def import_match_stats_to_db(match_id: int):
    """Scrape stats for a completed match and write to player_stats table."""
    from match_stats_scraper import extract_all_stats

    db = SessionLocal()
    try:
        match = db.query(Match).filter(Match.id == match_id).first()
        if not match:
            print(f"Match {match_id} not found")
            return
        if not match.url_statistics:
            print(f"Match {match_id} has no statistics URL")
            return

        df = extract_all_stats(match.url_playbyplay, match.url_statistics)
        year = datetime.now().year

        for _, row in df.iterrows():
            player = (
                db.query(Player)
                .filter(
                    Player.name == row["Player"],
                    Player.championship_year == year,
                )
                .first()
            )
            if not player:
                continue

            existing = (
                db.query(PlayerStat)
                .filter(PlayerStat.player_id == player.id, PlayerStat.match_id == match.id)
                .first()
            )
            win = bool(row.get("Win", 0))
            if existing:
                existing.goals = int(row.get("Goals", 0))
                existing.assists = int(row.get("Assists", 0))
                existing.ppg = int(row.get("Power Play Goal", 0))
                existing.shg = int(row.get("Shorthanded Goal", 0))
                existing.gwg = int(row.get("Game Winning Goal", 0))
                existing.pim = int(row.get("Penalty Minutes", 0))
                existing.plus_minus = int(row.get("Plus Minus", 0))
                existing.saves = int(row.get("Saves", 0))
                existing.goals_against = int(row.get("Goals Against", 0))
                existing.win = win
            else:
                db.add(PlayerStat(
                    player_id=player.id,
                    match_id=match.id,
                    goals=int(row.get("Goals", 0)),
                    assists=int(row.get("Assists", 0)),
                    ppg=int(row.get("Power Play Goal", 0)),
                    shg=int(row.get("Shorthanded Goal", 0)),
                    gwg=int(row.get("Game Winning Goal", 0)),
                    pim=int(row.get("Penalty Minutes", 0)),
                    plus_minus=int(row.get("Plus Minus", 0)),
                    saves=int(row.get("Saves", 0)),
                    goals_against=int(row.get("Goals Against", 0)),
                    win=win,
                ))

        match.status = "completed"
        db.commit()
        print(f"Imported stats for match {match_id}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scraper_bridge.py [players|matches|stats <match_id>]")
        sys.exit(1)

    command = sys.argv[1]
    if command == "players":
        import_players_to_db()
    elif command == "matches":
        import_matches_to_db()
    elif command == "stats" and len(sys.argv) >= 3:
        import_match_stats_to_db(int(sys.argv[2]))
    else:
        print("Unknown command")
        sys.exit(1)
