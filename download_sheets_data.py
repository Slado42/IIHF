import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os
from config import CREDENTIALS_PATH, SHEETS_SCOPE, SPREADSHEETS, TEST_SHEET

def download_sheet_data():
    """
    Download data from sheets named 'test' from multiple Google Spreadsheets.
    Uses the same service account credentials as in app.py.
    Returns a single DataFrame with all data and owner information.
    """
    # Authenticate and connect to Google Sheets
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SHEETS_SCOPE)
    client = gspread.authorize(credentials)
    
    # Create a list to store DataFrames from each source
    all_dfs = []
    
    # Process each spreadsheet
    for source_name, spreadsheet_id in SPREADSHEETS.items():
        try:
            # Open the spreadsheet by ID
            spreadsheet = client.open_by_key(spreadsheet_id)
            
            # Try to open the "test" sheet
            try:
                worksheet = spreadsheet.worksheet(TEST_SHEET)
                
                # Get all values from the worksheet
                data = worksheet.get_all_records()
                
                # Convert to DataFrame and add owner column
                if data:
                    df = pd.DataFrame(data)
                    df.insert(0, 'Owner', source_name)  # Add owner as the first column
                    all_dfs.append(df)
                    print(f"Successfully downloaded data from '{source_name}' spreadsheet")
                else:
                    print(f"Sheet '{TEST_SHEET}' in '{source_name}' spreadsheet is empty")
                
            except gspread.exceptions.WorksheetNotFound:
                print(f"Sheet '{TEST_SHEET}' not found in '{source_name}' spreadsheet")
                
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"Could not open spreadsheet for '{source_name}'. Check if the ID is correct and the service account has access.")
        except Exception as e:
            print(f"Error accessing '{source_name}' spreadsheet: {str(e)}")
    
    # Combine all DataFrames into a single DataFrame
    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        print(f"\nCombined data into a single DataFrame with {combined_df.shape[0]} rows and {combined_df.shape[1]} columns")
        return combined_df
    else:
        print("No data was downloaded from any spreadsheet")
        return pd.DataFrame()

if __name__ == "__main__":
    # Download and combine all sheet data
    combined_data = download_sheet_data()
    
    # Print the combined dataframe
    if not combined_data.empty:
        print("\nPreview of combined data:")
        print(combined_data.head())
        
        # Print a summary by owner
        print("\nData summary by owner:")
        for owner, group in combined_data.groupby('Owner'):
            print(f"{owner}: {group.shape[0]} rows")