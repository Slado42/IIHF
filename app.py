import pandas as pd
import gspread
import argparse
from gspread_dataframe import set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials
from gspread.exceptions import WorksheetNotFound
from match_stats_scraper import extract_all_stats
from config import CREDENTIALS_PATH, SHEETS_SCOPE

def process_match(day_number, url_playbyplay, url_statistics):
    """
    Process a specific match and add its stats to the appropriate day worksheet.
    
    Args:
        day_number: The day number of the championship (for worksheet name)
        url_playbyplay: URL for the play-by-play data
        url_statistics: URL for the statistics data
    
    Returns:
        True if successful, False otherwise
    """
    # Create worksheet name from day number
    worksheet_name = f"Day {day_number}"
    
    # Authenticate and connect to Google Sheets
    scope = SHEETS_SCOPE
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
    client = gspread.authorize(credentials)
    
    # Open the Google Spreadsheet by name or ID
    try:
        spreadsheet = client.open("IIHF")
        print(f"Connected to IIHF spreadsheet")
    except Exception as e:
        print(f"Error opening spreadsheet: {str(e)}")
        return False
    
    # Extract stats for this match
    try:
        print(f"Extracting stats from: {url_statistics}")
        stats_df = extract_all_stats(url_playbyplay, url_statistics)
        stats_df = stats_df.drop(columns=['Event'])
        print(f"Successfully extracted stats for {len(stats_df)} players")
    except Exception as e:
        print(f"Error extracting match stats: {str(e)}")
        return False
    
    try:
        # Attempt to open existing worksheet
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        # Append new data without headers
        worksheet.append_rows(stats_df.values.tolist(), value_input_option="USER_ENTERED")
        print(f"Appended {len(stats_df)} rows to existing worksheet: {worksheet_name}")

    except WorksheetNotFound:
        # Create new worksheet with headers
        worksheet = spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=stats_df.shape[0] + 1,  # Rows: data + header
            cols=stats_df.shape[1]
        )
        set_with_dataframe(worksheet, stats_df)
        print(f"Created new worksheet '{worksheet_name}' with {len(stats_df)} entries")
    
    print(f"DataFrame successfully added to sheet: {worksheet_name}")
    return True

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Process IIHF match data and update Google Sheets.')
    parser.add_argument('--day', type=int, help='Day number of the championship')
    parser.add_argument('--playbyplay', type=str, help='URL for play-by-play data')
    parser.add_argument('--statistics', type=str, help='URL for statistics data')
    
    args = parser.parse_args()
    
    # If arguments provided, use them
    if args.day and args.playbyplay and args.statistics:
        return process_match(args.day, args.playbyplay, args.statistics)
    else:
        # Legacy behavior: use hardcoded test data from match_urls.csv
        print("No command-line arguments provided. Using test match data.")
        
        # Read data from CSV file
        match_urls_df = pd.read_csv("match_urls.csv")
        
        # Using a specific test row
        test_row = 2
        url_playbyplay = list(match_urls_df['url_playbyplay'])[test_row]
        url_statistics = list(match_urls_df['url_statistics'])[test_row]
        day_number = list(match_urls_df['Day'])[test_row]
        
        return process_match(day_number, url_playbyplay, url_statistics)

if __name__ == "__main__":
    main()
