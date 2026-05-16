import os
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', '/opt/render/project/src')

import pandas as pd
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth
from game_winning_goals import extract_gwg


def extract_other_stats(url_playbyplay, url_statistics):
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, args=[
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-gpu',
        ])
        page = browser.new_page()

        try:
            # Load the statistics page and capture its HTML for BeautifulSoup parsing.
            # Playwright uses its own bundled Chromium — no system Chrome needed.
            page.goto(url_statistics, timeout=30000)
            try:
                page.wait_for_selector('.s-team--home', timeout=30000)
            except PlaywrightTimeout:
                print(f"Warning: .s-team--home not found on stats page after 30s")
                print(f"  URL: {page.url}")
                print(f"  Title: {page.title()}")
                print(f"  HTML (first 1000): {page.content()[:1000]}")
            stats_html = page.content()

            # Load the play-by-play page for goal event data
            page.goto(url_playbyplay, timeout=30000)

            match_score_home = 0
            match_score_away = 0
            df = pd.DataFrame()

            try:
                page.wait_for_selector('.s-timeline-event.js-timeline-event', timeout=15000)

                events = page.query_selector_all('.s-timeline-event.js-timeline-event')

                # Parse game result
                score_elements = page.query_selector_all('.s-team-score')
                if len(score_elements) >= 2:
                    match_score_home = score_elements[0].inner_text().strip()
                    match_score_away = score_elements[1].inner_text().strip()

                # Parse goal events
                goal_data = []
                for event in events:
                    description = event.query_selector('.s-cell--description')
                    if not description:
                        continue

                    title_el = description.query_selector('.s-title')
                    if not title_el:
                        continue
                    title = title_el.inner_text()

                    player_elements = description.query_selector_all('.s-player')
                    if player_elements:
                        name_el = player_elements[0].query_selector('.s-name')
                        if name_el:
                            scorer = name_el.inner_text()
                            goal_data.append({
                                'Event': title.strip(),
                                'Player': scorer.strip()
                            })

                df = pd.DataFrame(goal_data)
                if not df.empty:
                    df = df[df.Event.str.contains('Goal!')]
                    df['Shorthanded Goal'] = df['Event'].str.contains(r'\(SH').astype(int)
                    df['Power Play Goal'] = df['Event'].str.contains(r'\(PP').astype(int)

                    df = extract_gwg(df)
                    df['Event'] = df.pop('Event')
                    df = df.groupby('Player').agg({
                        'Shorthanded Goal': 'sum',
                        'Power Play Goal': 'sum',
                        'Game Winning Goal': 'max',  # max not sum — GWG is boolean per player
                        'Event': list
                    }).reset_index()

            except PlaywrightTimeout as pbp_err:
                print(f"Warning: play-by-play page timed out ({pbp_err}), using stats page only")
            except Exception as pbp_err:
                print(f"Warning: play-by-play parsing failed ({pbp_err}), using stats page only")

            return stats_html, df, match_score_home, match_score_away

        finally:
            browser.close()
