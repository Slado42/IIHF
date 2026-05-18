from pdf_stats_scraper import scrape_game_stats


def extract_all_stats(url_playbyplay, url_statistics, home_team: str, away_team: str):
    """
    Fetch per-player match stats. Delegates to PDF scraper on stats.iihf.com.
    url_playbyplay and url_statistics are accepted for API compatibility but unused.
    """
    return scrape_game_stats(home_team, away_team)
