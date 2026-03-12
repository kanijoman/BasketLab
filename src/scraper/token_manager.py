"""Token management with caching."""

import re
import requests
from bs4 import BeautifulSoup
from typing import Optional
from cachetools import TTLCache

from .constants import MATCH_PAGE_URL, HTML_HEADERS, DEFAULT_TIMEOUT, TOKEN_CACHE_HOURS


class TokenManager:
    """Manages authentication tokens with a TTL-based cache."""

    def __init__(self):
        """Initialize token manager with a TTL cache (auto-expires stale tokens)."""
        self.token_cache: TTLCache = TTLCache(maxsize=256, ttl=TOKEN_CACHE_HOURS * 3600)

    def get_token(self, match_code: str, session: requests.Session) -> Optional[str]:
        """
        Get authentication token for a match, using cache if available.

        Args:
            match_code: Match identifier
            session: Requests session

        Returns:
            Token string or None if not found
        """
        cached = self.token_cache.get(match_code)
        if cached:
            return cached

        # Fetch and cache a new token
        token = self._fetch_token_from_page(match_code, session)
        if token:
            self.token_cache[match_code] = token

        return token

    def invalidate_token(self, match_code: str):
        """
        Invalidate cached token for a match.

        Args:
            match_code: Match identifier
        """
        self.token_cache.pop(match_code, None)

    def _fetch_token_from_page(self, match_code: str, session: requests.Session) -> Optional[str]:
        """
        Fetch token from match page headers or HTML.

        Args:
            match_code: Match identifier
            session: Requests session

        Returns:
            Token string or None if not found
        """
        url = MATCH_PAGE_URL.format(match_code=match_code)

        try:
            response = session.get(url, timeout=DEFAULT_TIMEOUT, headers=HTML_HEADERS)
            response.raise_for_status()

            # Try to get token from Authorization header
            token = self._extract_token_from_header(response)
            if token:
                return token

            # Parse HTML to find token
            soup = BeautifulSoup(response.text, "html.parser")

            # Try to find token in script tags
            token = self._extract_token_from_scripts(soup)
            if token:
                return token

            # Try to find token in hidden input fields
            token = self._extract_token_from_inputs(soup)
            if token:
                return token

            # Try to find token in meta tags
            token = self._extract_token_from_meta(soup)
            if token:
                return token

            print(f"[TokenManager] No token found for match {match_code}")
            return None

        except requests.RequestException as e:
            print(f"[TokenManager] Failed to fetch token for match {match_code}: {e}")
            return None

    def _extract_token_from_header(self, response: requests.Response) -> Optional[str]:
        """Extract token from Authorization header."""
        if "Authorization" in response.headers:
            auth_header = response.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
        return None

    def _extract_token_from_scripts(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract token from script tags."""
        pattern = r'Bearer\s+([A-Za-z0-9\-_\.]+)|token\s*[:=]\s*[\'"]?([A-Za-z0-9\-_\.]+)[\'"]?|\{[^}]*"token"\s*:\s*"([A-Za-z0-9\-_\.]+)"'

        for script in soup.find_all("script"):
            if script.string:
                match = re.search(pattern, script.string)
                if match:
                    return next(g for g in match.groups() if g)
        return None

    def _extract_token_from_inputs(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract token from hidden input fields."""
        for input_tag in soup.find_all("input", type="hidden"):
            value = input_tag.get("value", "")
            # JWT tokens typically start with "eyJhbGci" (base64 encoded {"alg")
            if value.startswith("eyJhbGci"):
                return value
        return None

    def _extract_token_from_meta(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract token from meta tags."""
        pattern = r'Bearer\s+([A-Za-z0-9\-_\.]+)|([A-Za-z0-9\-_\.]+)'

        for meta in soup.find_all("meta", attrs={"name": re.compile(r'token', re.I)}):
            content = meta.get("content", "")
            if content:
                match = re.search(pattern, content)
                if match:
                    return match.group(1) or match.group(2)
        return None
