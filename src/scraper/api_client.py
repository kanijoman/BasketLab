"""FEB API client for fetching match data."""

import requests
from typing import Optional, Dict, List

from .constants import BOXSCORE_API_URL, SHOTCHART_API_URL, KEYFACTS_API_URL, DEFAULT_HEADERS
from .web_client import WebClient
from .token_manager import TokenManager
from .data_processor import DataProcessor


class FEBApiClient:
    """Client for FEB API endpoints."""

    def __init__(self, token_manager: TokenManager, web_client: WebClient):
        """
        Initialize API client.

        Args:
            token_manager: TokenManager instance
            web_client: WebClient instance
        """
        self.token_manager = token_manager
        self.web_client = web_client
        self.data_processor = DataProcessor()

    def fetch_boxscore(self, match_code: str, session: requests.Session) -> Optional[Dict]:
        """
        Fetch and process complete boxscore data including shotchart and playbyplay.

        Args:
            match_code: Match identifier
            session: Requests session

        Returns:
            Complete boxscore data or None if failed
        """
        token = self.token_manager.get_token(match_code, session)
        if not token:
            return None

        # Fetch boxscore data with retry logic
        url = BOXSCORE_API_URL.format(match_code=match_code)
        headers = {"Authorization": f"Bearer {token}"}

        response = self.web_client.get_with_retry(
            url,
            headers=headers,
            on_401=lambda: self._refresh_token(match_code, session)
        )

        if not response:
            return None

        try:
            data = response.json()
        except ValueError as e:
            return None

        # Process boxscore data
        data = self.data_processor.process_boxscore(data, match_code)
        if not data:
            return None

        # Fetch additional data
        token = self.token_manager.get_token(match_code, session)  # Get fresh token
        if token:
            self._add_shotchart_data(data, match_code, session, token)
            self._add_playbyplay_data(data, match_code, session, token)

        return data

    def fetch_shotchart(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """
        Fetch shotchart data for a match.

        Args:
            match_code: Match identifier
            session: Requests session
            token: Authentication token

        Returns:
            Shotchart data list or None if failed
        """
        return self._fetch_api_data(
            SHOTCHART_API_URL.format(match_code=match_code),
            match_code,
            session,
            token,
            "SHOTCHART"
        )

    def fetch_playbyplay(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """
        Fetch play-by-play data for a match.

        Args:
            match_code: Match identifier
            session: Requests session
            token: Authentication token

        Returns:
            Play-by-play data list or None if failed
        """
        return self._fetch_api_data(
            KEYFACTS_API_URL.format(match_code=match_code),
            match_code,
            session,
            token,
            "PLAYBYPLAY"
        )

    def _fetch_api_data(self, url: str, match_code: str, session: requests.Session,
                       token: str, key: str) -> Optional[List]:
        """
        Fetch data from API endpoint with retry on 401.

        Args:
            url: API endpoint URL
            match_code: Match identifier
            session: Requests session
            token: Authentication token
            key: JSON key to extract from response

        Returns:
            Data list or None if failed
        """
        headers = {"Authorization": f"Bearer {token}"}

        response = self.web_client.get_with_retry(
            url,
            headers=headers,
            on_401=lambda: self._refresh_token(match_code, session)
        )

        if not response:
            return None

        try:
            json_data = response.json()
            return json_data.get(key, [])
        except ValueError as e:
            return None

    def _refresh_token(self, match_code: str, session: requests.Session) -> Optional[str]:
        """
        Refresh token after 401 error.

        Args:
            match_code: Match identifier
            session: Requests session

        Returns:
            New token or None if failed
        """
        self.token_manager.invalidate_token(match_code)
        return self.token_manager.get_token(match_code, session)

    def _add_shotchart_data(self, data: Dict, match_code: str, session: requests.Session, token: str):
        """Add shotchart data to boxscore dictionary."""
        shotchart_data = self.fetch_shotchart(match_code, session, token)
        if shotchart_data is not None:
            data["SHOTCHART"] = shotchart_data

    def _add_playbyplay_data(self, data: Dict, match_code: str, session: requests.Session, token: str):
        """Add play-by-play data to boxscore dictionary."""
        playbyplay_data = self.fetch_playbyplay(match_code, session, token)
        if playbyplay_data is not None:
            data["PLAYBYPLAY"] = playbyplay_data
