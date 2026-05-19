"""
IIHF gamecenter stats scraper — runs locally, bypasses Cloudflare via playwright-stealth.

Two data sources:
  1. Rendered stats HTML page (Playwright) → G, A, PIM, +/-, saves, GA per player
  2. realtime.iihf.com JSON API (plain requests) → PPG, SHG, GWG from goal events
"""
import os
# Only override browser path on Render (where it's pre-installed); leave unset locally.
if os.getenv('RENDER'):
    os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/render/project/src')

import re
import requests
import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'


def _scrape_stats_page(url_statistics: str) -> tuple[list[dict], str]:
    """
    Load the gamecenter statistics page with Playwright and extract per-player stats.

    Returns (players, game_id) where players is a list of dicts:
      {name, team ('home'|'away'), position, goals, assists, pim, plus_minus, saves, goals_against}
    and game_id is the realtime.iihf.com game identifier.
    """
    base_url = url_statistics.split('/gamecenter/')[0]

    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
        ])
        page = browser.new_page(user_agent=_UA)
        try:
            page.goto(base_url, timeout=60000, wait_until='domcontentloaded')
            for attempt in range(2):
                try:
                    page.goto(url_statistics, timeout=60000, wait_until='domcontentloaded')
                    break
                except PlaywrightTimeout:
                    if attempt == 0:
                        page.goto(base_url, timeout=60000, wait_until='domcontentloaded')
                    else:
                        raise

            page.wait_for_selector('.s-team--home', timeout=30000)
            # Wait for JS to populate stat values
            page.wait_for_selector('td.s-cell--g.js-table-cell', timeout=15000)

            # Extract game_id for the realtime API
            game_id_el = page.query_selector('#game-id')
            game_id = game_id_el.get_attribute('value') if game_id_el else ''

            players = []
            # Each gc-statistics section belongs to home or away team.
            # Sections alternate: first 4 are home, last 4 are away (skaters + goalies each).
            sections = page.query_selector_all('.m-statistics-table--gc-statistics')

            for sec in sections:
                # Determine team by walking up to s-team--home / s-team--away
                team_cls = page.evaluate(
                    """(el) => {
                        let p = el.parentElement;
                        while (p) {
                            if (p.classList.contains('s-team--home')) return 'home';
                            if (p.classList.contains('s-team--away')) return 'away';
                            p = p.parentElement;
                        }
                        return null;
                    }""",
                    sec,
                )
                if team_cls is None:
                    continue

                # Build name/jersey map from left table: data-fwk-id → {name, jersey}
                left_rows = sec.query_selector_all('.s-table-wrapper--left tr[data-fwk-id]')
                name_map: dict[str, dict] = {}
                for row in left_rows:
                    fwk_id = row.get_attribute('data-fwk-id')
                    name_el = row.query_selector('.s-cell--name .s-value')
                    name = name_el.inner_text().strip() if name_el else ''
                    if name:
                        name_map[fwk_id] = {'name': name}

                if not name_map:
                    continue

                # Extract stats from right table: data-fwk-id → stat cells
                right_rows = sec.query_selector_all('.s-table-wrapper--right tr[data-fwk-id]')
                for row in right_rows:
                    fwk_id = row.get_attribute('data-fwk-id')
                    if fwk_id not in name_map:
                        continue

                    def cell(cls):
                        el = row.query_selector(f'.s-cell--{cls} .s-value')
                        txt = el.inner_text().strip() if el else ''
                        try:
                            return int(txt)
                        except ValueError:
                            return 0

                    pos_el = row.query_selector('.s-cell--pos .s-value')
                    pos_raw = pos_el.inner_text().strip().upper() if pos_el else ''
                    pos_map = {'F': 'Forward', 'D': 'Defender', 'GK': 'Goalkeeper', 'G': 'Goalkeeper'}
                    position = pos_map.get(pos_raw, 'Forward')

                    # Skater stats
                    goals = cell('g')
                    assists = cell('a')
                    pim = cell('pim')
                    plus_minus_el = row.query_selector('.s-cell--dynamic .s-value')
                    pm_txt = plus_minus_el.inner_text().strip() if plus_minus_el else '0'
                    try:
                        plus_minus = int(pm_txt)
                    except ValueError:
                        plus_minus = 0

                    # Goalie stats
                    saves = cell('svs')
                    ga = cell('ga')

                    players.append({
                        'name': name_map[fwk_id]['name'],
                        'team': team_cls,
                        'position': position,
                        'goals': goals,
                        'assists': assists,
                        'pim': pim,
                        'plus_minus': plus_minus,
                        'saves': saves,
                        'goals_against': ga,
                    })

            return players, game_id

        finally:
            browser.close()


def _scrape_goal_events(game_id: str) -> tuple[dict[str, int], dict[str, int], str, str]:
    """
    Fetch goal events from realtime.iihf.com (no Cloudflare).

    Returns (ppg_counts, shg_counts, gwg_scorer, home_abbr, away_abbr).
    Player names keyed by ReportingName (e.g. 'BARKOV Aleksander').
    """
    url = f'https://realtime.iihf.com/gamestate/GetLatestState/{game_id}'
    data = requests.get(url, timeout=30).json()

    home_abbr = data['HomeTeam']['ShortTeamName']
    away_abbr = data['AwayTeam']['ShortTeamName']
    home_score = int(data['CurrentScore']['Home'])
    away_score = int(data['CurrentScore']['Away'])

    ppg: dict[str, int] = {}
    shg: dict[str, int] = {}
    gwg_scorer = ''

    # GWG threshold: first goal that puts winner at loser_final + 1
    home_wins = home_score > away_score
    gwg_threshold = (away_score if home_wins else home_score) + 1
    gwg_found = False

    for period in data.get('Periods', []):
        for action in period.get('Actions', []):
            if action.get('Code') != 'GOL':
                continue

            scorer = action.get('Scorer', {})
            name = scorer.get('ReportingName', '')
            situation = (action.get('SituationType') or '').upper()
            new_score = action.get('NewScore', {})
            h = int(new_score.get('Home', 0))
            a = int(new_score.get('Away', 0))
            is_home_goal = action.get('IsExecutedByHomeTeam', False)

            if situation.startswith('PP'):
                ppg[name] = ppg.get(name, 0) + 1
            if situation.startswith('SH'):
                shg[name] = shg.get(name, 0) + 1

            if not gwg_found:
                running = h if home_wins else a
                if (home_wins == is_home_goal) and running == gwg_threshold:
                    gwg_scorer = name
                    gwg_found = True

    return ppg, shg, gwg_scorer, home_abbr, away_abbr


def extract_all_stats(url_playbyplay: str, url_statistics: str, home_team: str, away_team: str) -> pd.DataFrame:
    """
    Scrape per-player stats for a completed match.

    url_playbyplay is accepted for API compatibility but unused (events come from realtime API).
    Returns DataFrame with columns matching scraper_bridge expectations.
    """
    players, game_id = _scrape_stats_page(url_statistics)

    if not game_id:
        raise RuntimeError(f'Could not find game_id on stats page {url_statistics}')

    ppg, shg, gwg_scorer, home_abbr, away_abbr = _scrape_goal_events(game_id)

    # Deduplicate: if a player appears in multiple sections (skater + goalie row),
    # keep the row with the most stats (sum of numeric fields).
    seen: dict[tuple, dict] = {}
    for p in players:
        key = (p['name'], p['team'])
        score = p['goals'] + p['assists'] + p['pim'] + abs(p['plus_minus']) + p['saves'] + p['goals_against']
        if key not in seen or score > seen[key]['_score']:
            p['_score'] = score
            seen[key] = p
    players = list(seen.values())

    # Determine win per team
    home_win = home_abbr == home_team  # home_abbr from API matches home_team arg
    # Actually derive from CurrentScore already fetched inside _scrape_goal_events,
    # but we only have home_abbr/away_abbr here. Re-derive from players not needed —
    # we can call the API again or pass through. Simplest: check who scored more goals.
    home_goals = sum(p['goals'] for p in players if p['team'] == 'home')
    away_goals = sum(p['goals'] for p in players if p['team'] == 'away')

    rows = []
    for p in players:
        name = p['name']
        is_home = p['team'] == 'home'
        win = int(
            (is_home and home_goals > away_goals) or
            (not is_home and away_goals > home_goals)
        )
        rows.append({
            'Player': name,
            'Team': 'home' if is_home else 'away',
            'Position': p['position'],
            'Goals': p['goals'],
            'Assists': p['assists'],
            'Points': p['goals'] + p['assists'],
            'Penalty Minutes': p['pim'],
            'Plus Minus': p['plus_minus'],
            'Power Play Goal': ppg.get(name, 0),
            'Shorthanded Goal': shg.get(name, 0),
            'Game Winning Goal': int(name == gwg_scorer and bool(gwg_scorer)),
            'Saves': p['saves'],
            'Goals Against': p['goals_against'],
            'Win': win,
            'Event': '',
        })

    df = pd.DataFrame(rows)
    print(df[['Player', 'Team', 'Goals', 'Assists', 'Plus Minus', 'Saves', 'Goals Against']].to_string())
    return df
