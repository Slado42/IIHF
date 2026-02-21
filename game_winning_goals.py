import pandas as pd
import re

def extract_gwg(df):
    """Dynamically extracts team abbreviations and scores from event data"""
    # Extract team abbreviations from the first event
    first_event = df['Event'].iloc[0]
    team_match = re.search(r'Goal! ([A-Z]{3}) \d+ - \d+ ([A-Z]{3})', first_event)
    
    if not team_match:
        raise ValueError("Could not identify team abbreviations in event format")
    
    home_team, away_team = team_match.groups()
    
    # Create dynamic regex pattern for score extraction
    score_pattern = rf'Goal! {re.escape(home_team)} (\d+) - (\d+) {re.escape(away_team)}'
    
    # Extract scores using the dynamic pattern
    scores = df['Event'].str.extract(score_pattern)
    
    # Convert to integers and handle potential missing values
    df['Home Score'] = scores[0].astype(int)
    df['Away Score'] = scores[1].astype(int)
    df['Home Score MAX'] = df['Home Score'].max()
    df['Away Score MAX'] = df['Away Score'].max()
    df['Home Score LAG'] = df['Home Score'].shift(-1).fillna(0)
    df['Away Score LAG'] = df['Away Score'].shift(-1).fillna(0)
    df['Game Winning Goal'] = (((df['Home Score'] == df['Away Score MAX'] + 1) & (df['Home Score'] > df['Home Score LAG'])) | ((df['Away Score'] == df['Home Score MAX'] + 1) & (df['Away Score'] > df['Away Score LAG']))).astype(int)
    df.drop(columns=['Home Score MAX', 'Away Score MAX', 'Home Score', 'Away Score', 'Home Score LAG', 'Away Score LAG'], inplace=True)
    
    return df