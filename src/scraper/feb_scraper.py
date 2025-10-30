"""FEB website scraper for seasons, groups, and matches."""

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional

from utils import normalize_year, get_form_field_name, get_event_target
from .constants import (
    BASE_URL, SEASON_DROPDOWN_ID, GROUP_DROPDOWN_ID,
    HIDDEN_FIELDS, EXTENDED_TIMEOUT
)
from .web_client import WebClient


class FEBWebScraper:
    """Scrapes FEB website for calendar and match information."""

    def __init__(self, web_client: WebClient):
        """
        Initialize FEB web scraper.

        Args:
            web_client: WebClient instance
        """
        self.web_client = web_client

    def get_page_content(self, year: str) -> Tuple[BeautifulSoup, requests.Session]:
        """
        Fetch and parse webpage content for the given year.

        Args:
            year: Season year

        Returns:
            Tuple of (BeautifulSoup object, requests.Session)

        Raises:
            Exception if page fetch fails
        """
        norm_year = normalize_year(year)
        url = BASE_URL.format(year=norm_year)

        response = self.web_client.get(url, timeout=EXTENDED_TIMEOUT)
        if not response:
            raise Exception(f"Failed to fetch page for year {year}")

        soup = BeautifulSoup(response.text, "html.parser")
        return soup, self.web_client.get_session()

    def get_seasons(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract season options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (season_text, season_value) tuples
        """
        season_dropdown = soup.find("select", {"id": SEASON_DROPDOWN_ID})
        if not season_dropdown:
            return []

        seasons = []
        for option in season_dropdown.find_all("option"):
            text = option.text.strip()
            if text:
                value = option.get("value", text)
                seasons.append((text, value))

        return seasons

    def get_groups(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract group options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (group_text, group_value) tuples
        """
        group_dropdown = soup.find("select", {"id": GROUP_DROPDOWN_ID})
        if not group_dropdown:
            return []

        groups = []
        for option in group_dropdown.find_all("option"):
            text = option.text.strip()
            if text:
                value = option.get("value", "")
                groups.append((text, value))

        return groups

    def select_season(self, session: requests.Session, url: str, season_value: str,
                     hidden_fields: Dict[str, str]) -> Tuple[BeautifulSoup, Dict[str, str]]:
        """
        Perform a POST to select the season.

        Args:
            session: Requests session
            url: Target URL
            season_value: Season value to select
            hidden_fields: ASP.NET hidden form fields

        Returns:
            Tuple of (BeautifulSoup object, updated hidden_fields)

        Raises:
            Exception if POST fails
        """
        form_data = self._build_form_data(
            event_target=get_event_target(SEASON_DROPDOWN_ID),
            hidden_fields=hidden_fields,
            additional_fields={get_form_field_name(SEASON_DROPDOWN_ID): season_value}
        )

        response = self.web_client.post(url, data=form_data, timeout=EXTENDED_TIMEOUT)
        if not response:
            raise Exception("Failed to select season")

        soup = BeautifulSoup(response.text, "html.parser")
        updated_hidden_fields = self.get_hidden_fields(soup)

        return soup, updated_hidden_fields

    def select_group(self, session: requests.Session, url: str, season_value: str,
                    group_value: str, hidden_fields: Dict[str, str]) -> BeautifulSoup:
        """
        Perform a POST to select the group.

        Args:
            session: Requests session
            url: Target URL
            season_value: Season value
            group_value: Group value to select
            hidden_fields: ASP.NET hidden form fields

        Returns:
            BeautifulSoup object of the response

        Raises:
            Exception if POST fails
        """
        form_data = self._build_form_data(
            event_target=get_event_target(GROUP_DROPDOWN_ID),
            hidden_fields=hidden_fields,
            additional_fields={
                get_form_field_name(SEASON_DROPDOWN_ID): season_value,
                get_form_field_name(GROUP_DROPDOWN_ID): group_value
            }
        )

        response = self.web_client.post(url, data=form_data, timeout=EXTENDED_TIMEOUT)
        if not response:
            raise Exception("Failed to select group")

        return BeautifulSoup(response.text, "html.parser")

    def get_hidden_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract ASP.NET hidden fields from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Dictionary of hidden field names and values
        """
        fields = {}
        for field_name in HIDDEN_FIELDS:
            tag = soup.find("input", {"id": field_name})
            if tag and tag.has_attr("value"):
                fields[field_name] = tag["value"]
        return fields

    def get_matches(self, season_value: str, group_value: str, year: str,
                   session: requests.Session) -> List[str]:
        """
        Fetch match codes for the given season and group.

        Args:
            season_value: Season value
            group_value: Group value
            year: Season year
            session: Requests session

        Returns:
            List of match codes
        """
        norm_year = normalize_year(year)
        url = BASE_URL.format(year=norm_year)

        # Get initial page
        soup, _ = self.get_page_content(norm_year)
        hidden_fields = self.get_hidden_fields(soup)

        # Select season
        soup, hidden_fields = self.select_season(session, url, season_value, hidden_fields)

        # Select group
        soup = self.select_group(session, url, season_value, group_value, hidden_fields)

        # Extract match codes
        return self._extract_match_codes(soup)

    def _build_form_data(self, event_target: str, hidden_fields: Dict[str, str],
                        additional_fields: Dict[str, str]) -> Dict[str, str]:
        """Build ASP.NET form data for POST request."""
        form_data = {
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": ""
        }
        form_data.update(hidden_fields)
        form_data.update(additional_fields)
        return form_data

    def _extract_match_codes(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract match codes from the calendar page.

        Args:
            soup: BeautifulSoup object of the calendar page

        Returns:
            List of match codes
        """
        matches = []

        # Find all calendar containers
        for container in soup.find_all("div", class_="tableLayout de dos columnas"):
            for table in container.find_all("table"):
                # Skip header row
                for row in table.find_all("tr")[1:]:
                    match_code = self._extract_match_code_from_row(row)
                    if match_code:
                        matches.append(match_code)

        return matches

    def _extract_match_code_from_row(self, row) -> Optional[str]:
        """
        Extract match code from a table row.

        Args:
            row: BeautifulSoup table row element

        Returns:
            Match code or None if not found
        """
        # Find result cell
        res_cell = row.find("td", class_="resultado")
        if not res_cell:
            return None

        # Find link with match parameter
        link = res_cell.find("a", href=re.compile(r"p=\d+"))
        if not link:
            return None

        # Verify it's a valid score format (e.g., "75 - 68")
        link_text = link.get_text(strip=True)
        if not re.match(r"^\d+\s*-\s*\d+$", link_text):
            return None

        # Extract match code from URL parameter
        match = re.search(r"p=(\d+)", link["href"])
        if match:
            return match.group(1)

        return None
