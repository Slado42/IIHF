import re
import time
import pandas as pd
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth
from config import CREDENTIALS_PATH, SHEETS_SCOPE, SPREADSHEETS, LINEUPS_SHEET, LINEUPS_CSV, CHAMPIONSHIP_URL

UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

COUNTRY_ABBR_MAP = {
    'Austria': 'AUT', 'Switzerland': 'SUI', 'Norway': 'NOR',
    'Finland': 'FIN', 'Czech Republic': 'CZE', 'Czechia': 'CZE',
    'Slovakia': 'SVK', 'Germany': 'GER', 'Sweden': 'SWE',
    'United States': 'USA', 'Canada': 'CAN', 'Great Britain': 'GBR',
    'Kazakhstan': 'KAZ', 'France': 'FRA', 'Denmark': 'DEN',
    'Latvia': 'LAT', 'Poland': 'POL', 'Hungary': 'HUN',
    'Italy': 'ITA', 'Slovenia': 'SLO',
}

TEAM_CORRECTIONS = {
    'AUS': 'AUT', 'GRE': 'GBR', 'SWI': 'SUI', 'UNI': 'USA',
}


def _get_html(page, url, wait_selector, timeout=20000, retries=2):
    for attempt in range(retries + 1):
        try:
            page.goto(url, timeout=60000)
            try:
                page.wait_for_selector(wait_selector, timeout=timeout)
            except PlaywrightTimeout:
                pass
            return page.content()
        except PlaywrightTimeout:
            if attempt < retries:
                print(f"  Timeout on {url}, retrying ({attempt + 1}/{retries})...")
                time.sleep(3)
                page.goto(CHAMPIONSHIP_URL, timeout=60000)  # re-prime cookies
            else:
                print(f"  Failed after {retries + 1} attempts: {url}")
                return ""


def _parse_teams_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    team_data = []
    for link in soup.find_all('a', class_='s-country-title'):
        if not link.has_attr('href'):
            continue
        country_name = link.text.strip().split('\n')[0].strip()
        href = link['href']
        team_abbr = COUNTRY_ABBR_MAP.get(country_name)
        country_code = None
        code_match = re.search(r'/([A-Z]{3})(?:/|$)', href)
        if code_match:
            country_code = code_match.group(1)
        if not country_code:
            parent = link.find_parent()
            if parent:
                img_tag = parent.find('img', class_='s-team-img')
                if img_tag and 'alt' in img_tag.attrs:
                    m = re.search(r'([A-Z]{3})', img_tag['alt'])
                    if m:
                        country_code = m.group(1)
        if not country_code:
            country_code = country_name[:3].upper()
        country_code = TEAM_CORRECTIONS.get(country_code, country_code)
        if not team_abbr:
            team_abbr = TEAM_CORRECTIONS.get(country_code, country_code)
        team_data.append({
            'country_name': country_name,
            'country': country_code,
            'team_abbr': team_abbr,
            'team_url': f"https://www.iihf.com{href}",
        })
        print(f"Team: {country_name}, Code: {country_code}, Abbr: {team_abbr}")
    return pd.DataFrame(team_data)


def get_teams_df():
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        page = browser.new_page(user_agent=UA)
        try:
            page.goto(CHAMPIONSHIP_URL, timeout=30000)
            html = _get_html(page, f'{CHAMPIONSHIP_URL}/teams', 'a.s-country-title')
        finally:
            browser.close()
    return _parse_teams_from_html(html)


def extract_players_from_team_page(team_url, country_code, team_abbr):
    """Scrape one team roster. Opens its own browser — for single-team use only."""
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        page = browser.new_page(user_agent=UA)
        try:
            page.goto(CHAMPIONSHIP_URL, timeout=30000)
            html = _get_html(page, team_url, '.s-players, .s-table', timeout=15000)
        finally:
            browser.close()
    return _parse_players_from_html(html, country_code, team_abbr)


def _parse_players_from_html(html, country_code, team_abbr):
    soup = BeautifulSoup(html, 'html.parser')
    players = []

    players_section = soup.find('section', class_='s-players')
    if players_section:
        for item in players_section.find_all('div', class_='s-players__item'):
            name_elem = item.find('h4', class_='s-players__name')
            position_elem = item.find('p', string=lambda t: t and 'Position:' in t)
            if not name_elem:
                continue
            name = name_elem.text.strip()
            position = None
            if position_elem:
                m = re.search(r'Position:\s*(\w+)', position_elem.text)
                if m:
                    position = m.group(1).strip()
            if _skip_name(name, position):
                continue
            players.append({'name': name, 'position': position, 'country': country_code, 'team_abbr': team_abbr})

    if not players:
        table = soup.find('table', class_='s-table')
        if table:
            for row in table.find_all('tr'):
                cells = row.find_all('td')
                if len(cells) < 3:
                    continue
                name = cells[2].text.strip() if len(cells) > 2 else None
                position = None
                for cell in cells:
                    if 'Position:' in cell.text:
                        m = re.search(r'Position:\s*(\w+)', cell.text)
                        if m:
                            position = m.group(1).strip()
                if not name or _skip_name(name, position):
                    continue
                players.append({'name': name, 'position': position, 'country': country_code, 'team_abbr': team_abbr})

    return players


def _skip_name(name, position):
    if not name:
        return True
    if name.lower() == 'name' and not position:
        return True
    stripped = name.lstrip('#')
    if stripped.isdigit() and not position:
        return True
    return False


def upload_to_spreadsheets(df):
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials
    print(f"\nUploading data to {len(SPREADSHEETS)} spreadsheets...")
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SHEETS_SCOPE)
    client = gspread.authorize(credentials)

    for owner_name, spreadsheet_id in SPREADSHEETS.items():
        try:
            print(f"\nProcessing {owner_name}'s spreadsheet...")
            spreadsheet = client.open_by_key(spreadsheet_id)
            try:
                existing = spreadsheet.worksheet(LINEUPS_SHEET)
                spreadsheet.del_worksheet(existing)
                print(f"  Removed existing '{LINEUPS_SHEET}' sheet")
            except gspread.exceptions.WorksheetNotFound:
                pass
            worksheet = spreadsheet.add_worksheet(title=LINEUPS_SHEET, rows=df.shape[0] + 1, cols=df.shape[1])
            values = [df.columns.tolist()] + df.values.tolist()
            worksheet.update(values, value_input_option='USER_ENTERED')
            print(f"  Uploaded {df.shape[0]} rows to '{LINEUPS_SHEET}' in {owner_name}'s spreadsheet")
        except Exception as e:
            print(f"  Error uploading to {owner_name}'s spreadsheet: {str(e)}")


CHROMIUM_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-gpu',
]


def fetch_all_players() -> list:
    """Scrape all team rosters in a single browser session. No DB or Sheets side-effects."""
    all_players = []
    with Stealth().use_sync(sync_playwright()) as p:
        browser = p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        try:
            # Get teams list
            page = browser.new_page(user_agent=UA)
            page.goto(CHAMPIONSHIP_URL, timeout=60000)
            teams_html = _get_html(page, f'{CHAMPIONSHIP_URL}/teams', 'a.s-country-title')
            df_teams = _parse_teams_from_html(teams_html)
            page.close()
            print(f"Found {len(df_teams)} teams")

            # Scrape each team on a fresh page to release DOM memory between requests
            for _, row in df_teams.iterrows():
                print(f"Scraping players from {row['country_name']} ({row['team_abbr']})...")
                page = browser.new_page(user_agent=UA)
                try:
                    html = _get_html(page, row['team_url'], '.s-players, .s-table', timeout=15000)
                    players = _parse_players_from_html(html, row['country'], row['team_abbr'])
                    all_players.extend(players)
                    print(f"  {row['team_abbr']}: {len(players)} players")
                finally:
                    page.close()
                time.sleep(2)
        finally:
            browser.close()
    return all_players


def scrape_and_process():
    print("Fetching team data and player rosters from IIHF website...")
    all_players = fetch_all_players()

    df_players = pd.DataFrame(all_players)
    df_players = df_players[~(
        ((df_players['name'].str.replace('#', '').str.isdigit()) |
         (df_players['name'].str.lower() == 'name')) &
        df_players['position'].isna()
    )]

    df_players.to_csv(LINEUPS_CSV, index=False)
    print(f"Lineups saved to {LINEUPS_CSV} with {len(df_players)} total players")

    upload_to_spreadsheets(df_players)
    return df_players


if __name__ == "__main__":
    df_players = scrape_and_process()
