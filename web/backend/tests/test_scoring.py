"""
Tests for the calculate_player_points scoring function in app.scoring.

Real signature: calculate_player_points(stat: PlayerStat, position: str, is_captain: bool) -> float

Position values: "Forward", "Defender", "Goalkeeper"

Scoring rules:
  Forward  goal:        3 pts
  Forward  assist:      2 pts
  Forward  ppg bonus:   1 pt
  Forward  win:         1 pt
  Defender goal:        4 pts
  Goalkeeper win:       3 pts
  Goalkeeper save:      0.2 pts
  Goalkeeper GA:       -1 pt
  Captain multiplier:   x2
"""

import pytest
from unittest.mock import MagicMock
from app.scoring import calculate_player_points


def make_stat(**kwargs):
    """Create a mock PlayerStat-like object with numeric defaults."""
    stat = MagicMock()
    stat.goals = kwargs.get("goals", 0)
    stat.assists = kwargs.get("assists", 0)
    stat.ppg = kwargs.get("ppg", 0)
    stat.shg = kwargs.get("shg", 0)
    stat.gwg = kwargs.get("gwg", 0)
    stat.win = kwargs.get("win", False)
    stat.saves = kwargs.get("saves", 0)
    stat.goals_against = kwargs.get("goals_against", 0)
    return stat


# ---------------------------------------------------------------------------
# Parametrised cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "position, stat_kwargs, is_captain, expected",
    [
        # 1. Forward: 1 goal (3) + 1 assist (2) = 5
        ("Forward", {"goals": 1, "assists": 1}, False, 5.0),
        # 2. Forward: 1 PPG goal (3) + ppg bonus (1) = 4
        ("Forward", {"goals": 1, "ppg": 1}, False, 4.0),
        # 3. Forward: team win = 1
        ("Forward", {"win": True}, False, 1.0),
        # 4. Defender: 1 goal = 4
        ("Defender", {"goals": 1}, False, 4.0),
        # 5. Goalkeeper: win = 3
        ("Goalkeeper", {"win": True}, False, 3.0),
        # 6. Goalkeeper: 10 saves (2.0) + 2 GA (-2.0) = 0
        ("Goalkeeper", {"saves": 10, "goals_against": 2}, False, 0.0),
        # 8. All zeros -> 0
        ("Forward", {}, False, 0.0),
    ],
    ids=[
        "forward_goal_and_assist",
        "forward_ppg_bonus",
        "forward_team_win",
        "defender_goal",
        "goalkeeper_win",
        "goalkeeper_saves_and_ga",
        "all_zeros",
    ],
)
def test_calculate_player_points(position, stat_kwargs, is_captain, expected):
    stat = make_stat(**stat_kwargs)
    result = calculate_player_points(stat, position, is_captain)
    assert result == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# Captain multiplier (case 7)
# ---------------------------------------------------------------------------

def test_captain_doubles_points():
    """Forward with is_captain=True, 1 goal: 3 * 2 = 6 pts."""
    stat = make_stat(goals=1)
    result = calculate_player_points(stat, "Forward", True)
    assert result == pytest.approx(6.0, abs=1e-6)
