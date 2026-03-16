"""FBCYL website scraper for seasons, gender, territory, category, and competitions."""

import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional, Any

from utils import normalize_year, get_form_field_name, get_event_target
from .web_client import WebClient


# FBCYL specific constants
FBCYL_BASE_URL = "https://www.fbcyl.es"
FBCYL_SEARCH_URL = "https://www.fbcyl.es/buscar_competicion"
FBCYL_AJAX_CATEGORIES_URL = "https://www.fbcyl.es/ajax/combo_categories2/{temporada}/{genere}/{territorial}"
FBCYL_AJAX_COMPETITIONS_URL = "https://www.fbcyl.es/ajax/combo_competicions2/{categoria}/{genere}/{territorial}"
FBCYL_API_BASE_URL = "https://esb.optimalwayconsulting.com/fbcyl/1/jR4rgA5K6Chhh5vyfrxo9wTScdg2NT7K"
FBCYL_MATCH_JSON_URL = "https://msstats.optimalwayconsulting.com/v1/fbcyl/getJsonWithMatchMoves/{match_id}"
FBCYL_EXTENDED_TIMEOUT = 30

# FBCYL form field IDs (obtenidos mediante inspección real de la página)
FBCYL_SEASON_DROPDOWN_ID = "temporada"
FBCYL_GENDER_DROPDOWN_ID = "genere"  # Nota: es "genere" no "genero"
FBCYL_TERRITORY_DROPDOWN_ID = "territorial"  # Nota: es "territorial" no "territorio"
FBCYL_CATEGORY_DROPDOWN_ID = "categoria"
FBCYL_COMPETITION_DROPDOWN_ID = "competicio"  # Nota: es "competicio" no "competicion"

# FBCYL usa AJAX/JavaScript para actualizar dropdowns, no ASP.NET ViewState
# Por lo tanto, no necesitamos FBCYL_HIDDEN_FIELDS


class FBCYLWebScraper:
    """Scrapes FBCYL website for competitions and match information."""

    def __init__(self, web_client: WebClient):
        """
        Initialize FBCYL scraper.

        Args:
            web_client: WebClient instance for making HTTP requests
        """
        self.web_client = web_client

    def get_page_content(self) -> Tuple[BeautifulSoup, requests.Session]:
        """
        Fetch and parse initial FBCYL search page.

        Returns:
            Tuple of (BeautifulSoup object, session)

        Raises:
            Exception if page fetch fails
        """
        response = self.web_client.get(FBCYL_SEARCH_URL, timeout=FBCYL_EXTENDED_TIMEOUT)
        if not response:
            raise Exception("Failed to fetch FBCYL page")

        soup = BeautifulSoup(response.content, "html.parser")
        return soup, self.web_client.session

    def get_seasons(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract season/temporada options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (season_text, season_value) tuples
        """
        season_dropdown = soup.find("select", {"id": FBCYL_SEASON_DROPDOWN_ID})
        if not season_dropdown:
            season_dropdown = soup.find("select", {"name": FBCYL_SEASON_DROPDOWN_ID})

        if not season_dropdown:
            return []

        seasons = []
        for option in season_dropdown.find_all("option"):
            text = option.text.strip()
            value = option.get("value", "")
            # Skip placeholder options - check both text and value
            if text and text.lower() not in ["temporada", "seleccionar", "selecciona"] and value and value != "0":
                seasons.append((text, value))

        return seasons

    def get_genders(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract gender/género options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (gender_text, gender_value) tuples
        """
        gender_dropdown = soup.find("select", {"id": FBCYL_GENDER_DROPDOWN_ID})
        if not gender_dropdown:
            gender_dropdown = soup.find("select", {"name": FBCYL_GENDER_DROPDOWN_ID})

        if not gender_dropdown:
            return []

        genders = []
        for option in gender_dropdown.find_all("option"):
            text = option.text.strip()
            value = option.get("value", "")
            # Skip placeholder options
            if text and text.lower() not in ["género", "genero", "seleccionar", "selecciona"] and value:
                genders.append((text, value))

        return genders

    def get_territories(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract territory/territorio options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (territory_text, territory_value) tuples
        """
        territory_dropdown = soup.find("select", {"id": FBCYL_TERRITORY_DROPDOWN_ID})
        if not territory_dropdown:
            territory_dropdown = soup.find("select", {"name": FBCYL_TERRITORY_DROPDOWN_ID})

        if not territory_dropdown:
            return []

        territories = []
        for option in territory_dropdown.find_all("option"):
            text = option.text.strip()
            value = option.get("value", "")
            # Skip placeholder options - value "0" is the placeholder
            if text and text.lower() not in ["territorio", "seleccionar", "selecciona"] and value and value != "0":
                territories.append((text, value))

        return territories

    def get_categories(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract category/categoría options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (category_text, category_value) tuples
        """
        category_dropdown = soup.find("select", {"id": FBCYL_CATEGORY_DROPDOWN_ID})
        if not category_dropdown:
            category_dropdown = soup.find("select", {"name": FBCYL_CATEGORY_DROPDOWN_ID})

        if not category_dropdown:
            return []

        categories = []
        for option in category_dropdown.find_all("option"):
            text = option.text.strip()
            value = option.get("value", "")
            # Skip empty options and placeholders, but keep options with valid values
            if text and text.lower() not in ["categoría", "seleccionar", "selecciona"] and value:
                categories.append((text, value))

        return categories

    def get_competitions(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract competition/competición options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (competition_text, competition_value) tuples
        """
        competition_dropdown = soup.find("select", {"id": FBCYL_COMPETITION_DROPDOWN_ID})
        if not competition_dropdown:
            competition_dropdown = soup.find("select", {"name": FBCYL_COMPETITION_DROPDOWN_ID})

        if not competition_dropdown:
            return []

        competitions = []
        for option in competition_dropdown.find_all("option"):
            text = option.text.strip()
            value = option.get("value", "")
            # Skip empty options and placeholders, but keep options with valid values
            if text and text.lower() not in ["competición / grupo", "competicion", "seleccionar", "selecciona"] and value:
                competitions.append((text, value))

        return competitions

    def fetch_categories_ajax(self, temporada: str, genere: str = "", territorial: str = "0") -> List[Tuple[str, str]]:
        """
        Fetch categories via AJAX based on season, gender, and territory.

        Args:
            temporada: Season value (e.g., "2025" for 2025-2026)
            genere: Gender value ("M", "F", "X", or empty string)
            territorial: Territory value (default "0" for all)

        Returns:
            List of (category_text, category_value) tuples

        Example:
            categories = scraper.fetch_categories_ajax("2025", "M", "1")
        """
        # Build URL with parameters
        url = FBCYL_AJAX_CATEGORIES_URL.format(
            temporada=temporada,
            genere=genere,
            territorial=territorial
        )

        try:
            response = self.web_client.get(url, timeout=FBCYL_EXTENDED_TIMEOUT)
            if not response:
                return []

            # Parse HTML response
            soup = BeautifulSoup(response.content, "html.parser")

            # Find all option elements in the response
            categories = []
            for option in soup.find_all("option"):
                text = option.text.strip()
                value = option.get("value", "")
                # Skip placeholder options
                if text and text.lower() not in ["categoría", "categoria", "seleccionar", "selecciona"] and value:
                    categories.append((text, value))

            return categories

        except Exception as e:
            return []

    def fetch_competitions_ajax(self, categoria: str, genere: str = "", territorial: str = "0") -> List[Tuple[str, str]]:
        """
        Fetch competitions via AJAX based on category, gender, and territory.

        Args:
            categoria: Category value (e.g., "1018")
            genere: Gender value ("M", "F", "X", or empty string)
            territorial: Territory value (default "0" for all)

        Returns:
            List of (competition_text, competition_value) tuples

        Example:
            competitions = scraper.fetch_competitions_ajax("1018", "F", "1")
        """
        # Build URL with parameters
        url = FBCYL_AJAX_COMPETITIONS_URL.format(
            categoria=categoria,
            genere=genere,
            territorial=territorial
        )

        try:
            response = self.web_client.get(url, timeout=FBCYL_EXTENDED_TIMEOUT)
            if not response:
                return []

            # Parse HTML response
            soup = BeautifulSoup(response.content, "html.parser")

            # Find all option elements in the response
            competitions = []
            for option in soup.find_all("option"):
                text = option.text.strip()
                value = option.get("value", "")
                # Skip placeholder options
                if text and text.lower() not in ["competición / grupo", "competicion", "seleccionar", "selecciona"] and value:
                    competitions.append((text, value))

            return competitions

        except Exception as e:
            return []

    def get_hidden_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract hidden form fields (if any).

        Note: FBCYL doesn't use ASP.NET ViewState, but keeping this method
        for compatibility and in case there are other hidden fields.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Dictionary of hidden field names to values (empty for FBCYL)
        """
        # FBCYL uses AJAX/JavaScript, not ASP.NET postback
        # Return empty dict for now
        return {}

    def _build_form_data(self, event_target: str, hidden_fields: Dict[str, str],
                        additional_fields: Dict[str, str]) -> Dict[str, str]:
        """
        Build form data for POST request.

        Note: FBCYL uses AJAX/JavaScript for dropdown updates, not traditional form postback.
        This method is kept for potential future use but may not be needed.

        Args:
            event_target: Event target (not used for FBCYL)
            hidden_fields: Hidden fields (empty for FBCYL)
            additional_fields: Additional form fields to include

        Returns:
            Form data dictionary (just the additional fields for FBCYL)
        """
        # For FBCYL, we likely just need the selection values
        # No ASP.NET postback mechanism
        return additional_fields.copy()

    def select_dropdown_option(self, session: requests.Session, url: str,
                              dropdown_id: str, option_value: str,
                              current_selections: Dict[str, str],
                              hidden_fields: Dict[str, str]) -> Tuple[BeautifulSoup, Dict[str, str]]:
        """
        Select a dropdown option.

        Note: FBCYL uses AJAX to dynamically load dropdown options.
        This method may need to be adapted to call the actual AJAX endpoint
        instead of doing a full page POST.

        Args:
            session: Requests session
            url: Target URL (may need to be AJAX endpoint)
            dropdown_id: ID of the dropdown to modify
            option_value: Value to select
            current_selections: Dictionary of current selections {dropdown_id: value}
            hidden_fields: Hidden form fields (unused for FBCYL)

        Returns:
            Tuple of (BeautifulSoup object, empty dict for hidden_fields)

        Raises:
            Exception if request fails
        """
        # TODO: Implement AJAX call to FBCYL endpoint
        # For now, this is a placeholder that needs to be adapted
        # to the actual AJAX mechanism used by FBCYL

        # The page likely has JavaScript that calls an endpoint like:
        # /api/get_categories?temporada=2024&genere=M&territorial=1

        raise NotImplementedError(
            "FBCYL uses AJAX for dropdown updates. "
            "This method needs to be implemented by reverse-engineering the AJAX calls. "
            "Check browser DevTools Network tab to see the actual endpoints."
        )

    def get_competition_url(self, competition_id: str) -> str:
        """
        Build the URL for a competition page.

        Args:
            competition_id: ID of the competition (value from dropdown)

        Returns:
            Full URL to competition page
        """
        return f"{FBCYL_BASE_URL}/competiciones/resultados/{competition_id}"

    def get_calendar_url(self, competition_id: str, round_number: int = 0) -> str:
        """
        Build the URL for the calendar page of a competition.

        Args:
            competition_id: ID of the competition
            round_number: Round/jornada number (0 = all rounds/jornadas)

        Returns:
            Full URL to calendar page
        """
        # Calendar URL is the competition results URL + /{round_number}
        # Round 0 shows all matches from all rounds
        return f"{FBCYL_BASE_URL}/competiciones/resultados/{competition_id}/{round_number}"

    def get_matches(self, competition_id: str, round_number: int = 0) -> List[str]:
        """
        Fetch match UUIDs from ESB API endpoint.

        Args:
            competition_id: Competition ID (group ID from FBCYL)
            round_number: Round/jornada number (0 = all rounds)

        Returns:
            List of match UUIDs (24-character hex strings)
        """
        # Use getAllGamesByGrupWithMatchRecords endpoint to get ALL played matches
        # The /0 at the end means "all rounds"
        esb_url = f"{FBCYL_API_BASE_URL}/FCBQWeb/getAllGamesByGrupWithMatchRecords/{competition_id}/0"

        response = self.web_client.get(esb_url)
        if not response:
            return []

        try:
            # Decode Base64 response
            json_data = json.loads(base64.b64decode(response.text).decode('utf-8'))

            if json_data.get('result') != 'OK':
                return []

            # Extract match UUIDs from JSON structure
            match_uuids = self._extract_match_uuids_from_json(json_data, round_number)

            return match_uuids

        except Exception as e:
            return []

    def _extract_match_uuids_from_json(self, json_data: Dict[str, Any], round_filter: int = 0) -> List[str]:
        """
        Extract match UUIDs from ESB API JSON response.

        Args:
            json_data: Decoded JSON response from ESB API
            round_filter: Filter by round number (0 = all rounds)

        Returns:
            List of match UUIDs (universallyid field)
        """
        match_uuids = []

        try:
            rounds = json_data.get('messageData', {}).get('rounds', {})

            for round_num, round_data in rounds.items():
                # Skip if filtering by specific round
                if round_filter > 0 and int(round_num) != round_filter:
                    continue

                # Extract matches from this round
                matches = round_data.get('matches', {})
                for match_id, match_data in matches.items():
                    uuid = match_data.get('universallyid')
                    if uuid and len(uuid) == 24:
                        match_uuids.append(uuid)

        except Exception as e:
            pass

        return match_uuids

    def get_match_json_moves(self, match_uuid: str) -> Optional[Dict]:
        """
        Get the match data with play-by-play moves (jugadas).

        Args:
            match_uuid: The match UUID (24-character hex string)

        Returns:
            Dictionary with match data including moves, or None if error
        """
        match_url = f"https://msstats.optimalwayconsulting.com/v1/fbcyl/getJsonWithMatchMoves/{match_uuid}"

        response = self.web_client.get(match_url)
        if not response:
            return None

        try:
            return response.json()
        except Exception as e:
            return None

    def get_match_json_stats(self, match_uuid: str) -> Optional[Dict]:
        """
        Get the match data with statistics.

        Args:
            match_uuid: The match UUID (24-character hex string)

        Returns:
            Dictionary with match statistics data, or None if error
        """
        # IMPORTANT: currentSeason=true parameter is required to get the stats data
        match_url = f"https://msstats.optimalwayconsulting.com/v1/fbcyl/getJsonWithMatchStats/{match_uuid}?currentSeason=true"

        response = self.web_client.get(match_url)
        if not response:
            return None

        try:
            return response.json()
        except Exception as e:
            return None

    def get_match_complete_data(
        self,
        match_uuid: str,
        *,
        league_ctx: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Get complete match data by fetching both moves and stats JSONs.

        Args:
            match_uuid: The match UUID (24-character hex string)
            league_ctx: Optional dict with competition metadata to persist
                alongside the document.  When provided the following keys
                are expected (all strings):
                ``gender``, ``territory``, ``category``,
                ``competition_id``, ``season``.
                Injected as ``_league``, ``_gender``, ``_territory``,
                ``_category``, ``_competition``, ``_season``.

        Returns:
            Dictionary with combined data: {'moves': {...}, 'stats': {...}},
            enriched with ``_*`` metadata fields when *league_ctx* is
            supplied.  Returns ``None`` if both API calls fail.
        """
        moves_data = self.get_match_json_moves(match_uuid)
        stats_data = self.get_match_json_stats(match_uuid)

        if not moves_data and not stats_data:
            return None

        doc: Dict = {
            'uuid': match_uuid,
            'moves': moves_data,
            'stats': stats_data,
        }

        if league_ctx:
            doc["_league"] = "FBCYL"
            doc["_gender"] = league_ctx.get("gender", "")
            doc["_territory"] = league_ctx.get("territory", "")
            doc["_category"] = league_ctx.get("category", "")
            doc["_competition"] = league_ctx.get("competition_id", "")
            doc["_season"] = league_ctx.get("season", "")

        return doc
