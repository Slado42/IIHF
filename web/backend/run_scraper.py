"""
Local scraper script — run this on your machine to import match stats into Supabase.

Usage:
    DATABASE_URL="postgresql://..." python run_scraper.py           # all unprocessed completed matches
    DATABASE_URL="postgresql://..." python run_scraper.py --day 3   # specific day
    DATABASE_URL="postgresql://..." python run_scraper.py --all     # reimport every completed match
    DATABASE_URL="postgresql://..." python run_scraper.py --match 37  # single match
"""
import sys
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import SessionLocal
from app.models import Match
from app.routers.scores import _calculate_day_scores
from scraper_bridge import import_match_stats_to_db


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--day", type=int, help="Scrape all matches for a specific day")
    group.add_argument("--all", action="store_true", help="Reimport every completed match")
    group.add_argument("--match", type=int, help="Scrape a single match by ID")
    args = parser.parse_args()

    db = SessionLocal()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cutoff = now - timedelta(hours=3)

    try:
        if args.match:
            matches = db.query(Match).filter(Match.id == args.match).all()
        elif args.day:
            matches = db.query(Match).filter(Match.day == args.day, Match.match_time <= now).all()
        elif args.all:
            matches = db.query(Match).filter(Match.match_time <= now).order_by(Match.id).all()
        else:
            matches = (
                db.query(Match)
                .filter(Match.match_time <= cutoff, Match.status != "completed")
                .order_by(Match.id)
                .all()
            )
        match_ids = [(m.id, m.day) for m in matches]
    finally:
        db.close()

    if not match_ids:
        print("No matches to process.")
        return

    print(f"Processing {len(match_ids)} match(es)...")
    results = []
    for match_id, day in match_ids:
        print(f"\n--- Match {match_id} (day {day}) ---")
        try:
            import_match_stats_to_db(match_id)
            results.append((match_id, day, "ok"))
        except Exception as e:
            print(f"  ERROR: {e}")
            results.append((match_id, day, f"error: {e}"))

    days_to_rescore = sorted({day for _, day, status in results if status == "ok"})
    if days_to_rescore:
        print(f"\nRecalculating scores for days: {days_to_rescore}")
        db = SessionLocal()
        try:
            for day in days_to_rescore:
                _calculate_day_scores(day, db)
                print(f"  Day {day} rescored.")
        finally:
            db.close()

    print("\n=== Summary ===")
    for match_id, day, status in results:
        print(f"  Match {match_id} day {day}: {status}")


if __name__ == "__main__":
    main()
