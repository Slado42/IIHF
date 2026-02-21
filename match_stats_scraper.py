import requests
from bs4 import BeautifulSoup
import pandas as pd
from other_stats_scraper_selenium import extract_other_stats

# URL of the IIHF website page you want to scrape
#url = 'https://www.iihf.com/en/events/2024/wm20/gamecenter/statistics/42153/1-svk-vs-cze'

def extract_all_stats(url_playbyplay, url_statistics):
    # Send a GET request to the URL
    response = requests.get(url_statistics)

    # Check if the request was successful
    if response.status_code == 200:
        # Parse the HTML content of the page
        soup = BeautifulSoup(response.content, 'html.parser')

        teams = ['s-team--home', 's-team--away']
        player_stats_names = {
                                'Position': 's-cell--pos',
                                'Goals': 's-cell--g',
                                'Assists': 's-cell--a',
                                'Points': 's-cell--p',
                                'Penalty Minutes': 's-cell--pim',
                                'Plus Minus': 's-cell--dynamic'}
        goalies_stats_names = {
                                'Goals Against': 's-cell--ga',
                                'Saves': 's-cell--svs'}

        player_list = []
        goalies_list = []
        stats_list = []
        players_df = pd.DataFrame()
        players_away_df = pd.DataFrame()
        goalies_df = pd.DataFrame()
        goalies_away_df = pd.DataFrame()

        for team in teams:
            team_name_soup = soup.find('div', class_=team)
            players_table_soup = team_name_soup.find_all('div', class_='s-tables')[0]
            players_info_soup = players_table_soup.find_all('tbody', class_='s-table__body')[0]
            player_names_soup = players_info_soup.find_all('td', class_='s-cell--name')
            for player in player_names_soup:
                name_of_player = player.find('span', class_='js-table-cell-value').text
                player_list.append(name_of_player)
            if team == 's-team--home':
                players_df['Player'] = player_list
                players_df['Team'] = 'home'
            else:
                players_away_df['Player'] = player_list
                players_away_df['Team'] = 'away'
            player_list = []

            stats_info_soup = players_table_soup.find_all('tbody', class_='s-table__body')[1]
            for stat_name, stat_class in player_stats_names.items():
                player_stats_soup = stats_info_soup.find_all('td', class_=stat_class)
                for stat in player_stats_soup:
                    stats_list.append(stat.find('span', class_='js-table-cell-value').text)
                if team == 's-team--home':
                    players_df[stat_name] = stats_list
                else:
                    players_away_df[stat_name] = stats_list
                stats_list = []

            goalies_table_soup = team_name_soup.find_all('div', class_='s-tables')[1]
            goalies_info_soup = goalies_table_soup.find_all('tbody', class_='s-table__body')[0]
            goalies_names_soup = goalies_info_soup.find_all('td', class_='s-cell--name')
            for goalie in goalies_names_soup:
                name_of_goalie = goalie.find('span', class_='js-table-cell-value').text
                goalies_list.append(name_of_goalie)
            if team == 's-team--home':
                goalies_df['Player'] = goalies_list
            else:
                goalies_away_df['Player'] = goalies_list
            goalies_list = []
            
            stats_goalies_info_soup = goalies_table_soup.find_all('tbody', class_='s-table__body')[1]
            for stat_name, stat_class in goalies_stats_names.items():
                goalies_stats_soup = stats_goalies_info_soup.find_all('td', class_=stat_class)
                for stat in goalies_stats_soup:
                    stats_list.append(stat.find('span', class_='js-table-cell-value').text)
                if team == 's-team--home':
                    goalies_df[stat_name] = stats_list
                else:
                    goalies_away_df[stat_name] = stats_list
                stats_list = []
    else:
        print(f"Failed to retrieve the webpage. Status code: {response.status_code}")

    players_df = pd.concat([players_df, players_away_df], ignore_index=True)
    goalies_df = pd.concat([goalies_df, goalies_away_df], ignore_index=True)
    players_df = players_df.merge(goalies_df, on='Player', how='left').replace("", 0).fillna(0)
    others_df, match_score_home, match_score_away = extract_other_stats(url_playbyplay)
    if not others_df.empty:
        fin_df = players_df.merge(others_df, on='Player', how='left').replace("", 0).fillna(0)
        winners = fin_df[fin_df['Game Winning Goal'] > 0]['Team'].values # Get the team that scored the game-winning goal
        fin_df['Win'] = fin_df['Team'].apply(lambda x: 1 if x in winners else 0) # Create a new column indicating if the player's team won
        fin_df['Event'] = fin_df.pop('Event') # Move Event column to the end
    else:
        fin_df = players_df
        fin_df['Shorthanded Goal'] = 0
        fin_df['Power Play Goal'] = 0
        fin_df['Game Winning Goal'] = 0
        fin_df['Win'] = [match_score_home if x == 'home' else match_score_away for x in fin_df['Team']]
        fin_df['Event'] = 0
    
    # Set all stats for goalies with 0 saves to 0
    goalies_mask = (fin_df['Position'] == 'GK') & (fin_df['Saves'].astype(int) == 0)
    if goalies_mask.any():
        # Get all columns except the first 3 (Player, Team, Position)
        stats_columns = fin_df.columns[3:]
        # Set all stats to 0 for goalies who didn't play (0 saves)
        fin_df.loc[goalies_mask, stats_columns] = 0
        print("Reset stats for goalkeepers with 0 saves to 0")

    print(fin_df)
    return fin_df

extract_all_stats('https://www.iihf.com/en/events/2025/wm/gamecenter/playbyplay/62022/','https://www.iihf.com/en/events/2025/wm/gamecenter/statistics/62022/')