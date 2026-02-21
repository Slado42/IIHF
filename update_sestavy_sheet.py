import pandas as pd
import gspread
import numpy as np
from oauth2client.service_account import ServiceAccountCredentials
from download_sheets_data import download_sheet_data
from config import CREDENTIALS_PATH, SHEETS_SCOPE, SESTAVY_SHEET

def update_sestavy_sheet():
    """
    Updates the "Sestavy" sheet in the Google Spreadsheet with data from download_sheet_data.py,
    but only writes to cells that are currently empty.
    """
    # Get the combined data from the download_sheets_data function
    print("Downloading data from source spreadsheets...")
    combined_data = download_sheet_data()
    
    if combined_data is None or combined_data.empty:
        print("No data to update. Exiting.")
        return
    
    # Add the "Owner-Sestava" column after Owner and Sestava columns
    if 'Owner' in combined_data.columns and 'Sestava' in combined_data.columns:
        print("Creating 'Owner-Sestava' column...")
        combined_data['Owner-Sestava'] = combined_data['Owner'] + '-' + combined_data['Sestava']
        
        # Reorder columns to place Owner-Sestava right after Owner and Sestava
        owner_idx = combined_data.columns.get_loc('Owner')
        sestava_idx = combined_data.columns.get_loc('Sestava')
        last_idx = max(owner_idx, sestava_idx) + 1
        
        # Create new column order
        columns = list(combined_data.columns)
        owner_sestava_idx = columns.index('Owner-Sestava')
        columns.pop(owner_sestava_idx)  # Remove from current position
        
        # Insert after Owner and Sestava
        columns.insert(last_idx, 'Owner-Sestava')
        combined_data = combined_data[columns]
    else:
        print("Warning: 'Owner' or 'Sestava' columns not found. Cannot create 'Owner-Sestava' column.")
    
    print(f"Downloaded data with {combined_data.shape[0]} rows and {combined_data.shape[1]} columns")
    print(f"Column names: {combined_data.columns.tolist()}")
    print(f"First few rows: \n{combined_data.head(3)}")
    
    # Authenticate and connect to Google Sheets using the same credentials as in app.py
    print("Connecting to Google Sheets...")
    scope = SHEETS_SCOPE
    credentials = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, scope)
    client = gspread.authorize(credentials)
    
    # Open the target spreadsheet
    try:
        spreadsheet = client.open("IIHF")
        print(f"Successfully opened 'IIHF' spreadsheet")
    except Exception as e:
        print(f"Error opening spreadsheet: {str(e)}")
        return
    
    # Find or create the "Sestavy" worksheet
    try:
        sestavy_worksheet = spreadsheet.worksheet(SESTAVY_SHEET)
        print(f"Found existing '{SESTAVY_SHEET}' worksheet")
    except gspread.exceptions.WorksheetNotFound:
        print(f"'{SESTAVY_SHEET}' worksheet not found, creating a new one...")
        try:
            sestavy_worksheet = spreadsheet.add_worksheet(
                title=SESTAVY_SHEET,
                rows=max(1000, combined_data.shape[0] + 5),  # Create a large sheet to accommodate future updates
                cols=combined_data.shape[1] + 5
            )
            print(f"Successfully created '{SESTAVY_SHEET}' worksheet")
        except Exception as e:
            print(f"Error creating worksheet: {str(e)}")
            return
    
    # Get worksheet dimensions for reference
    worksheet_row_count = sestavy_worksheet.row_count
    worksheet_col_count = sestavy_worksheet.col_count
    try:
        existing_data = sestavy_worksheet.get_all_values()
        existing_rows = len(existing_data)
        print(f"Retrieved {existing_rows} existing rows from 'Sestavy' worksheet")
    except Exception as e:
        print(f"Error getting worksheet data: {str(e)}")
        return
    
    # Get worksheet dimensions through alternative method
    try:
        # Use get_worksheet directly which returns the worksheet metadata
        worksheet_info = spreadsheet.worksheet("Sestavy")
        # This will get the total row count
        worksheet_row_count = worksheet_info.row_count
        worksheet_col_count = worksheet_info.col_count
        print(f"Worksheet has {worksheet_row_count} total rows and {worksheet_col_count} columns available")
    except Exception as e:
        print(f"Error getting worksheet dimensions: {str(e)}")
        # Default to a reasonable size if we can't get the actual dimensions
        worksheet_row_count = max(1000, existing_rows * 2)
        print(f"Using default worksheet size: {worksheet_row_count} rows")
    
    # If first time setup or not enough rows
    if existing_rows == 0 or worksheet_row_count < combined_data.shape[0] + 10:
        print("Setting up sheet structure...")
        headers = combined_data.columns.tolist()
        
        try:
            # Resize the sheet if needed to accommodate our data
            if worksheet_row_count < combined_data.shape[0] + 10:
                sestavy_worksheet.resize(rows=max(1000, combined_data.shape[0] * 2))
                worksheet_row_count = max(1000, combined_data.shape[0] * 2)
                print(f"Resized sheet to {worksheet_row_count} rows")
            
            # If completely empty, add headers
            if existing_rows == 0:
                sestavy_worksheet.append_row(headers)
                print(f"Added headers: {headers}")
                
                # Refresh our view of the data
                existing_data = sestavy_worksheet.get_all_values()
                existing_rows = len(existing_data)
        except Exception as e:
            print(f"Error setting up sheet: {str(e)}")
            return
    
    # Get existing headers
    if existing_rows > 0:
        existing_headers = existing_data[0]
        print(f"Existing headers: {existing_headers}")
        
        # Check if Owner-Sestava header needs to be added to the worksheet
        if 'Owner-Sestava' not in existing_headers and 'Owner-Sestava' in combined_data.columns:
            print("Adding 'Owner-Sestava' header to worksheet...")
            
            # Try to place after Owner and Sestava columns if they exist
            owner_col = -1
            sestava_col = -1
            
            if 'Owner' in existing_headers:
                owner_col = existing_headers.index('Owner')
            if 'Sestava' in existing_headers:
                sestava_col = existing_headers.index('Sestava') 
            
            insert_col = max(owner_col, sestava_col) + 2  # 1-indexed, plus 1 more for after
            if owner_col == -1 and sestava_col == -1:
                # If neither column exists, add to the end
                insert_col = len(existing_headers) + 1
            
            # Insert the new header
            cell = gspread.utils.rowcol_to_a1(1, insert_col)
            sestavy_worksheet.update(cell, 'Owner-Sestava')
            
            # Shift other headers if needed
            if insert_col <= len(existing_headers):
                # Get values to the right
                for col in range(len(existing_headers), insert_col - 1, -1):
                    # Move each column one to the right
                    from_cell = gspread.utils.rowcol_to_a1(1, col)
                    to_cell = gspread.utils.rowcol_to_a1(1, col + 1)
                    sestavy_worksheet.update(to_cell, existing_headers[col-1])
            
            # Update our local headers
            existing_headers.insert(insert_col - 1, 'Owner-Sestava')
            print(f"Added 'Owner-Sestava' header at column {insert_col}")
            
            # Refresh our data view
            existing_data = sestavy_worksheet.get_all_values()
        
        # Verify headers match what we expect
        for header in combined_data.columns:
            if header not in existing_headers:
                print(f"Warning: Header '{header}' not found in the existing sheet")
    else:
        existing_headers = []
    
    # Convert DataFrame to values for processing
    # Handle NaN values by converting them to empty strings
    combined_data_values = combined_data.fillna('').replace([np.nan], [''])
    
    # Prepare for cell-by-cell updates (only updating empty cells)
    cells_to_update = []
    
    # For each row in our data, we need to find or create cells in the spreadsheet
    print("Checking for empty cells to update...")
    update_count = 0
    
    # Determine the starting row for updates
    # If header only, start at row 2 (1-indexed), otherwise use the first empty row
    start_row = 2  # Start after header (1-indexed)
    
    # Process each cell in the combined data
    for idx, (_, row_data) in enumerate(combined_data_values.iterrows()):
        target_row = start_row + idx
        
        # Check if we're trying to update beyond the worksheet's capacity
        if target_row > worksheet_row_count:
            print(f"Warning: Data row {idx} exceeds worksheet capacity ({worksheet_row_count} rows). Resizing...")
            # Resize the sheet to accommodate more data
            sestavy_worksheet.resize(rows=target_row + 100)  # Add some buffer
            worksheet_row_count = target_row + 100
            print(f"Resized sheet to {worksheet_row_count} rows")
            
        for col_name in combined_data_values.columns:
            if col_name in existing_headers:
                col_idx = existing_headers.index(col_name)
                
                # Check if cell is empty - but be careful about accessing beyond existing data
                cell_is_empty = True
                if idx + 1 < existing_rows:  # If we have data for this row
                    try:
                        existing_value = existing_data[idx + 1][col_idx]  # +1 for header row
                        cell_is_empty = existing_value.strip() == ''
                    except IndexError:
                        # If this cell doesn't exist in our data view, it's empty
                        cell_is_empty = True
                
                # Only update if the cell is empty
                if cell_is_empty:
                    value = row_data[col_name]
                    
                    # Convert numpy types to native Python types for JSON compatibility
                    if isinstance(value, (np.int64, np.int32, np.float64, np.float32)):
                        value = value.item()
                    
                    # Prepare cell update
                    cell_notation = gspread.utils.rowcol_to_a1(target_row, col_idx + 1)  # +1 because columns are 1-indexed
                    cells_to_update.append({
                        'range': cell_notation,
                        'values': [[value]]
                    })
                    update_count += 1
        
        # Progress reporting
        if (idx + 1) % 10 == 0 or idx == len(combined_data_values) - 1:
            print(f"Processed {idx + 1}/{len(combined_data_values)} rows...")
    
    # Execute batch updates if we have cells to update
    if cells_to_update:
        print(f"Updating {len(cells_to_update)} empty cells...")
        try:
            # Split updates into smaller batches to avoid API limits
            batch_size = 10
            for i in range(0, len(cells_to_update), batch_size):
                current_batch = cells_to_update[i:i + batch_size]
                sestavy_worksheet.batch_update(current_batch)
                print(f"Batch {i // batch_size + 1}/{(len(cells_to_update) + batch_size - 1) // batch_size} completed")
            
            print(f"Successfully updated {len(cells_to_update)} previously empty cells")
        except Exception as e:
            print(f"Error during batch update: {str(e)}")
            print(f"Error details: {str(e)}")
    else:
        print("No empty cells found that need updating")
    
    print("Completed updating 'Sestavy' sheet.")

if __name__ == "__main__":
    update_sestavy_sheet()