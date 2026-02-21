#!/usr/bin/env python3
"""
Script to automatically run app.py for today's IIHF matches that started less than an hour ago.
The script will:
1. Check today's date
2. Find matches scheduled for today in match_urls.csv
3. Filter for matches that started less than an hour ago
4. Run app.py for each relevant match, adding data to the correct "Day X" sheet

This script can be scheduled to run every hour (e.g., via cron job) to automatically
process new matches as they start.
"""

import pandas as pd
import subprocess
from datetime import datetime, timedelta
import os
import sys
import argparse
import logging
from config import MATCH_URLS_CSV

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("match_processor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Process IIHF matches that started recently.')
    parser.add_argument('--hours', type=float, default=5.0, 
                        help='Process matches that started within this many hours (default: 5.0)')
    parser.add_argument('--test', action='store_true', 
                        help='Run in test mode (print actions without executing app.py)')
    parser.add_argument('--date', type=str, 
                        help='Override date (format: DD MMM, e.g., "10 May")')
    args = parser.parse_args()

    logger.info(f"Running automatic match data processing at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load match data
    try:
        match_urls_df = pd.read_csv(MATCH_URLS_CSV)
        logger.info(f"Loaded {len(match_urls_df)} matches from {MATCH_URLS_CSV}")
    except Exception as e:
        logger.error(f"Error loading match data: {str(e)}")
        return
    
    # Get current date and time
    now = datetime.now()
    current_year = now.year
    
    # Extract today's matches (or override date if provided)
    if args.date:
        today_str = args.date
        logger.info(f"Using override date: {today_str}")
    else:
        today_str = now.strftime("%d %b").lstrip("0")  # Format like "10 May" (without leading 0)
        logger.info(f"Using today's date: {today_str}")
    
    todays_matches = match_urls_df[match_urls_df['date'] == today_str].copy()
    
    if todays_matches.empty:
        logger.info(f"No matches scheduled for {today_str}")
        return
    
    logger.info(f"Found {len(todays_matches)} matches scheduled for {today_str}")
    
    # Convert match times to datetime objects for comparison
    try:
        todays_matches['datetime'] = todays_matches.apply(
            lambda row: datetime.strptime(f"{row['date']} {current_year} {row['time']}", "%d %b %Y %H:%M"),
            axis=1
        )
    except ValueError as e:
        logger.error(f"Error parsing date/time: {e}")
        logger.error("Ensure date format in CSV is 'DD MMM' (e.g., '10 May') and time format is 'HH:MM'")
        return
    
    # Filter for matches that started less than X hours ago
    hours_ago = now - timedelta(hours=args.hours)
    recent_matches = todays_matches[todays_matches['datetime'] > hours_ago]
    recent_matches = recent_matches[recent_matches['datetime'] <= now]
    
    if recent_matches.empty:
        logger.info(f"No matches started within the last {args.hours} hour(s)")
        return
    
    logger.info(f"Found {len(recent_matches)} matches that started within the last {args.hours} hour(s):")
    
    # Process each recent match
    for _, match in recent_matches.iterrows():
        day_number = match['Day']
        url_playbyplay = match['url_playbyplay']
        url_statistics = match['url_statistics']
        match_time = match['time']
        
        logger.info(f"\nProcessing match at {match_time} (Day {day_number}):")
        logger.info(f"  Play-by-play URL: {url_playbyplay}")
        logger.info(f"  Statistics URL: {url_statistics}")
        
        # Skip invalid URLs
        if not url_playbyplay.startswith('http') or not url_statistics.startswith('http'):
            logger.warning(f"  Skipping match with invalid URLs")
            continue
        
        # Run app.py with parameters for this match
        cmd = [
            sys.executable, 
            "app.py",
            "--day", str(day_number),
            "--playbyplay", url_playbyplay,
            "--statistics", url_statistics
        ]
        
        if args.test:
            logger.info(f"  TEST MODE: Would execute: {' '.join(cmd)}")
        else:
            try:
                logger.info(f"  Executing app.py...")
                result = subprocess.run(cmd, check=True, capture_output=True, text=True)
                logger.info(f"  Success: {result.stdout.strip()}")
            except subprocess.CalledProcessError as e:
                logger.error(f"  Error processing match: {e}")
                logger.error(f"  Error details: {e.stderr}")

if __name__ == "__main__":
    main()