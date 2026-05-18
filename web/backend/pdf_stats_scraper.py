"""
PDF-based IIHF game stats scraper using stats.iihf.com (no Cloudflare protection).

Replaces the Playwright/iihf.com approach. Fetches the Game Summary PDF
(report type 74) for each match, OCRs it with Tesseract, and parses:
  - Game Statistics section  → G, A, PIM, +/- per player (direct table read)
  - Goals section            → PPG, SHG, GWG (goal type + scorer only)
  - Goalkeeper Records       → saves, goals against
"""
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
    images = convert_from_bytes(pdf_bytes, dpi=300)
    return "\n".join(pytesseract.image_to_string(img) for img in images)


def get_game_pdf_url(home_team: str, away_team: str) -> str:
    """
    Fetch the tournament schedule HTML and return the Game Summary (_74_) PDF URL
    for the game where home_team plays away_team.
    """
    resp = requests.get(f"{STATS_BASE_URL}/index.html", timeout=30)
    resp.raise_for_status()
    html = resp.text

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


# ── Game Statistics section ──────────────────────────────────────────────────

# Player line regex: handles hyphenated names (EKMAN-LARSSON), apostrophes (O'REILLY),
# doubled position codes from OCR (FF→F, DD→D), leading dash/dash noise, and OCR
# noise chars (!, °, %) injected into surnames (e.g. LOHRE!I → LOHREI).
_PLAYER_RE = re.compile(
    r"^\s*(\d+)\s*[—–_\-]?\s*([FD]{1,2}|GK)\s+[—–_\-]?\s*"
    r"([A-Z][A-Z'!°%]*(?:-[A-Z][A-Z'!°%]*)*(?:\s+[A-Z][A-Z'!°%]*(?:-[A-Z][A-Z'!°%]*)*)*\s+\w+)"
)


def _extract_gap_pim(rest: str) -> tuple[int, int, int, int]:
    """
    Extract G, A, P, PIM from the stats area immediately after the player name.

    OCR always merges G A P into the first whitespace-delimited token:
      '112' = 1G 1A 2P,  '000' = 0G 0A 0P,  '0o1%1' = 0G 1A 1P (noise between digits).
    Occasionally OCR splits G from AP ('0 00' = 0G 0A 0P) — handled by collecting
    digits across tokens until we have 3.
    PIM is the first token after the token(s) that provided all 3 GAP digits.
    """
    area = re.sub(r'\s*\+[CA]\b|\s*\([A-Z]+\)', '', rest).lstrip()
    tokens = area.split()

    # Collect digits from the first few tokens (usually just 1 token: e.g. '112' or '01141')
    gap_digits: list[int] = []
    pim_token_idx: int | None = None

    for i, tok in enumerate(tokens[:5]):
        tok_digits = [int(c) for c in re.findall(r'\d', tok[:8])]
        gap_digits.extend(tok_digits)
        if len(gap_digits) >= 3:
            pim_token_idx = i + 1
            break

    if len(gap_digits) < 3 or pim_token_idx is None:
        return 0, 0, 0, 0

    # Find the first ordered triple (d[i], d[j], d[k]) where d[i]+d[j]==d[k].
    # OCR sometimes inserts digit noise into the GAP string (e.g. '0411' for 0G 1A 1P);
    # the triplet search recovers the correct values even when digits aren't consecutive.
    g = a = p = None
    n = min(len(gap_digits), 6)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                if gap_digits[i] + gap_digits[j] == gap_digits[k]:
                    g, a, p = gap_digits[i], gap_digits[j], gap_digits[k]
                    break
            if g is not None:
                break
        if g is not None:
            break

    if g is None:
        return 0, 0, 0, 0

    pim = 0
    if pim_token_idx < len(tokens):
        pim_digits = re.sub(r'[^\d]', '', tokens[pim_token_idx])
        pim = int(pim_digits) if pim_digits else 0

    return g, a, p, pim


def _parse_game_statistics(
    text: str, home_team: str = '', away_team: str = ''
) -> tuple[dict[str, dict[int, str]], list[dict]]:
    """
    Single pass through the Game Statistics section.

    Returns:
      jersey_map  — {team_abbr: {jersey_no: name_raw}}  (for PPG/SHG/GWG attribution)
      players     — [{name_raw, team, pos, goals, assists, pim, plus_minus}]
    """
    jersey_map: dict[str, dict[int, str]] = {}
    players: list[dict] = []
    current_team: str | None = None
    after_total = False

    pos_map = {"F": "Forward", "D": "Defender", "GK": "Goalkeeper",
               "FF": "Forward", "DD": "Defender"}

    for line in text.split("\n"):
        stripped = line.strip()

        # Game Statistics explicit header: "Team : SUI (Red)" — always update team.
        explicit_team_m = re.match(r"Team\s*:\s*([A-Z]{3})\s*\(", stripped)
        if explicit_team_m:
            current_team = explicit_team_m.group(1)
            jersey_map.setdefault(current_team, {})
            after_total = False
            continue

        # Goalkeeper Records header: "Team : SUI - Switzerland" — only initialise
        # if we haven't seen a Game Statistics team header yet.
        gk_team_m = re.match(r"Team\s*:\s*([A-Z]{3})", stripped)
        if gk_team_m and current_team is None:
            current_team = gk_team_m.group(1)
            jersey_map.setdefault(current_team, {})
            continue

        if current_team is None:
            continue

        # "Total N" or bare "Total" = end of one team's block.
        if re.match(r"^Total\s*(\d|$)", stripped):
            after_total = True
            continue

        player_m = _PLAYER_RE.match(line)
        if not player_m:
            continue

        if after_total and home_team and away_team:
            current_team = away_team if current_team == home_team else home_team
            jersey_map.setdefault(current_team, {})
            after_total = False

        jersey = int(player_m.group(1))
        pos_code = player_m.group(2)
        name_raw = re.sub(r"\s*\+[CA]$", "", player_m.group(3)).strip()
        pos = pos_map.get(pos_code, "Forward")

        jersey_map[current_team][jersey] = name_raw

        # Stats come right after the name match ends in the line.
        rest = line[player_m.end():]

        # Goalies don't have meaningful G/A/PIM in Game Statistics (always 0);
        # their actual saves/GA come from Goalkeeper Records.
        if pos == "Goalkeeper":
            g = a = pim = 0
        else:
            g, a, _p, pim = _extract_gap_pim(rest)

        # +/- is the value immediately before the TOI columns.
        # Try 5-column (with OT), 4-column, and 3-column+SHF+AVG variants.
        pm = 0
        for pattern in (
            r"(?<![:\d])(-?\+?\d+)\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+\s+\d+:\d+\s*$",
            r"(?<![:\d])(-?\+?\d+)\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+\s+\d+:\d+\s*$",
            r"(?<![:\d])(-?\+?\d+)\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+\s+\d+:\d+\s*$",
            # OCR sometimes renders the TOT field as bare ":" — match 3 TOI periods + ":" + SHF + AVG
            r"(?<![:\d])(-?\+?\d+)\s+\d+:\d+\.?\s+\d+:\d+\.?\s+\d+:\d+\.?\s+:\s+\d+\s+\d+:\d+\s*$",
        ):
            pm_m = re.search(pattern, line.strip())
            if pm_m:
                try:
                    pm = int(pm_m.group(1).replace("+", ""))
                except ValueError:
                    pm = 0
                break

        players.append({
            "name_raw": name_raw,
            "team": current_team,
            "pos": pos,
            "goals": g,
            "assists": a,
            "pim": pim,
            "plus_minus": pm,
        })

    return jersey_map, players


# ── Goal types (PPG / SHG / GWG only) ────────────────────────────────────────

def _parse_goal_types(text: str, jersey_map: dict[str, dict[int, str]]) -> list[dict]:
    """
    Parse goal events to determine scorer, goal type, and running score.
    Used only for PPG/SHG flags and GWG calculation — G/A/PIM come from Game Statistics.

    Returns [{scorer, team, is_pp, is_sh, home_score, away_score}]
    """
    events = []
    blocks = re.split(r"(?=Goal\s+\d+:\d+)", text)

    for block in blocks:
        m = re.match(
            r"Goal\s+\d+:\d+\.?\s+"
            r"(\d+):(\d+)\s+"                                        # home:away score
            r"([A-Z]{3})\s+"                                         # team
            r"(?:[_\s]*)"                                            # optional OCR noise
            r"(\w+)"                                                  # goal type
            r"(?:\s+(\d+)\s+([A-Z][A-Z0-9'\-]+(?:[ \t]+[A-Z])?)?"   # optional jersey + name
            r"\s*(?:\(\d+\))?)?",                                    # optional (goal_count)
            block,
        )
        if not m:
            continue

        team = m.group(3)
        goal_type = m.group(4).upper()
        scorer_jersey = int(m.group(5)) if m.group(5) else None
        scorer = jersey_map.get(team, {}).get(scorer_jersey, "") if scorer_jersey else ""

        events.append({
            "scorer": scorer,
            "team": team,
            "is_pp": goal_type.startswith("PP"),
            "is_sh": goal_type.startswith("SH"),
            "home_score": int(m.group(1)),
            "away_score": int(m.group(2)),
        })

    return events


# ── GWG ───────────────────────────────────────────────────────────────────────

def _calc_gwg(events: list[dict], home_abbr: str, final_home: int, final_away: int) -> str:
    """GWG: first goal that puts the winning team at loser_final+1."""
    if final_home == final_away:
        return ""
    home_wins = final_home > final_away
    threshold = (final_away if home_wins else final_home) + 1
    for ev in events:
        is_home_goal = ev["team"] == home_abbr
        if home_wins != is_home_goal:
            continue
        running = ev["home_score"] if home_wins else ev["away_score"]
        if running == threshold:
            return ev["scorer"]
    return ""


# ── Goalkeeper records ────────────────────────────────────────────────────────

def _parse_goalie_records(text: str) -> dict[str, tuple[int, int]]:
    """
    Parse all Goalkeeper Records sections (may be split across teams in the PDF).
    Returns {name_raw: (sog, svs)}.
    """
    goalies: dict[str, tuple[int, int]] = {}
    gk_start = re.search(r"Goalkeeper Records", text)
    if not gk_start:
        return goalies
    # Search from the first Goalkeeper Records marker to end of text.
    # GK rows in the Game Statistics section have no time format, so the
    # pattern \d+:\d+ is specific enough to avoid false positives there.
    for m in re.finditer(r"\d+\s+([A-Z][A-Z]+\s+\w+)\s+(\d+)\s+(\d+)\s+\d+:\d+", text[gk_start.start():]):
        name = m.group(1).strip()
        goalies[name] = (int(m.group(2)), int(m.group(3)))  # (sog, svs)
    return goalies


# ── Name normalisation ────────────────────────────────────────────────────────

def _pdf_to_db_name(name_raw: str) -> str:
    name = re.sub(r"\s*\+[CA]\s*", " ", name_raw)
    name = re.sub(r"\s*\([A-Z]+\)\s*", " ", name)
    name = re.sub(r"[!°%]", "", name)  # strip common OCR noise chars from surnames
    return " ".join(name.split())


# ── Main entry point ─────────────────────────────────────────────────────────

def scrape_game_stats(home_team: str, away_team: str) -> pd.DataFrame:
    """
    Fetch and parse the IIHF game summary PDF for home_team vs away_team.

    Returns a DataFrame with columns:
      Player, Team, Position, Goals, Assists, Points, Penalty Minutes,
      Plus Minus, Goals Against, Saves, Power Play Goal, Shorthanded Goal,
      Game Winning Goal, Win, Event
    """
    pdf_url = get_game_pdf_url(home_team, away_team)
    print(f"  Fetching PDF: {pdf_url}")
    pdf_resp = requests.get(pdf_url, timeout=60)
    pdf_resp.raise_for_status()

    text = _ocr_pdf(pdf_resp.content)

    # Truncate goals/penalties text at Goalkeeper Records to prevent bleed-through.
    gk_pos = re.search(r"Goalkeeper Records", text)
    goals_text = text[:gk_pos.start()] if gk_pos else text

    home_abbr, away_abbr, home_score, away_score = _parse_score(text)
    jersey_map, roster = _parse_game_statistics(text, home_team, away_team)
    goal_events = _parse_goal_types(goals_text, jersey_map)
    goalie_records = _parse_goalie_records(text)
    gwg_scorer = _calc_gwg(goal_events, home_abbr, home_score, away_score)

    # Per-scorer PPG and SHG counts from goal events.
    ppg_counts: dict[str, int] = {}
    shg_counts: dict[str, int] = {}
    for ev in goal_events:
        if ev["scorer"]:
            if ev["is_pp"]:
                ppg_counts[ev["scorer"]] = ppg_counts.get(ev["scorer"], 0) + 1
            if ev["is_sh"]:
                shg_counts[ev["scorer"]] = shg_counts.get(ev["scorer"], 0) + 1

    rows = []
    for p in roster:
        name_raw = p["name_raw"]
        team = p["team"]
        pos = p["pos"]
        win = int(
            (team == home_abbr and home_score > away_score)
            or (team == away_abbr and away_score > home_score)
        )
        saves = ga = 0
        if pos == "Goalkeeper" and name_raw in goalie_records:
            sog, svs = goalie_records[name_raw]
            saves, ga = svs, sog - svs

        rows.append({
            "Player": _pdf_to_db_name(name_raw),
            "Team": "home" if team == home_abbr else "away",
            "Position": pos,
            "Goals": p["goals"],
            "Assists": p["assists"],
            "Points": p["goals"] + p["assists"],
            "Penalty Minutes": p["pim"],
            "Plus Minus": p["plus_minus"],
            "Power Play Goal": ppg_counts.get(name_raw, 0),
            "Shorthanded Goal": shg_counts.get(name_raw, 0),
            "Game Winning Goal": int(bool(gwg_scorer) and name_raw == gwg_scorer),
            "Saves": saves,
            "Goals Against": ga,
            "Win": win,
            "Event": "",
        })

    df = pd.DataFrame(rows)

    # Zero out all stats for backup goalies (0 saves = didn't play).
    gk_zero = (df["Position"] == "Goalkeeper") & (df["Saves"] == 0)
    if gk_zero.any():
        num_cols = df.select_dtypes(include="number").columns
        df.loc[gk_zero, num_cols] = 0
        print("Reset stats for backup goalkeepers with 0 saves to 0")

    print(df)
    return df


if __name__ == "__main__":
    df = scrape_game_stats("FIN", "GER")
    print(df.to_string())
