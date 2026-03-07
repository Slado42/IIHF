"""
Tests for calculate_player_points() in app.scoring.

Scoring rules (from rules_iihf_fantasy_2026.docx):
  Forward:    goal=3, assist=2, ppg bonus=1, shg bonus=3, gwg bonus=1, plus_minus=face, pim=-0.5
  Defender:   goal=4, assist=3, ppg bonus=1, shg bonus=3, gwg bonus=1, plus_minus=face, pim=-0.5
  Goalkeeper: win=3, save=0.2(floor), ga=-1, shutout=+3(when win&ga==0),
              goal=5, assist=4, ppg bonus=1, shg bonus=3, gwg bonus=1, plus_minus=face, pim=-0.5
  Skaters: no win bonus
  Captain: x2 multiplier on total
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
    stat.plus_minus = kwargs.get("plus_minus", 0)
    stat.pim = kwargs.get("pim", 0)
    return stat


@pytest.mark.parametrize(
    "position, stat_kwargs, is_captain, expected",
    [
        # Forward
        ("Forward", {"goals": 1, "assists": 1}, False, 5.0),      # 3+2
        ("Forward", {"goals": 1, "ppg": 1}, False, 4.0),          # 3+1 ppg bonus
        ("Forward", {"win": True}, False, 0.0),                    # no win bonus for skaters
        ("Forward", {"goals": 1, "shg": 1}, False, 6.0),          # 3+3 shg bonus
        ("Forward", {"goals": 1, "pim": 2}, False, 2.0),          # 3 + 2*(-0.5)
        ("Forward", {"goals": 1, "plus_minus": 2}, False, 5.0),   # 3 + 2*1.0
        # Defender
        ("Defender", {"goals": 1}, False, 4.0),
        ("Defender", {"goals": 1, "assists": 1}, False, 7.0),      # 4+3
        ("Defender", {"goals": 1, "shg": 1}, False, 7.0),          # 4+3 shg bonus
        # Goalkeeper
        ("Goalkeeper", {"win": True, "goals_against": 1}, False, 2.0),  # win(3)+ga(-1)=2, no shutout
        ("Goalkeeper", {"saves": 10, "goals_against": 2}, False, 0.0),  # floor(2.0)-2=0
        ("Goalkeeper", {"saves": 7}, False, 1.0),                  # floor(1.4)=1
        ("Goalkeeper", {"win": True, "saves": 10, "goals_against": 0}, False, 8.0),  # 3+3+floor(2)
        ("Goalkeeper", {"goals": 1, "assists": 1}, False, 9.0),    # 5+4
        ("Goalkeeper", {"goals_against": 2, "plus_minus": -1, "pim": 2}, False, -4.0),  # -2-1-1
        # All zeros
        ("Forward", {}, False, 0.0),
    ],
    ids=[
        "forward_goal_and_assist",
        "forward_ppg_bonus",
        "forward_no_win_bonus",
        "forward_shg_bonus",
        "forward_pim",
        "forward_plus_minus",
        "defender_goal",
        "defender_goal_and_assist",
        "defender_shg_bonus",
        "goalkeeper_win_no_shutout",
        "goalkeeper_saves_and_ga",
        "goalkeeper_saves_floor",
        "goalkeeper_shutout",
        "goalkeeper_goal_and_assist",
        "goalkeeper_pim_and_pm",
        "all_zeros",
    ],
)
def test_calculate_player_points(position, stat_kwargs, is_captain, expected):
    stat = make_stat(**stat_kwargs)
    result = calculate_player_points(stat, position, is_captain)
    assert result == pytest.approx(expected, abs=1e-6)


def test_captain_doubles_points():
    """Forward with is_captain=True, 1 goal: 3 * 2 = 6 pts."""
    stat = make_stat(goals=1)
    result = calculate_player_points(stat, "Forward", True)
    assert result == pytest.approx(6.0, abs=1e-6)


def test_captain_doubles_goalkeeper_shutout():
    """Goalkeeper shutout: win(3)+shutout(3)+floor(20*0.2=4)=10, captain: 10*2=20."""
    stat = make_stat(win=True, saves=20, goals_against=0)
    result = calculate_player_points(stat, "Goalkeeper", True)
    assert result == pytest.approx(20.0, abs=1e-6)


def test_goalkeeper_no_shutout_if_ga():
    """Goalkeeper win with GA > 0: no shutout bonus. win(3)+floor(25*0.2=5)+ga(-1)=7."""
    stat = make_stat(win=True, saves=25, goals_against=1)
    result = calculate_player_points(stat, "Goalkeeper", False)
    assert result == pytest.approx(7.0, abs=1e-6)
