"""
Tests for lineup management endpoints: POST/GET /lineup/me

Schema (LineupSaveRequest):
  day: int
  players: list[LineupPlayerIn]
    player_id: int
    is_captain: bool

Positions stored in Player model: "Forward", "Defender", "Goalkeeper"
POSITION_LIMITS: Forward=3, Defender=2, Goalkeeper=1
"""

import pytest
from datetime import datetime, timedelta, timezone
from app.models import Player, Match


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _add_players(db, specs):
    """
    Insert Player rows and return their ids.
    specs: list of (position_str,) e.g. [("Forward",), ("Goalkeeper",)]
    """
    ids = []
    for i, (pos,) in enumerate(specs):
        p = Player(
            name=f"Player{i}",
            position=pos,
            team_abbr="TST",
            championship_year=2026,
        )
        db.add(p)
        db.flush()
        ids.append(p.id)
    db.commit()
    return ids


def _standard_lineup(player_ids, captain_index=0):
    """
    Build a valid 3F+2D+1G lineup payload.
    player_ids must have 6 elements: [F, F, F, D, D, G].
    """
    positions = ["Forward", "Forward", "Forward", "Defender", "Defender", "Goalkeeper"]
    return {
        "day": 1,
        "players": [
            {
                "player_id": pid,
                "is_captain": (i == captain_index),
            }
            for i, pid in enumerate(player_ids)
        ],
    }


@pytest.fixture()
def player_ids(db):
    """Insert 6 players (3F+2D+1G) and return their ids."""
    specs = [
        ("Forward",), ("Forward",), ("Forward",),
        ("Defender",), ("Defender",),
        ("Goalkeeper",),
    ]
    return _add_players(db, specs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSaveLineup:
    def test_save_lineup_valid(self, client, auth_headers, player_ids):
        """POST /lineup/me with 3F+2D+1G and exactly 1 captain returns 200."""
        payload = _standard_lineup(player_ids, captain_index=0)
        response = client.post("/lineup/me", json=payload, headers=auth_headers)
        assert response.status_code == 200

    def test_save_lineup_too_many_forwards(self, client, auth_headers, db, player_ids):
        """Submitting 4 forwards in the lineup should return 422."""
        # Replace the Defender (index 3) with an extra Forward
        extra_f = Player(name="ExtraF", position="Forward", team_abbr="TST", championship_year=2026)
        db.add(extra_f)
        db.commit()

        payload = {
            "day": 1,
            "players": [
                {"player_id": player_ids[0], "is_captain": True},
                {"player_id": player_ids[1], "is_captain": False},
                {"player_id": player_ids[2], "is_captain": False},
                {"player_id": extra_f.id, "is_captain": False},    # 4th Forward
                {"player_id": player_ids[4], "is_captain": False},
                {"player_id": player_ids[5], "is_captain": False},
            ],
        }
        response = client.post("/lineup/me", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_save_lineup_no_captain(self, client, auth_headers, player_ids):
        """Valid slot counts but no captain flag set should return 422."""
        payload = {
            "day": 1,
            "players": [
                {"player_id": pid, "is_captain": False}
                for pid in player_ids
            ],
        }
        response = client.post("/lineup/me", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_save_lineup_multiple_captains(self, client, auth_headers, player_ids):
        """Two players with is_captain=True should return 422."""
        payload = {
            "day": 1,
            "players": [
                {"player_id": player_ids[0], "is_captain": True},
                {"player_id": player_ids[1], "is_captain": True},  # 2nd captain
                {"player_id": player_ids[2], "is_captain": False},
                {"player_id": player_ids[3], "is_captain": False},
                {"player_id": player_ids[4], "is_captain": False},
                {"player_id": player_ids[5], "is_captain": False},
            ],
        }
        response = client.post("/lineup/me", json=payload, headers=auth_headers)
        assert response.status_code == 422

    def test_save_lineup_locked_player(self, client, auth_headers, db, player_ids):
        """
        A player whose team's match has already started (match_time in the past,
        status not 'completed') is locked and causes a 422.
        """
        # The locked player uses team_abbr "TST".
        # Insert a match with match_time in the past (status="upcoming" = not completed).
        past_time = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
        from datetime import date
        match = Match(
            day=1,
            date=date(2026, 2, 22),
            match_time=past_time,
            home_team="TST",
            away_team="OPP",
            status="live",
        )
        db.add(match)
        db.commit()

        payload = _standard_lineup(player_ids, captain_index=0)
        response = client.post("/lineup/me", json=payload, headers=auth_headers)
        assert response.status_code == 422


class TestGetLineup:
    def test_get_lineup(self, client, auth_headers, player_ids):
        """After saving, GET /lineup/me?day=N returns the saved lineup."""
        day = 1
        payload = _standard_lineup(player_ids, captain_index=0)

        save_resp = client.post("/lineup/me", json=payload, headers=auth_headers)
        assert save_resp.status_code == 200

        get_resp = client.get(f"/lineup/me?day={day}", headers=auth_headers)
        assert get_resp.status_code == 200
        data = get_resp.json()

        # Expect the same 6 players back
        assert len(data["lineup"]) == 6

        returned_ids = {entry["player_id"] for entry in data["lineup"]}
        assert returned_ids == set(player_ids)

        # Exactly one captain
        captains = [entry for entry in data["lineup"] if entry["is_captain"]]
        assert len(captains) == 1
        assert captains[0]["player_id"] == player_ids[0]
