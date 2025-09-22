import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from utils import normalize_year, get_form_field_name, get_event_target

class FEBWebScraper:
    """Handles web scraping for the FEB basketball website."""

    BASE_URL = "https://baloncestoenvivo.feb.es/calendario/lf2/9/{year}"
    MATCH_PAGE_URL = "https://baloncestoenvivo.feb.es/partido/{match_code}"
    BOXSCORE_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/BoxScore/{match_code}"
    SHOTCHART_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/ShotChart/{match_code}"
    KEYFACTS_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/KeyFacts/{match_code}"
    SEASON_DROPDOWN_ID = "_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList"
    GROUP_DROPDOWN_ID = "_ctl0_MainContentPlaceHolderMaster_gruposDropDownList"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0.0.0",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
        "Referer": "https://baloncestoenvivo.feb.es/"
    }

    def __init__(self):
        """Initialize with token cache."""
        self.token_cache = {}  # {match_code: (token, expiry_time)}

    def get_page_content(self, year: str) -> tuple[BeautifulSoup, requests.Session]:
        """Fetch and parse webpage content for the given year."""
        norm_year = normalize_year(year)
        url = self.BASE_URL.format(year=norm_year)
        try:
            session = requests.Session()
            response = session.get(url, timeout=15, headers=self.HEADERS)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser"), session
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch {url}: {e}")
            raise

    def get_seasons(self, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract season options from the page."""
        season_dropdown = soup.find("select", {"id": self.SEASON_DROPDOWN_ID})
        return [(opt.text.strip(), opt.get("value", opt.text.strip()))
                for opt in season_dropdown.find_all("option") if opt.text.strip()] if season_dropdown else []

    def get_groups(self, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract group options from the page."""
        group_dropdown = soup.find("select", {"id": self.GROUP_DROPDOWN_ID})
        return [(opt.text.strip(), opt.get("value", ""))
                for opt in group_dropdown.find_all("option") if opt.text.strip()] if group_dropdown else []

    def select_season(self, session: requests.Session, url: str, season_value: str, hidden_fields: Dict[str, str]) -> tuple[BeautifulSoup, Dict[str, str]]:
        """Perform a POST to select the season."""
        form_data = {
            "__EVENTTARGET": get_event_target(self.SEASON_DROPDOWN_ID),
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            get_form_field_name(self.SEASON_DROPDOWN_ID): season_value
        }
        form_data.update(hidden_fields)
        try:
            response = session.post(url, data=form_data, headers=self.HEADERS, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return soup, self.get_hidden_fields(soup)
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to select season: {e}")
            raise

    def select_group(self, session: requests.Session, url: str, season_value: str, group_value: str, hidden_fields: Dict[str, str]) -> BeautifulSoup:
        """Perform a POST to select the group."""
        form_data = {
            "__EVENTTARGET": get_event_target(self.GROUP_DROPDOWN_ID),
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            get_form_field_name(self.SEASON_DROPDOWN_ID): season_value,
            get_form_field_name(self.GROUP_DROPDOWN_ID): group_value
        }
        form_data.update(hidden_fields)
        try:
            response = session.post(url, data=form_data, headers=self.HEADERS, timeout=15)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to select group: {e}")
            raise

    def get_hidden_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract hidden fields from the page."""
        fields = {}
        for hidden in ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__PREVIOUSPAGE"]:
            tag = soup.find("input", {"id": hidden})
            if tag and tag.has_attr("value"):
                fields[hidden] = tag["value"]
        return fields

    def fetch_token(self, match_code: str, session: requests.Session) -> Optional[str]:
        """Fetch token from the match page headers or HTML."""
        if match_code in self.token_cache and self.token_cache[match_code][1] > datetime.now():
            return self.token_cache[match_code][0]
        
        url = self.MATCH_PAGE_URL.format(match_code=match_code)
        headers = self.HEADERS | {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"}
        try:
            response = session.get(url, timeout=10, headers=headers)
            response.raise_for_status()
            token = None
            if "Authorization" in response.headers and response.headers["Authorization"].startswith("Bearer "):
                token = response.headers["Authorization"][7:]
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                for script in soup.find_all("script"):
                    if script.string:
                        match = re.search(r'Bearer\s+([A-Za-z0-9\-_\.]+)|token\s*[:=]\s*[\'"]?([A-Za-z0-9\-_\.]+)[\'"]?|\{[^}]*"token"\s*:\s*"([A-Za-z0-9\-_\.]+)"', script.string)
                        if match:
                            token = next(g for g in match.groups() if g)
                            break
                if not token:
                    for input_tag in soup.find_all("input", type="hidden"):
                        if input_tag.get("value", "").startswith("eyJhbGci"):
                            token = input_tag["value"]
                            break
                if not token:
                    for meta in soup.find_all("meta", attrs={"name": re.compile(r'token', re.I)}):
                        if meta.get("content"):
                            match = re.search(r'Bearer\s+([A-Za-z0-9\-_\.]+)|([A-Za-z0-9\-_\.]+)', meta.get("content"))
                            if match:
                                token = match.group(1) or match.group(2)
                                break
            if token:
                self.token_cache[match_code] = (token, datetime.now() + timedelta(hours=24))
                return token
            print(f"[FEBWebScraper] No token found for match {match_code}")
            return None
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch token for match {match_code}: {e}")
            return None

    def fetch_shotchart(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """Fetch JSON shotchart data for the given match_code."""
        return self._fetch_api_data(self.SHOTCHART_API_URL.format(match_code=match_code), match_code, session, token, "SHOTCHART")

    def fetch_playbyplay(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """Fetch JSON playbyplay data for the given match_code."""
        return self._fetch_api_data(self.KEYFACTS_API_URL.format(match_code=match_code), match_code, session, token, "PLAYBYPLAY")

    def _fetch_api_data(self, url: str, match_code: str, session: requests.Session, token: str, key: str) -> Optional[List]:
        """Helper to fetch JSON data from API with retry on 401."""
        headers = self.HEADERS | {"Authorization": f"Bearer {token}"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json().get(key, [])
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                print(f"[FEBWebScraper] Unauthorized (401) for {key.lower()} {match_code}")
                if match_code in self.token_cache:
                    del self.token_cache[match_code]
                token = self.fetch_token(match_code, session)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        response.raise_for_status()
                        return response.json().get(key, [])
                    except requests.RequestException as retry_e:
                        print(f"[FEBWebScraper] Retry failed for {key.lower()} {match_code}: {retry_e}")
                        return None
                return None
            print(f"[FEBWebScraper] HTTP error for {key.lower()} {match_code}: {e}")
            return None
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch {key.lower()} for match {match_code}: {e}")
            return None

    def _process_boxscore_data(self, data: Dict, match_code: str) -> Optional[Dict]:
        """Process boxscore data to add games_played and win_lose."""
        if not isinstance(data, dict) or "BOXSCORE" not in data or "TEAM" not in data["BOXSCORE"]:
            print(f"[FEBWebScraper] Invalid or missing BOXSCORE.TEAM for match {match_code}")
            return data
        data["HEADER"] = data.get("HEADER", {})
        data["HEADER"]["game_code"] = int(match_code)
        team_list = data["BOXSCORE"]["TEAM"]
        if not isinstance(team_list, list) or len(team_list) != 2:
            print(f"[FEBWebScraper] Invalid TEAM structure for match {match_code}: Expected list of 2 teams")
            return data

        # Add games_played to players
        for team in team_list:
            if not isinstance(team, dict) or "PLAYER" not in team or not isinstance(team["PLAYER"], list):
                print(f"[FEBWebScraper] Invalid PLAYER structure for team {team.get('name', 'Unknown')} in match {match_code}")
                continue
            for player in team["PLAYER"]:
                if not isinstance(player, dict) or "min" not in player or not isinstance(player["min"], str):
                    print(f"[FEBWebScraper] Invalid or missing min for player {player.get('name', 'Unknown')} in match {match_code}")
                    player["games_played"] = 0
                    continue
                try:
                    player["games_played"] = 1 if int(player["min"]) != 0 else 0
                except ValueError:
                    print(f"[FEBWebScraper] Invalid min value for player {player.get('name', 'Unknown')} in match {match_code}: {player['min']}")
                    player["games_played"] = 0

        # Add win_lose to teams
        team1, team2 = team_list
        if not all(isinstance(team, dict) and "TOTAL" in team and isinstance(team["TOTAL"], dict) and "pts" in team["TOTAL"] for team in team_list):
            print(f"[FEBWebScraper] Missing or invalid TOTAL.pts for teams in match {match_code}")
            team1["win_lose"] = team2["win_lose"] = "E"
        else:
            try:
                pts1, pts2 = int(team1["TOTAL"]["pts"]), int(team2["TOTAL"]["pts"])
                team1["win_lose"], team2["win_lose"] = ("W", "L") if pts1 > pts2 else ("L", "W") if pts1 < pts2 else ("E", "E")
            except ValueError:
                print(f"[FEBWebScraper] Invalid pts value for match {match_code}: Team1 pts={team1['TOTAL'].get('pts', 'Missing')}, Team2 pts={team2['TOTAL'].get('pts', 'Missing')}")
                team1["win_lose"] = team2["win_lose"] = "E"

        return data

    def fetch_boxscore(self, match_code: str, session: requests.Session) -> Optional[Dict]:
        """Fetch and process boxscore data, adding game_code, games_played, win_lose, SHOTCHART, and PLAYBYPLAY."""
        token = self.fetch_token(match_code, session)
        if not token:
            print(f"[FEBWebScraper] No valid token for match {match_code}")
            return None

        url = self.BOXSCORE_API_URL.format(match_code=match_code)
        headers = self.HEADERS | {"Authorization": f"Bearer {token}"}
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            data = self._process_boxscore_data(data, match_code)
            if data:
                shotchart_data = self.fetch_shotchart(match_code, session, token)
                if shotchart_data is not None:
                    data["SHOTCHART"] = shotchart_data
                playbyplay_data = self.fetch_playbyplay(match_code, session, token)
                if playbyplay_data is not None:
                    data["PLAYBYPLAY"] = playbyplay_data
            return data
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                print(f"[FEBWebScraper] Unauthorized (401) for match {match_code}")
                if match_code in self.token_cache:
                    del self.token_cache[match_code]
                token = self.fetch_token(match_code, session)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        data = self._process_boxscore_data(data, match_code)
                        if data:
                            shotchart_data = self.fetch_shotchart(match_code, session, token)
                            if shotchart_data is not None:
                                data["SHOTCHART"] = shotchart_data
                            playbyplay_data = self.fetch_playbyplay(match_code, session, token)
                            if playbyplay_data is not None:
                                data["PLAYBYPLAY"] = playbyplay_data
                        return data
                    except requests.RequestException as retry_e:
                        print(f"[FEBWebScraper] Retry failed for match {match_code}: {retry_e}")
                        return None
                return None
            print(f"[FEBWebScraper] HTTP error for match {match_code}: {e}")
            return None
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch boxscore for match {match_code}: {e}")
            return None

    def get_matches(self, season_value: str, group_value: str, year: str, session: requests.Session) -> List[str]:
        """Fetch match codes for the given season and group."""
        norm_year = normalize_year(year)
        url = self.BASE_URL.format(year=norm_year)
        soup, session = self.get_page_content(norm_year)
        hidden_fields = self.get_hidden_fields(soup)
        soup, hidden_fields = self.select_season(session, url, season_value, hidden_fields)
        soup = self.select_group(session, url, season_value, group_value, hidden_fields)
        matches = []
        for cont in soup.find_all("div", class_="tableLayout de dos columnas"):
            for table in cont.find_all("table"):
                for row in table.find_all("tr")[1:]:
                    res_cell = row.find("td", class_="resultado")
                    if res_cell and (link := res_cell.find("a", href=re.compile(r"p=\d+"))):
                        if re.match(r"^\d+\s*-\s*\d+$", link.get_text(strip=True)):
                            if m := re.search(r"p=(\d+)", link["href"]):
                                matches.append(m.group(1))
        return matches