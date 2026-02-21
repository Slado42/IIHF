"""
Diagnostic script to test IIHF scraper compatibility with 2026 WM20 website.
Run this to check if the existing scraping classes/structure still work.
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def check(condition, name):
    status = "OK" if condition else "BROKEN"
    print(f"  [{status}] {name}")
    return condition

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


# ──────────────────────────────────────────────────────────────
# 1. SCHEDULE PAGE
# ──────────────────────────────────────────────────────────────
section("1. Schedule page: https://www.iihf.com/en/events/2026/wm20/schedule")

url = 'https://www.iihf.com/en/events/2026/wm20/schedule'
r = requests.get(url, headers=HEADERS)
print(f"  HTTP status: {r.status_code}")

if r.status_code == 200:
    soup = BeautifulSoup(r.content, 'html.parser')

    cards = soup.find_all('div', class_='b-card-schedule')
    check(len(cards) > 0, f"div.b-card-schedule match cards found ({len(cards)} cards)")

    if cards:
        card = cards[0]
        check(card.find('div', class_='s-date') is not None, "div.s-date inside card")
        check(card.find('div', class_='s-time') is not None, "div.s-time inside card")
        check(card.find('a', class_='s-hover__link') is not None, "a.s-hover__link game link")
        check(card.has_attr('data-hometeam'), "data-hometeam attribute on card")
        check(card.has_attr('data-guestteam'), "data-guestteam attribute on card")

        print(f"\n  Sample card data-hometeam: {card.get('data-hometeam', 'MISSING')}")
        print(f"  Sample card data-guestteam: {card.get('data-guestteam', 'MISSING')}")

        link = card.find('a', class_='s-hover__link')
        if link:
            sample_url = f"https://www.iihf.com{link['href']}"
            print(f"  Sample game URL: {sample_url}")

    # Show what classes are actually on divs (top-level) to help debug if broken
    if len(cards) == 0:
        print("\n  Schedule page classes found (first 30 divs):")
        for d in soup.find_all('div')[:30]:
            if d.get('class'):
                print(f"    {d.get('class')}")
else:
    print("  Could not fetch schedule page.")


# ──────────────────────────────────────────────────────────────
# 2. TEAMS PAGE
# ──────────────────────────────────────────────────────────────
section("2. Teams page: https://www.iihf.com/en/events/2026/wm20/teams")

url_teams = 'https://www.iihf.com/en/events/2026/wm20/teams'
r2 = requests.get(url_teams, headers=HEADERS)
print(f"  HTTP status: {r2.status_code}")

team_url_for_roster = None
if r2.status_code == 200:
    soup2 = BeautifulSoup(r2.content, 'html.parser')
    team_links = soup2.find_all('a', class_='s-country-title')
    check(len(team_links) > 0, f"a.s-country-title team links ({len(team_links)} found)")

    if team_links:
        first = team_links[0]
        print(f"  First team link text: {first.text.strip()}")
        print(f"  First team link href: {first.get('href', 'MISSING')}")
        if first.get('href'):
            team_url_for_roster = f"https://www.iihf.com{first['href']}"

    if len(team_links) == 0:
        print("\n  Looking for alternative team link structures:")
        for a in soup2.find_all('a')[:30]:
            if a.get('class'):
                print(f"    <a class='{a.get('class')}' href='{a.get('href', '')}'>")


# ──────────────────────────────────────────────────────────────
# 3. TEAM ROSTER PAGE
# ──────────────────────────────────────────────────────────────
section("3. Team roster page")

# Use known WM20 2026 roster URL pattern
roster_url = team_url_for_roster or 'https://www.iihf.com/en/events/2026/wm20/roster/CAN'
print(f"  Fetching: {roster_url}")
r3 = requests.get(roster_url, headers=HEADERS)
print(f"  HTTP status: {r3.status_code}")

if r3.status_code == 200:
    soup3 = BeautifulSoup(r3.content, 'html.parser')

    players_section = soup3.find('section', class_='s-players')
    check(players_section is not None, "section.s-players")

    if players_section:
        items = players_section.find_all('div', class_='s-players__item')
        check(len(items) > 0, f"div.s-players__item ({len(items)} found)")

        if items:
            first_item = items[0]
            name_elem = first_item.find('h4', class_='s-players__name')
            check(name_elem is not None, "h4.s-players__name")
            if name_elem:
                print(f"  First player name: {name_elem.text.strip()}")

            pos_elem = first_item.find('p', string=lambda t: t and 'Position:' in t)
            check(pos_elem is not None, "p element with 'Position:' text")
            if pos_elem:
                print(f"  First player position text: {pos_elem.text.strip()}")

    table = soup3.find('table', class_='s-table')
    check(table is not None, "Fallback table.s-table")


# ──────────────────────────────────────────────────────────────
# 4. MATCH STATISTICS PAGE
# ──────────────────────────────────────────────────────────────
section("4. Match statistics page (finding a completed WM20 2026 game)")

# Try to find a completed game URL from the schedule
stats_url = None
if r.status_code == 200:
    soup_sched = BeautifulSoup(r.content, 'html.parser')
    for card in soup_sched.find_all('div', class_='b-card-schedule'):
        link = card.find('a', class_='s-hover__link')
        if link and link.get('href'):
            pbp_url = f"https://www.iihf.com{link['href']}"
            # Normalize: strip trailing slug part, keep base gamecenter URL
            pbp_base = pbp_url[:pbp_url.rfind('/') + 1] if pbp_url.endswith('/') else pbp_url + '/'
            # Convert to statistics URL
            stats_candidate = pbp_base.replace('gamecenter/playbyplay', 'gamecenter/statistics')
            stats_url = stats_candidate
            break

if not stats_url:
    # Fallback: try a known WM20 2026 game ID (games often start around 70000+)
    stats_url = 'https://www.iihf.com/en/events/2026/wm20/gamecenter/statistics/68001/'

print(f"  Fetching: {stats_url}")
r4 = requests.get(stats_url, headers=HEADERS)
print(f"  HTTP status: {r4.status_code}")

if r4.status_code == 200:
    soup4 = BeautifulSoup(r4.content, 'html.parser')

    home = soup4.find('div', class_='s-team--home')
    away = soup4.find('div', class_='s-team--away')
    check(home is not None, "div.s-team--home")
    check(away is not None, "div.s-team--away")

    if home:
        tables = home.find_all('div', class_='s-tables')
        check(len(tables) >= 2, f"div.s-tables inside home team (expected 2, got {len(tables)})")

        if tables:
            skaters_table = tables[0]
            tbodies = skaters_table.find_all('tbody', class_='s-table__body')
            check(len(tbodies) >= 2, f"tbody.s-table__body in skaters table (expected 2, got {len(tbodies)})")

            if tbodies:
                # Names tbody
                name_cells = tbodies[0].find_all('td', class_='s-cell--name')
                check(len(name_cells) > 0, f"td.s-cell--name in names tbody ({len(name_cells)} found)")
                if name_cells:
                    val = name_cells[0].find('span', class_='js-table-cell-value')
                    check(val is not None, "span.js-table-cell-value inside name cell")

            if len(tbodies) >= 2:
                stats_tbody = tbodies[1]
                for cls in ['s-cell--pos', 's-cell--g', 's-cell--a', 's-cell--p', 's-cell--pim', 's-cell--dynamic']:
                    cells = stats_tbody.find_all('td', class_=cls)
                    check(len(cells) > 0, f"td.{cls} ({len(cells)} cells)")

        if len(tables) >= 2:
            goalies_table = tables[1]
            gtbodies = goalies_table.find_all('tbody', class_='s-table__body')
            check(len(gtbodies) >= 2, f"tbody.s-table__body in goalies table (expected 2, got {len(gtbodies)})")
            if len(gtbodies) >= 2:
                for cls in ['s-cell--ga', 's-cell--svs']:
                    cells = gtbodies[1].find_all('td', class_=cls)
                    check(len(cells) > 0, f"Goalie td.{cls} ({len(cells)} cells)")
else:
    print(f"  Could not fetch stats page (status {r4.status_code})")
    print("  Note: Game may not have completed yet, or URL pattern changed.")

print("\n\nDiagnostic complete.")
