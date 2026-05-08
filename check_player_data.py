"""
Checks how many players are loaded in the database for the current championship year
and whether the data looks fresh enough for fantasy selection.

Run manually or via scheduled subagent:
    python check_player_data.py
"""
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.append(str(ROOT / "web" / "backend"))

from app.database import SessionLocal
from app.models import Player

MINIMUM_EXPECTED_PLAYERS = 200
CHAMPIONSHIP_YEAR = 2026


def check():
    db = SessionLocal()
    try:
        total = db.query(Player).filter(Player.championship_year == CHAMPIONSHIP_YEAR).count()

        by_team = (
            db.query(Player.team_abbr, Player.position)
            .filter(Player.championship_year == CHAMPIONSHIP_YEAR)
            .all()
        )
        teams = {row.team_abbr for row in by_team}
        positions = {}
        for row in by_team:
            positions[row.position] = positions.get(row.position, 0) + 1

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Player data check for WM {CHAMPIONSHIP_YEAR}")
        print(f"  Total players : {total}")
        print(f"  Teams loaded  : {len(teams)} → {', '.join(sorted(teams)) if teams else 'NONE'}")
        print(f"  By position   : {positions}")

        if total < MINIMUM_EXPECTED_PLAYERS:
            print(f"\n  WARNING: Only {total} players found (expected >= {MINIMUM_EXPECTED_PLAYERS}).")
            print("  Run: python web/backend/scraper_bridge.py players")
            return False

        print(f"\n  OK: Player data looks complete.")
        return True
    finally:
        db.close()


if __name__ == "__main__":
    ok = check()
    sys.exit(0 if ok else 1)
