import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth
from config import CHAMPIONSHIP_URL

url = f'{CHAMPIONSHIP_URL}/schedule'


def scrape_schedule():
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled']
        )
        page = browser.new_page(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        try:
            # Prime session cookies on the main championship page first.
            page.goto(CHAMPIONSHIP_URL, timeout=30000)
            page.goto(url, timeout=30000)
            try:
                page.wait_for_selector('.b-card-schedule', timeout=20000)
            except PlaywrightTimeout:
                print("Warning: .b-card-schedule not found after 20s")
                print(f"  Title: {page.title()}")
                print(f"  HTML (first 500): {page.content()[:500]}")
                return

            html = page.content()
        finally:
            browser.close()

    soup = BeautifulSoup(html, 'html.parser')
    match_cards = soup.find_all('div', class_='b-card-schedule')

    matches = []
    for card in match_cards:
        date_el = card.find('div', class_='s-date')
        time_el = card.find('div', class_='s-time')
        if not date_el or not time_el:
            continue
        date = date_el.text.strip()
        # Extract HH:MM from text like "16:20 (Local time)"
        time_raw = time_el.text.strip()
        time_match = re.search(r'\d{1,2}:\d{2}', time_raw)
        if not time_match:
            continue
        time = time_match.group(0)

        gamecenter_link = None
        for a in card.find_all('a', class_='s-hover__link'):
            href = a.get('href', '')
            if href.startswith('/'):
                gamecenter_link = href
                break

        if not gamecenter_link:
            continue  # skip upcoming games without a gamecenter link yet

        home_team = card.get('data-hometeam', 'N/A')
        away_team = card.get('data-guestteam', 'N/A')
        phase = card.get('data-phase', 'PreliminaryRound')

        matches.append({
            'date': date,
            'time': time,
            'home_team': home_team,
            'away_team': away_team,
            'phase': phase,
            'url_playbyplay': f"https://www.iihf.com{gamecenter_link}",
        })

    if not matches:
        print("No match cards found — schedule may not have loaded or no completed games yet.")
        return

    df = pd.DataFrame(matches)
    df['url_playbyplay'] = df['url_playbyplay'].apply(lambda x: x[:x.rfind('/') + 1])
    df['url_statistics'] = df['url_playbyplay'].str.replace('gamecenter/playbyplay', 'gamecenter/statistics')

    # WM 2026 runs entirely in May 2026 — no cross-year handling needed.
    df['datetime'] = pd.to_datetime(df['date'] + ' 2026', format='%d %b %Y', errors='coerce')
    df = df.sort_values('datetime')

    unique_dates = df['datetime'].dt.date.unique()
    date_to_day = {date: idx + 1 for idx, date in enumerate(sorted(unique_dates))}
    df['Day'] = df['datetime'].dt.date.map(date_to_day)
    df.drop('datetime', axis=1, inplace=True)

    columns = ['Day'] + [col for col in df.columns if col != 'Day']
    df = df[columns]

    df.to_csv('match_urls.csv', index=False)
    print(f"Saved {len(df)} matches across {len(unique_dates)} championship days to match_urls.csv")


if __name__ == '__main__':
    scrape_schedule()
