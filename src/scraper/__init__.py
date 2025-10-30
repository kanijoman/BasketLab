"""FEB web scraper package."""

import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup

from .web_client import WebClient
from .token_manager import TokenManager
from .api_client import FEBApiClient
from .feb_scraper import FEBWebScraper as _FEBWebScraper
from .data_processor import DataProcessor


class FEBWebScraper:
    """Main class for FEB web scraping - backward compatible interface."""

    def __init__(self):
        """Initialize FEB web scraper with all components."""
        self.web_client = WebClient()
        self.token_manager = TokenManager()
        self.api_client = FEBApiClient(self.token_manager, self.web_client)
        self.web_scraper = _FEBWebScraper(self.web_client)

        # For backward compatibility - expose constants
        from .constants import (
            BASE_URL, MATCH_PAGE_URL, BOXSCORE_API_URL,
            SHOTCHART_API_URL, KEYFACTS_API_URL,
            SEASON_DROPDOWN_ID, GROUP_DROPDOWN_ID, DEFAULT_HEADERS
        )
        self.BASE_URL = BASE_URL
        self.MATCH_PAGE_URL = MATCH_PAGE_URL
        self.BOXSCORE_API_URL = BOXSCORE_API_URL
        self.SHOTCHART_API_URL = SHOTCHART_API_URL
        self.KEYFACTS_API_URL = KEYFACTS_API_URL
        self.SEASON_DROPDOWN_ID = SEASON_DROPDOWN_ID
        self.GROUP_DROPDOWN_ID = GROUP_DROPDOWN_ID
        self.HEADERS = DEFAULT_HEADERS

    def get_page_content(self, year: str) -> tuple[BeautifulSoup, requests.Session]:
        """Fetch and parse webpage content for the given year."""
        return self.web_scraper.get_page_content(year)

    def get_seasons(self, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract season options from the page."""
        return self.web_scraper.get_seasons(soup)

    def get_groups(self, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract group options from the page."""
        return self.web_scraper.get_groups(soup)

    def select_season(self, session: requests.Session, url: str, season_value: str,
                     hidden_fields: Dict[str, str]) -> tuple[BeautifulSoup, Dict[str, str]]:
        """Perform a POST to select the season."""
        return self.web_scraper.select_season(session, url, season_value, hidden_fields)

    def select_group(self, session: requests.Session, url: str, season_value: str,
                    group_value: str, hidden_fields: Dict[str, str]) -> BeautifulSoup:
        """Perform a POST to select the group."""
        return self.web_scraper.select_group(session, url, season_value, group_value, hidden_fields)

    def get_hidden_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract hidden fields from the page."""
        return self.web_scraper.get_hidden_fields(soup)

    def fetch_token(self, match_code: str, session: requests.Session) -> Optional[str]:
        """Fetch token from the match page."""
        return self.token_manager.get_token(match_code, session)

    def fetch_shotchart(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """Fetch JSON shotchart data."""
        return self.api_client.fetch_shotchart(match_code, session, token)

    def fetch_playbyplay(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """Fetch JSON playbyplay data."""
        return self.api_client.fetch_playbyplay(match_code, session, token)

    def fetch_boxscore(self, match_code: str, session: requests.Session) -> Optional[Dict]:
        """Fetch and process boxscore data."""
        return self.api_client.fetch_boxscore(match_code, session)

    def get_matches(self, season_value: str, group_value: str, year: str,
                   session: requests.Session) -> List[str]:
        """Fetch match codes for the given season and group."""
        return self.web_scraper.get_matches(season_value, group_value, year, session)


# Re-export for easier imports
__all__ = [
    'FEBWebScraper',
    'WebClient',
    'TokenManager',
    'FEBApiClient',
    'DataProcessor'
]
