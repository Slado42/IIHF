import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from match_stats_scraper import extract_all_stats
from config import CHAMPIONSHIP_URL

# URL of the IIHF website schedule page
url = f'{CHAMPIONSHIP_URL}/schedule'

# Use a session with browser-like headers to avoid Cloudflare 403.
# Prime the session by hitting the main championship page first.
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
})
session.get(CHAMPIONSHIP_URL)

# Send a GET request to the schedule URL
response = session.get(url)

# Check if the request was successful
if response.status_code == 200:
    # Parse the HTML content of the page
    soup = BeautifulSoup(response.content, 'html.parser')
    # Find all match cards
    match_cards = soup.find_all('div', class_='b-card-schedule')

    # Extract match data
    matches = []
    for card in match_cards:
        date = card.find('div', class_='s-date').text.strip()
        time = card.find('div', class_='s-time').text.strip()

        # Each completed game card has two s-hover__link elements:
        #   [0] = YouTube highlight video (js-video-modal-trigger)
        #   [1] = IIHF gamecenter play-by-play URL
        # We want the gamecenter link, so filter to the one whose href
        # starts with '/' (a relative IIHF URL) rather than 'http'.
        gamecenter_link = None
        for a in card.find_all('a', class_='s-hover__link'):
            href = a.get('href', '')
            if href.startswith('/'):
                gamecenter_link = href
                break

        if not gamecenter_link:
            continue  # skip cards without a gamecenter link (e.g. upcoming games)

        # Extract team acronyms from data attributes instead of HTML elements
        home_team = card.get('data-hometeam', 'N/A')
        away_team = card.get('data-guestteam', 'N/A')

        matches.append({
            'date': date,
            'time': time,
            'home_team': home_team,
            'away_team': away_team,
            'url_playbyplay': f"https://www.iihf.com{gamecenter_link}"
        })

    # Create DataFrame
    df = pd.DataFrame(matches)
    df['url_playbyplay'] = df['url_playbyplay'].apply(lambda x: x[:x.rfind('/') + 1])
    df['url_statistics'] = df['url_playbyplay'].str.replace('gamecenter/playbyplay', 'gamecenter/statistics')

    # Convert date strings to datetime objects for calculating championship days
    # Parse date format (assuming format is like '10 MAY')
    df['datetime'] = pd.to_datetime(df['date'] + ' 2024', format='%d %b %Y', errors='coerce')

    # Sort by date to ensure proper day calculation
    df = df.sort_values('datetime')

    # Get the first day of the championship
    first_day = df['datetime'].min()

    # Calculate the Day number (1-indexed) based on unique dates
    # Group by date and create a mapping of date to day number
    unique_dates = df['datetime'].dt.date.unique()
    date_to_day = {date: idx + 1 for idx, date in enumerate(sorted(unique_dates))}

    # Map each date to its corresponding day number
    df['Day'] = df['datetime'].dt.date.map(date_to_day)

    # Drop the temporary datetime column
    df.drop('datetime', axis=1, inplace=True)

    # Reorder columns to make Day column the first one
    columns = ['Day'] + [col for col in df.columns if col != 'Day']
    df = df[columns]

    # Save to CSV
    df.to_csv('match_urls.csv', index = False)

    print(f"Added Day column to the dataset with {len(unique_dates)} total championship days")
    print(f"Added home_team and away_team columns with 3-letter team acronyms from data attributes")

else:
    print(f"Failed to retrieve the webpage. Status code: {response.status_code}")
