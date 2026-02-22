"""
Tests for score calculation and standings.

Endpoints:
  POST /scores/calculate?day=N  - compute & persist points for all users on day N
  GET  /scores/standings         - return all users sorted by cumulative total
  GET  /scores/me                - return current user's day scores

Scoring chain:
  1. Create Player, Match, PlayerStat rows in the test DB
  2. Save a DailyLineup for test_user
  3. Call /scores/calculate?day=N
  4. Assert /scores/me or /scores/standings match expected values
"""

import pytest
from datetime import datetime, date, timezone
from app.models import Player, Match, PlayerStat, DailyLineup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_player(db, position="Forward", team="TST"):
    p = Player(name=f"P-{position[:1]}", position=position, team_abbr=team, championship_year=2026)
    db.add(p)
    db.flush()
    return p


def _insert_match(db, day=1):
    m = Match(
        day=day,
        date=date(2026, 2, 22),
        match_time=datetime(2026, 2, 22, 15, 0),
        home_team="TST",
        away_team="OPP",
        status="completed",
    )
    db.add(m)
    db.flush()
    return m


def _insert_stat(db, player_id, match_id, **kwargs):
    stat = PlayerStat(
        player_id=player_id,
        match_id=match_id,
        goals=kwargs.get("goals", 0),
        assists=kwargs.get("assists", 0),
        ppg=kwargs.get("ppg", 0),
        shg=kwargs.get("shg", 0),
        gwg=kwargs.get("gwg", 0),
        win=kwargs.get("win", False),
        saves=kwargs.get("saves", 0),
        goals_against=kwargs.get("goals_against", 0),
    )
    db.add(stat)
    db.flush()
    return stat


def _insert_lineup(db, user_id, player_list, captain_player_id, day=1):
    """
    player_list: list of Player ORM objects.
    Creates DailyLineup rows for each.
    """
    for player in player_list:
        db.add(DailyLineup(
            user_id=user_id,
            day=day,
            player_id=player.id,
            is_captain=(player.id == captain_player_id),
            locked=False,
        ))
    db.commit()


def _get_user_id(client, auth_headers):
    resp = client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    return resp.json()["id"]


def _seed_full_lineup(db, user_id, day=1):
    """
    Insert 3F+2D+1G players plus a match, and return the list of players.
    Captain is the first forward.
    """
    players = [
        _insert_player(db, "Forward"),
        _insert_player(db, "Forward"),
        _insert_player(db, "Forward"),
        _insert_player(db, "Defender"),
        _insert_player(db, "Defender"),
        _insert_player(db, "Goalkeeper"),
    ]
    db.commit()
    return players


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCalculateScores:
    def test_calculate_scores(self, client, auth_headers, db):
        """
        Insert player_stats, calculate scores for a day, verify user_day_scores.
        """
        user_id = _get_user_id(client, auth_headers)

        players = _seed_full_lineup(db, user_id)
        match = _insert_match(db, day=1)
        db.commit()

        # Forward pf0 scores 1 goal (3 pts).  He is captain -> 6 pts total.
        _insert_stat(db, players[0].id, match.id, goals=1)
        db.commit()

        _insert_lineup(db, user_id, players, captain_player_id=players[0].id, day=1)

        calc_resp = client.post("/scores/calculate?day=1")
        assert calc_resp.status_code == 200

        # GET /scores/me returns a list of day-scores
        score_resp = client.get("/scores/me", headers=auth_headers)
        assert score_resp.status_code == 200
        day_scores = score_resp.json()
        assert len(day_scores) >= 1

        day1 = next((d for d in day_scores if d["day"] == 1), None)
        assert day1 is not None
        # Captain (goals=1 -> 3pts) * 2 = 6; everyone else 0
        assert day1["total_points"] == pytest.approx(6.0, abs=1e-6)

    def test_captain_multiplier_applied(self, client, auth_headers, db):
        """Captain's points are doubled in the final score."""
        user_id = _get_user_id(client, auth_headers)

        players = _seed_full_lineup(db, user_id)
        match = _insert_match(db, day=2)
        db.commit()

        # Second forward scores 1 assist (2 pts), is captain -> 4 pts
        _insert_stat(db, players[1].id, match.id, assists=1)
        db.commit()

        _insert_lineup(db, user_id, players, captain_player_id=players[1].id, day=2)

        client.post("/scores/calculate?day=2")

        score_resp = client.get("/scores/me", headers=auth_headers)
        assert score_resp.status_code == 200
        day2 = next((d for d in score_resp.json() if d["day"] == 2), None)
        assert day2 is not None
        assert day2["total_points"] == pytest.approx(4.0, abs=1e-6)


class TestStandings:
    def test_standings(self, client, auth_headers, db):
        """
        After calculating scores, GET /scores/standings returns a sorted list.
        """
        user_id = _get_user_id(client, auth_headers)

        players = _seed_full_lineup(db, user_id)
        match = _insert_match(db, day=3)
        db.commit()

        # Captain: 2 goals (6 pts) -> 12 pts with captain multiplier
        _insert_stat(db, players[0].id, match.id, goals=2)
        db.commit()

        _insert_lineup(db, user_id, players, captain_player_id=players[0].id, day=3)
        client.post("/scores/calculate?day=3")

        standings_resp = client.get("/scores/standings")
        assert standings_resp.status_code == 200
        standings = standings_resp.json()

        assert isinstance(standings, list)
        assert len(standings) >= 1

        # Verify sorted descending by total_points
        totals = [entry["total_points"] for entry in standings]
        assert totals == sorted(totals, reverse=True)

        # Our test user must appear
        usernames = [entry["username"] for entry in standings]
        assert "testuser" in usernames
