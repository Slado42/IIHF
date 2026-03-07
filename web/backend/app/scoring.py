import math
from .models import PlayerStat

SCORING: dict[str, dict[str, float]] = {
    "Forward": {
        "goal": 3.0,
        "assist": 2.0,
        "ppg": 1.0,       # bonus on top of goal value
        "shg": 3.0,       # bonus on top of goal value
        "gwg": 1.0,       # bonus on top of goal value
        "plus_minus": 1.0,
        "pim": -0.5,
        # no win bonus for skaters
    },
    "Defender": {
        "goal": 4.0,
        "assist": 3.0,
        "ppg": 1.0,
        "shg": 3.0,
        "gwg": 1.0,
        "plus_minus": 1.0,
        "pim": -0.5,
        # no win bonus for skaters
    },
    "Goalkeeper": {
        "win": 3.0,
        "save": 0.2,           # applied via math.floor(saves * 0.2)
        "goals_against": -1.0,
        "shutout": 3.0,        # win=True AND goals_against==0
        "goal": 5.0,
        "assist": 4.0,
        "ppg": 1.0,            # bonus on top of goal value
        "shg": 3.0,            # bonus on top of goal value
        "gwg": 1.0,            # bonus on top of goal value
        "plus_minus": 1.0,
        "pim": -0.5,
    },
}

CAPTAIN_MULTIPLIER = 2.0


def calculate_player_points(stat: PlayerStat, position: str, is_captain: bool) -> float:
    """
    Calculate fantasy points for a player based on their match stats.

    Args:
        stat: PlayerStat ORM object (or any object with the same numeric attributes)
        position: "Forward", "Defender", or "Goalkeeper"
        is_captain: whether this player is the user's captain

    Returns:
        Fantasy points as a float
    """
    rules = SCORING.get(position, {})
    points = 0.0

    if position in ("Forward", "Defender"):
        points += stat.goals * rules["goal"]
        points += stat.assists * rules["assist"]
        points += stat.ppg * rules["ppg"]
        points += stat.shg * rules["shg"]
        points += stat.gwg * rules["gwg"]
        points += stat.plus_minus * rules["plus_minus"]
        points += stat.pim * rules["pim"]

    elif position == "Goalkeeper":
        if stat.win:
            points += rules["win"]
        points += math.floor(stat.saves * rules["save"])  # saves rounded down
        points += stat.goals_against * rules["goals_against"]
        if stat.win and stat.goals_against == 0:           # shutout bonus
            points += rules["shutout"]
        points += stat.goals * rules["goal"]
        points += stat.assists * rules["assist"]
        points += stat.ppg * rules["ppg"]
        points += stat.shg * rules["shg"]
        points += stat.gwg * rules["gwg"]
        points += stat.plus_minus * rules["plus_minus"]
        points += stat.pim * rules["pim"]

    if is_captain:
        points *= CAPTAIN_MULTIPLIER

    return round(points, 2)
