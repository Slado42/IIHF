import pandas as pd
import requests
import re
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import CREDENTIALS_PATH, SHEETS_SCOPE, SPREADSHEETS, LINEUPS_SHEET, LINEUPS_CSV, CHAMPIONSHIP_URL

def make_session():
    """Create a requests session with browser-like headers to avoid Cloudflare 403."""
    s = requests.Session()
    s.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    s.get(CHAMPIONSHIP_URL)  # prime session cookies
    return s

def extract_players_from_team_page(team_url, country_code, team_abbr):
    session = make_session()
    response = session.get(team_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    table = soup.find('table', class_='s-table')
    players = []
    if table:
        # Find all player rows
        players_section = soup.find('section', class_='s-players')
        if players_section:
            player_items = players_section.find_all('div', class_='s-players__item')
            for item in player_items:
                name_elem = item.find('h4', class_='s-players__name')
                position_elem = item.find('p', text=lambda t: t and 'Position:' in t)
                
                if name_elem:
                    name = name_elem.text.strip()
                    position = None
                    if position_elem:
                        position_match = re.search(r'Position:\s*(\w+)', position_elem.text)
                        if position_match:
                            position = position_match.group(1).strip()
                    
                    # Skip numerical names with no position or literal "name" with no position
                    if (name.isdigit() and not position) or (name.lower() == "name" and not position):
                        continue
                    
                    players.append({
                        'name': name,
                        'position': position,
                        'country': country_code,
                        'team_abbr': team_abbr  # Use the corrected team abbreviation
                    })
        
        # If player section not found, try alternative approach with table
        if not players and table:
            rows = table.find_all('tr')
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 3:
                    name = cells[2].text.strip() if len(cells) > 2 else None
                    position = None
                    
                    # Look for position info in this row
                    for cell in cells:
                        if 'Position:' in cell.text:
                            position_match = re.search(r'Position:\s*(\w+)', cell.text)
                            if position_match:
                                position = position_match.group(1).strip()
                    
                    # Skip numerical names or "name" with no position
                    if name and ((name.isdigit() or name.replace('#', '').isdigit()) and not position):
                        continue
                    if name and name.lower() == "name" and not position:
                        continue
                        
                    if name:
                        players.append({
                            'name': name,
                            'position': position,
                            'country': country_code,
                            'team_abbr': team_abbr  # Use the corrected team abbreviation
                        })
    
    # Additional filtering to ensure no numerical-only names in final output
    filtered_players = []
    for player in players:
        name = player['name']
        # Skip if name is only numbers, just a # followed by numbers, or literally "name"
        if ((name.isdigit() or (name.startswith('#') and name[1:].isdigit())) and not player['position']) or (name.lower() == "name" and not player['position']):
            continue
        filtered_players.append(player)
    
    return filtered_players

def get_teams_df():
    url = f'{CHAMPIONSHIP_URL}/teams'
    session = make_session()
    response = session.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    team_links = soup.find_all('a', class_='s-country-title')
    team_data = []
    
    # Create mapping of country names to abbreviations used in match_urls.csv
    country_abbr_map = {
        'Austria': 'AUT', 
        'Switzerland': 'SUI', 
        'Norway': 'NOR',
        'Finland': 'FIN', 
        'Czech Republic': 'CZE', 
        'Slovakia': 'SVK', 
        'Germany': 'GER', 
        'Sweden': 'SWE', 
        'United States': 'USA',
        'Canada': 'CAN', 
        'Great Britain': 'GBR', 
        'Kazakhstan': 'KAZ',
        'France': 'FRA', 
        'Denmark': 'DEN', 
        'Latvia': 'LAT', 
        'Poland': 'POL'
    }
    
    # Correction mapping for any inconsistent team codes from the IIHF website
    team_corrections = {
        'AUS': 'AUT',  # Australia → Austria
        'GRE': 'GBR',  # Greece → Great Britain
        'SWI': 'SUI',  # Switzerland
        'SLO': 'SVK',  # Slovakia
        'UNI': 'USA'   # United States
    }
    
    for link in team_links:
        if link.has_attr('href'):
            country_name = link.text.strip()
            
            # Use predefined abbreviation if available
            team_abbr = country_abbr_map.get(country_name)
            
            # If not in mapping, extract from URL or use alternative methods
            if not team_abbr:
                # Extract the country code from the URL - typically contains 3-letter code
                href = link['href']
                code_match = re.search(r'/([A-Z]{3})$', href)
                if code_match:
                    country_code = code_match.group(1)
                    team_abbr = team_corrections.get(country_code, country_code)
                
                # If code not in URL, try to get it from team_img tag
                if not team_abbr:
                    img = link.find_parent().find('img', class_='s-team-img')
                    if img and 'alt' in img.attrs:
                        code_match = re.search(r'([A-Z]{3})', img['alt'])
                        if code_match:
                            country_code = code_match.group(1)
                            team_abbr = team_corrections.get(country_code, country_code)
                
                # If still no code, use first 3 letters of the country name
                if not team_abbr:
                    team_abbr = country_name[:3].upper()
                    team_abbr = team_corrections.get(team_abbr, team_abbr)
            
            # Get the raw country code for backward compatibility
            country_code = None
            href = link['href']
            code_match = re.search(r'/([A-Z]{3})$', href)
            if code_match:
                country_code = code_match.group(1)
            if not country_code:
                img = link.find_parent().find('img', class_='s-team-img')
                if img and 'alt' in img.attrs:
                    code_match = re.search(r'([A-Z]{3})', img['alt'])
                    if code_match:
                        country_code = code_match.group(1)
            if not country_code:
                country_code = country_name[:3].upper()
            
            # Apply corrections to country code if needed
            country_code = team_corrections.get(country_code, country_code)
                
            team_data.append({
                'country_name': country_name,
                'country': country_code,
                'team_abbr': team_abbr,  # Store the corrected team abbreviation
                'team_url': f"https://www.iihf.com{link['href']}"
            })
            print(f"Team: {country_name}, Code: {country_code}, Abbr: {team_abbr}")
            
    return pd.DataFrame(team_data)

def upload_to_spreadsheets(df):
    """
    Upload the player data to all configured spreadsheets.
    Creates or replaces the "Lineups" sheet in each spreadsheet.
    
    Args:
        df: DataFrame containing the player data
    """
    print(f"\nUploading data to {len(SPREADSHEETS)} spreadsheets...")
    
    # Connect to Google Sheets
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SHEETS_SCOPE)
    client = gspread.authorize(credentials)
    
    for owner_name, spreadsheet_id in SPREADSHEETS.items():
        try:
            print(f"\nProcessing {owner_name}'s spreadsheet...")
            
            # Open spreadsheet
            spreadsheet = client.open_by_key(spreadsheet_id)
            
            # Check if the Lineups sheet already exists and delete it
            try:
                existing_worksheet = spreadsheet.worksheet(LINEUPS_SHEET)
                spreadsheet.del_worksheet(existing_worksheet)
                print(f"  Removed existing '{LINEUPS_SHEET}' sheet")
            except gspread.exceptions.WorksheetNotFound:
                pass  # No existing sheet to delete
            
            # Create new worksheet and add data
            rows = df.shape[0] + 1  # +1 for header
            cols = df.shape[1]
            
            # Create new worksheet with appropriate dimensions
            worksheet = spreadsheet.add_worksheet(title=LINEUPS_SHEET, rows=rows, cols=cols)
            
            # Convert DataFrame to list of lists for upload
            values = [df.columns.tolist()] + df.values.tolist()
            
            # Update cells
            worksheet.update(values, value_input_option='USER_ENTERED')
            
            print(f"  Successfully uploaded {df.shape[0]} rows to '{LINEUPS_SHEET}' in {owner_name}'s spreadsheet")
            
        except Exception as e:
            print(f"  Error uploading to {owner_name}'s spreadsheet: {str(e)}")

def scrape_and_process():
    """Main function to scrape team data and process players"""
    print("Fetching team data from IIHF website...")
    df_teams = get_teams_df()
    print(f"Found {len(df_teams)} teams")
    
    all_players = []
    for _, row in df_teams.iterrows():
        print(f"Scraping players from {row['country_name']} ({row['team_abbr']})...")
        players = extract_players_from_team_page(row['team_url'], row['country'], row['team_abbr'])
        all_players.extend(players)
        print(f"  Added {len(players)} players")

    # Create and filter players DataFrame
    print("\nCreating final player dataset...")
    df_players = pd.DataFrame(all_players)
    # Final filter to remove any remaining numerical entries or literal "name" entries
    df_players = df_players[~(((df_players['name'].str.replace('#', '').str.isdigit()) | 
                            (df_players['name'].str.lower() == "name")) & 
                            df_players['position'].isna())]
    
    # Save to CSV
    df_players.to_csv(LINEUPS_CSV, index=False)
    print(f"Lineups saved to {LINEUPS_CSV} with {len(df_players)} total players")
    
    # Upload to all spreadsheets
    upload_to_spreadsheets(df_players)
    
    return df_players

if __name__ == "__main__":
    df_players = scrape_and_process()