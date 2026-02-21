"""
Common configuration settings for the IIHF scraper project
"""
import os

# ── Championship URL ──────────────────────────────────────────
# Update this for each new championship.
# Examples:
#   2025 World Championship:    https://www.iihf.com/en/events/2025/wm
#   2026 World Juniors (WM20):  https://www.iihf.com/en/events/2026/wm20
#   2026 World Championship:    https://www.iihf.com/en/events/2026/wm
CHAMPIONSHIP_URL = "https://www.iihf.com/en/events/2026/wm20"

# Credentials path
CREDENTIALS_PATH = "/Users/david.sladek/Documents/repos/playground/IIHF/credentials/iihf-449710-b400daf9886d.json"

# Google Sheets API scope
SHEETS_SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Dictionary of spreadsheet sources with their IDs
SPREADSHEETS = {
    "Ondra": "15vu_UIJfC7eCGcoBOlLttTbINIJpa1e9QrHd77p3hV4",
    "Petr": "16tlMIxcXLMyzOZqh-XA97kJCJR6KslQ3iKOF5t0U7kY",
    "David": "1N_d1i-rSlcVN8wcNrV8-AfpE2K1lChH6gKU11YI5cCk",
    "Vašek": "19fCmOtg4a0dp2S9WRaKBr5e3wJ5KgQZuptPFHZtO8AA",
    "Pavel": "14UWXjzt7_3cirIGH492QkZyQPfiQKR7G2kq6tfe8AUE"
}

# Sheet names
TEST_SHEET = "test"
LINEUPS_SHEET = "Lineups"  # Sheet where lineups data will be stored
SESTAVY_SHEET = "Sestavy"  # Original sheet name for update_sestavy_sheet.py

# Output file paths
MATCH_URLS_CSV = "match_urls.csv"
LINEUPS_CSV = "lineups.csv"