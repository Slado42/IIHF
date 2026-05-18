"""
PDF-based IIHF game stats scraper using stats.iihf.com (no Cloudflare protection).

Replaces the Playwright/iihf.com approach. Fetches the Game Summary PDF
(report type 74) for each match, OCRs it with Tesseract, and parses sections:
  - Goals table  → goals, assists, PPG, SHG, GWG
  - Penalties    → PIM
  - Player stats → full roster + +/-
  - Goalie stats → saves, goals against
"""
import io
import re
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
from config import STATS_BASE_URL


def _ocr_pdf(pdf_bytes: bytes) -> str:
    """Convert PDF pages to images and OCR. Lazy import so startup isn't blocked."""
    from pdf2image import convert_from_bytes
    import pytesseract
    images = convert_from_bytes(pdf_bytes, dpi=200)
    return "\n".join(pytesseract.image_to_string(img) for img in images)


def get_game_pdf_url(home_team: str, away_team: str) -> str:
    """
    Fetch the tournament schedule HTML and return the Game Summary (_74_) PDF URL
    for the game where home_team plays away_team.

    Finds the _74_ href whose position in the raw HTML is closest to the matchup
    string (e.g. "FIN - GER"), avoiding dependency on the page's DOM structure.
    """
    resp = requests.get(f"{STATS_BASE_URL}/index.html", timeout=30)
    resp.raise_for_status()
    html = resp.text

    # Home team is in an align="right" bold cell; away team follows after a "-" cell.
    # Limit span to 150 chars to match within a single row and avoid standings tables.
    matchup_m = re.search(
        rf'align="right"><b>{re.escape(home_team)}</b>&nbsp;</td>.{{0,150}}&nbsp;<b>{re.escape(away_team)}</b>',
        html,
        re.DOTALL,
    )
    if not matchup_m:
        raise ValueError(f"Matchup '{home_team} vs {away_team}' not found in schedule HTML")

    pdf_links = [
        (m.start(), m.group(1))
        for m in re.finditer(r'href="([^"]*_74_[^"]*\.pdf)"', html)
    ]
    if not pdf_links:
        raise ValueError("No _74_ PDF links found in schedule HTML")

    # The PDF link appears after the team names in the same row; take the first one after the match.
    after = [(pos, h) for pos, h in pdf_links if pos > matchup_m.end()]
    if not after:
        raise ValueError(f"No _74_ PDF found after matchup '{home_team} vs {away_team}' in HTML")
    _, href = min(after, key=lambda x: x[0])
    return href if href.startswith("http") else f"{STATS_BASE_URL}/{href.lstrip('/')}"


# ── Score ────────────────────────────────────────────────────────────────────

def _parse_score(text: str) -> tuple[str, str, int, int]:
    """Returns (home_abbr, away_abbr, home_score, away_score)."""
    m = re.search(r"([A-Z]{3})\s*-\s*([A-Z]{3})\s*(\d+)\s*-\s*(\d+)", text)
    if not m:
        raise ValueError("Score pattern not found in PDF OCR text")
    return m.group(1), m.group(2), int(m.group(3)), int(m.group(4))


# ── Roster (jersey map + full player list) ──────────────────────────────────

def _build_jersey_map(text: str, home_team: str = '', away_team: str = '') -> dict[str, dict[int, str]]:
    """
    Parse the Game Statistics section to build a per-team jersey-number → name_raw map.
    Used to resolve scorer/assist jersey numbers from the goals table.

    Returns {team_abbr: {jersey_no: name_raw}}
    """
    jersey_map: dict[str, dict[int, str]] = {}
    current_team: str | None = None
    after_total = False

    for line in text.split("\n"):
        stripped = line.strip()

        # Game Statistics explicit header: "Team : SUI (Red)" — always update.
        explicit_team_m = re.match(r"Team\s*:\s*([A-Z]{3})\s*\(", stripped)
        if explicit_team_m:
            current_team = explicit_team_m.group(1)
            jersey_map.setdefault(current_team, {})
            after_total = False
            continue

        # Goalkeeper Records header: "Team : SUI - Switzerland" — only initialise
        # if we haven't seen a team yet; prevents this line from overriding once
        # Game Statistics player rows have already started under the correct team.
        gk_team_m = re.match(r"Team\s*:\s*([A-Z]{3})", stripped)
        if gk_team_m and current_team is None:
            current_team = gk_team_m.group(1)
            jersey_map.setdefault(current_team, {})
            continue

        if current_team is None:
            continue

        # "Total N" marks end of one team's stats block — used as team boundary
        # when the explicit "Team : XXX (Color)" header is absent or garbled.
        if re.match(r"^Total\s+\d", stripped):
            after_total = True
            continue

        # Player rows: "16 F BARKOV Aleksander", "41D HEINOLA Ville", "12 D — STIPSICZ Bence"
        player_m = re.match(r"^\s*(\d+)\s*([FD]|GK)\s+[—–_\-]?\s*([A-Z]{2,}(?:\s+[A-Z]{2,})*\s+\w+)", line)
        if player_m:
            if after_total and home_team and away_team:
                current_team = away_team if current_team == home_team else home_team
                jersey_map.setdefault(current_team, {})
                after_total = False
            jersey = int(player_m.group(1))
            name_raw = re.sub(r"\s*\+[CA]$", "", player_m.group(3)).strip()
            jersey_map[current_team][jersey] = name_raw

    return jersey_map


def _parse_roster(text: str, home_team: str = '', away_team: str = '') -> list[dict]:
    """
    Returns full list of players: [{name_raw, team, pos, plus_minus}].
    Plus/minus is extracted from the end of each stat line:
      pattern: (+-N) HH:MM HH:MM HH:MM HH:MM N H:MM
    """
    players = []
    current_team: str | None = None
    after_total = False

    for line in text.split("\n"):
        stripped = line.strip()

        # Game Statistics explicit header: "Team : SUI (Red)" — always update.
        explicit_team_m = re.match(r"Team\s*:\s*([A-Z]{3})\s*\(", stripped)
        if explicit_team_m:
            current_team = explicit_team_m.group(1)
            after_total = False
            continue

        # Goalkeeper Records header: "Team : SUI - Switzerland" — only initialise
        # if we haven't seen a team yet.
        gk_team_m = re.match(r"Team\s*:\s*([A-Z]{3})", stripped)
        if gk_team_m and current_team is None:
            current_team = gk_team_m.group(1)
            continue

        if current_team is None:
            continue

        if re.match(r"^Total\s+\d", stripped):
            after_total = True
            continue

        player_m = re.match(r"^\s*(\d+)\s*([FD]|GK)\s+[—–_\-]?\s*([A-Z]{2,}(?:\s+[A-Z]{2,})*\s+\w+)", line)
        if not player_m:
            continue

        if after_total and home_team and away_team:
            current_team = away_team if current_team == home_team else home_team
            after_total = False

        pos_code = player_m.group(2)
        name_raw = re.sub(r"\s*\+[CA]$", "", player_m.group(3)).strip()
        pos_map = {"F": "Forward", "D": "Defender", "GK": "Goalkeeper"}

        # +/- is the value immediately before the TOI columns (HH:MM ... HH:MM N H:MM)
        # Lookbehind (?<![:\d]) prevents matching "32" from the middle of "3:32".
        # Some PDFs have 5 TOI columns (P1 P2 P3 OT TOT) when OT column is shown;
        # others have 4 (P1 P2 P3 TOT). Try 5-column form first, then 4, then 3.
        pm = 0
        pm_m = re.search(
            r"(?<![:\d])(-?\+?\d+)\s+\d+:\d+\s+\d+:\d+\s+\d+:\d+\s+\d+:\d+\s+\d+:\d+\s+\d+\s+\d+:\d+\s*$",
            line.strip(),
        )
        if not pm_m:
            pm_m = re.search(
                r"(?<![:\d])(-?\+?\d+)\s+\d+:\d+\s+\d+:\d+\s+\d+:\d+\s+\d+:\d+\s+\d+\s+\d+:\d+\s*$",
                line.strip(),
            )
        if not pm_m:
            # Truncated row: +/- precedes 3 per-period TOI columns only
            pm_m = re.search(
                r"(?<![:\d])(-?\d+)\s+\d+:\d+\s+\d+:\d+\s+\d+:\d+\s*$",
                line.strip(),
            )
        if pm_m:
            try:
                pm = int(pm_m.group(1).replace("+", ""))
            except ValueError:
                pm = 0

        players.append(
            {
                "name_raw": name_raw,
                "team": current_team,
                "pos": pos_map.get(pos_code, "Forward"),
                "plus_minus": pm,
            }
        )

    return players


# ── Goals ─────────────────────────────────────────────────────────────────────

def _parse_goals(text: str, jersey_map: dict[str, dict[int, str]]) -> list[dict]:
    """
    Parse each goal event. Returns list of:
      {scorer, assist1, assist2, team, is_pp, is_sh, home_score, away_score}

    Scorer and assists are resolved via the jersey map. Falls back to OCR name if
    the jersey number is not found.
    """
    events = []

    # Match blocks: "Goal HH:MM N:N TEAM TYPE ..." up to next Goal/Penalty/GK
    # Use DOTALL so we capture multi-line blocks (wrap-around assistants)
    blocks = re.split(r"(?=Goal\s+\d+:\d+)", text)

    for block in blocks:
        m = re.match(
            r"Goal\s+\d+:\d+\s+(\d+):(\d+)\s+([A-Z]{3})\s+(\w+)\s+"
            r"(\d+)\s+([A-Z][A-Z0-9]+(?:\s+[A-Z])?)\s*\(\d+\)(.*)",
            block,
            re.DOTALL,
        )
        if not m:
            continue

        home_score = int(m.group(1))
        away_score = int(m.group(2))
        team = m.group(3)
        goal_type = m.group(4).upper()
        scorer_jersey = int(m.group(5))
        rest = m.group(7)

        team_map = jersey_map.get(team, {})
        scorer = team_map.get(scorer_jersey, "")

        # Everything before the first "On[Ii]ce" / "Onlce" marker holds assist info.
        pre_onice = re.split(r"On\s*[lI]?\s*[iI]?[cC][eE]", rest, maxsplit=1)[0]

        # Collect jersey+name pairs from the pre-onice section.
        # Format: "86 TERAVAINEN T" or on the next line "16 BARKOV A"
        assist_entries = re.findall(r"(\d+)\s+([A-Z][A-Z]+(?:\s+[A-Z])?)", pre_onice)

        assists = []
        for jersey_str, _ocr_name in assist_entries:
            jersey = int(jersey_str)
            name = team_map.get(jersey, "")
            if name and name not in assists:
                assists.append(name)

        events.append(
            {
                "scorer": scorer,
                "assists": assists,
                "team": team,
                "is_pp": goal_type.startswith("PP"),
                "is_sh": goal_type.startswith("SH"),
                "home_score": home_score,
                "away_score": away_score,
            }
        )

    return events


def _calc_gwg(events: list[dict], home_abbr: str, final_home: int, final_away: int) -> str:
    """
    GWG: the goal that first puts the winning team at loser_final+1.
    Returns the scorer's name_raw or '' if undetermined.
    """
    if final_home == final_away:
        return ""
    home_wins = final_home > final_away
    gwg_threshold = (final_away if home_wins else final_home) + 1
    for ev in events:
        is_home_goal = ev["team"] == home_abbr
        if home_wins != is_home_goal:
            continue  # goal scored by the losing team
        running = ev["home_score"] if home_wins else ev["away_score"]
        if running == gwg_threshold:
            return ev["scorer"]
    return ""


# ── Penalties ─────────────────────────────────────────────────────────────────

def _parse_penalties(text: str, jersey_map: dict[str, dict[int, str]]) -> dict[str, int]:
    """
    Parse penalty lines. Returns {name_raw: total_pim}.
    Uses jersey number for lookup when available.
    """
    pim: dict[str, int] = {}
    for m in re.finditer(
        r"Penalty\s+\d+:\d+\s+\d+:\d+\s+([A-Z]{3})\s+(\d+)\s*min\.\s+(\d+)\s+([A-Z][A-Z]+)",
        text,
    ):
        team = m.group(1)
        minutes = int(m.group(2))
        jersey = int(m.group(3))
        name = jersey_map.get(team, {}).get(jersey, m.group(4).strip())
        pim[name] = pim.get(name, 0) + minutes

    return pim


# ── Goalie records ────────────────────────────────────────────────────────────

def _parse_goalie_records(text: str) -> dict[str, tuple[int, int]]:
    """
    Parse the Goalkeeper Records section.
    Returns {name_raw: (sog, svs)}.
    """
    goalies: dict[str, tuple[int, int]] = {}
    gk_m = re.search(r"Goalkeeper Records(.*?)(?:Game Statistics|$)", text, re.DOTALL)
    if not gk_m:
        return goalies

    section = gk_m.group(1)
    # Each goalie row: "31 ANNUNEN Justus 18 17 60:00"
    for m in re.finditer(r"\d+\s+([A-Z][A-Z]+\s+\w+)\s+(\d+)\s+(\d+)\s+\d+:\d+", section):
        name = m.group(1).strip()
        sog = int(m.group(2))
        svs = int(m.group(3))
        goalies[name] = (sog, svs)

    return goalies


# ── Name normalisation ────────────────────────────────────────────────────────

def _pdf_to_db_name(name_raw: str) -> str:
    """
    PDF names are 'LASTNAME Firstname', matching the DB format exactly.
    Just strip OCR artefacts: captain/alternate markers (+C, +A) and award tags (BP).
    """
    name = re.sub(r"\s*\+[CA]\s*", " ", name_raw)
    name = re.sub(r"\s*\([A-Z]+\)\s*", " ", name)
    return " ".join(name.split())


# ── Main entry point ─────────────────────────────────────────────────────────

def scrape_game_stats(home_team: str, away_team: str) -> pd.DataFrame:
    """
    Fetch and parse the IIHF game summary PDF for home_team vs away_team.

    Returns a DataFrame with the same column structure as the old
    extract_all_stats() / match_stats_scraper output:
      Player, Team, Position, Goals, Assists, Points, Penalty Minutes,
      Plus Minus, Goals Against, Saves, Power Play Goal, Shorthanded Goal,
      Game Winning Goal, Win, Event
    """
    pdf_url = get_game_pdf_url(home_team, away_team)
    print(f"  Fetching PDF: {pdf_url}")
    pdf_resp = requests.get(pdf_url, timeout=60)
    pdf_resp.raise_for_status()

    text = _ocr_pdf(pdf_resp.content)

    # Goals and penalties only appear before the Goalkeeper Records section.
    # Truncating prevents the last goal block from bleeding into Game Statistics
    # and picking up player-stat rows as false assists or penalty entries.
    gk_pos = re.search(r"Goalkeeper Records", text)
    goals_text = text[:gk_pos.start()] if gk_pos else text

    home_abbr, away_abbr, home_score, away_score = _parse_score(text)
    jersey_map = _build_jersey_map(text, home_team, away_team)
    roster = _parse_roster(text, home_team, away_team)
    goal_events = _parse_goals(goals_text, jersey_map)
    penalty_pim = _parse_penalties(goals_text, jersey_map)
    goalie_records = _parse_goalie_records(text)
    gwg_scorer = _calc_gwg(goal_events, home_abbr, home_score, away_score)

    # Aggregate per-player goal stats
    goal_stats: dict[str, dict] = {}
    for ev in goal_events:
        scorer = ev["scorer"]
        if scorer:
            d = goal_stats.setdefault(scorer, {"goals": 0, "ppg": 0, "shg": 0, "assists": 0})
            d["goals"] += 1
            if ev["is_pp"]:
                d["ppg"] += 1
            if ev["is_sh"]:
                d["shg"] += 1
        for a in ev["assists"]:
            if a:
                ad = goal_stats.setdefault(a, {"goals": 0, "ppg": 0, "shg": 0, "assists": 0})
                ad["assists"] += 1

    rows = []
    for p in roster:
        name_raw = p["name_raw"]
        team = p["team"]
        pos = p["pos"]
        win = int(
            (team == home_abbr and home_score > away_score)
            or (team == away_abbr and away_score > home_score)
        )
        g = goal_stats.get(name_raw, {})
        pim = penalty_pim.get(name_raw, 0)
        saves = ga = 0
        if pos == "Goalkeeper" and name_raw in goalie_records:
            sog, svs = goalie_records[name_raw]
            saves, ga = svs, sog - svs

        rows.append(
            {
                "Player": _pdf_to_db_name(name_raw),
                "Team": "home" if team == home_abbr else "away",
                "Position": pos,
                "Goals": g.get("goals", 0),
                "Assists": g.get("assists", 0),
                "Points": g.get("goals", 0) + g.get("assists", 0),
                "Penalty Minutes": pim,
                "Plus Minus": p["plus_minus"],
                "Power Play Goal": g.get("ppg", 0),
                "Shorthanded Goal": g.get("shg", 0),
                "Game Winning Goal": int(bool(gwg_scorer) and name_raw == gwg_scorer),
                "Saves": saves,
                "Goals Against": ga,
                "Win": win,
                "Event": "",
            }
        )

    df = pd.DataFrame(rows)

    # Zero out all stats for backup goalies (0 saves = didn't play)
    gk_zero = (df["Position"] == "Goalkeeper") & (df["Saves"] == 0)
    if gk_zero.any():
        num_cols = df.select_dtypes(include="number").columns
        df.loc[gk_zero, num_cols] = 0
        print("Reset stats for backup goalkeepers with 0 saves to 0")

    print(df)
    return df


if __name__ == "__main__":
    # Quick test: FIN vs GER, Game 1
    df = scrape_game_stats("FIN", "GER")
    print(df.to_string())
