from .models import PlayerStat

SCORING: dict[str, dict[str, float]] = {
    "Forward": {
        "goal": 3.0,
        "assist": 2.0,
        "ppg": 1.0,
        "shg": 1.0,
        "gwg": 1.0,
        "win": 1.0,
    },
    "Defender": {
        "goal": 4.0,
        "assist": 3.0,
        "ppg": 1.0,
        "shg": 1.0,
        "gwg": 1.0,
        "win": 1.0,
    },
    "Goalkeeper": {
        "win": 3.0,
        "save": 0.2,
        "goals_against": -1.0,
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
        points += stat.goals * rules.get("goal", 0)
        points += stat.assists * rules.get("assist", 0)
        points += stat.ppg * rules.get("ppg", 0)
        points += stat.shg * rules.get("shg", 0)
        points += stat.gwg * rules.get("gwg", 0)
        if stat.win:
            points += rules.get("win", 0)
    elif position == "Goalkeeper":
        if stat.win:
            points += rules.get("win", 0)
        points += stat.saves * rules.get("save", 0)
        points += stat.goals_against * rules.get("goals_against", 0)

    if is_captain:
        points *= CAPTAIN_MULTIPLIER

    return round(points, 2)
