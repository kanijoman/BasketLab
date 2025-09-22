import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re
from utils import normalize_year, get_form_field_name, get_event_target

class FEBWebScraper:
    """A class to handle web scraping operations for the FEB basketball website."""

    BASE_URL = "https://baloncestoenvivo.feb.es/calendario/lf2/9/{year}"
    MATCH_PAGE_URL = "https://baloncestoenvivo.feb.es/partido/{match_code}"
    BOXSCORE_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/BoxScore/{match_code}"
    SHOTCHART_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/ShotChart/{match_code}"
    KEYFACTS_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/KeyFacts/{match_code}"
    SEASON_DROPDOWN_ID = "_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList"
    GROUP_DROPDOWN_ID = "_ctl0_MainContentPlaceHolderMaster_gruposDropDownList"

    def __init__(self):
        """Initialize with token cache."""
        self.token_cache = {}  # {match_code: (token, expiry_time)}

    def get_page_content(self, year: str) -> tuple[BeautifulSoup, requests.Session]:
        """Fetch and parse the webpage content for the given year."""
        norm_year = normalize_year(year)
        url = self.BASE_URL.format(year=norm_year)
        try:
            session = requests.Session()
            response = session.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser"), session
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch URL: {url} --> {e}")
            raise

    def get_seasons(self, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract season options from the page."""
        season_dropdown = soup.find("select", {"id": self.SEASON_DROPDOWN_ID})
        if season_dropdown:
            return [(opt.text.strip(), opt.get("value", opt.text.strip())) for opt in season_dropdown.find_all("option") if opt.text.strip()]
        return []

    def get_groups(self, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract group options from the page."""
        group_dropdown = soup.find("select", {"id": self.GROUP_DROPDOWN_ID})
        if group_dropdown:
            return [(opt.text.strip(), opt.get("value", "")) for opt in group_dropdown.find_all("option") if opt.text.strip()]
        return []

    def select_season(self, session: requests.Session, url: str, season_value: str, hidden_fields: Dict[str, str]) -> tuple[BeautifulSoup, Dict[str, str]]:
        """Perform a POST to select the season."""
        season_field_name = get_form_field_name(self.SEASON_DROPDOWN_ID)
        season_event_target = get_event_target(self.SEASON_DROPDOWN_ID)
        form_data = {
            "__EVENTTARGET": season_event_target,
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            season_field_name: season_value,
        }
        form_data.update(hidden_fields)
        try:
            response = session.post(url, data=form_data, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            return soup, self.get_hidden_fields(soup)
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to select season: {e}")
            raise

    def select_group(self, session: requests.Session, url: str, season_value: str, group_value: str, hidden_fields: Dict[str, str]) -> BeautifulSoup:
        """Perform a POST to select the group."""
        season_field_name = get_form_field_name(self.SEASON_DROPDOWN_ID)
        group_field_name = get_form_field_name(self.GROUP_DROPDOWN_ID)
        group_event_target = get_event_target(self.GROUP_DROPDOWN_ID)
        form_data = {
            "__EVENTTARGET": group_event_target,
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            season_field_name: season_value,
            group_field_name: group_value,
        }
        form_data.update(hidden_fields)
        try:
            response = session.post(url, data=form_data, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
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
        if match_code in self.token_cache:
            token, expiry = self.token_cache[match_code]
            if expiry > datetime.now():
                return token
            del self.token_cache[match_code]

        url = self.MATCH_PAGE_URL.format(match_code=match_code)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,gl;q=0.7",
            "Referer": "https://baloncestoenvivo.feb.es/",
        }
        try:
            response = session.get(url, timeout=10, headers=headers)
            response.raise_for_status()

            token = None
            if "Authorization" in response.headers and response.headers["Authorization"].startswith("Bearer "):
                token = response.headers["Authorization"][7:]
            else:
                soup = BeautifulSoup(response.text, "html.parser")
                scripts = soup.find_all("script")
                for script in scripts:
                    if script.string:
                        match = re.search(r'Bearer\s+([A-Za-z0-9\-_\.]+)', script.string) or \
                                re.search(r'token\s*[:=]\s*[\'"]?([A-Za-z0-9\-_\.]+)[\'"]?', script.string) or \
                                re.search(r'\{[^}]*"token"\s*:\s*"([A-Za-z0-9\-_\.]+)"[^}]*\}', script.string)
                        if match:
                            token = match.group(1)
                            break
                if not token:
                    inputs = soup.find_all("input", type="hidden")
                    for input_tag in inputs:
                        if input_tag.get("value", "").startswith("eyJhbGci"):
                            token = input_tag["value"]
                            break
                if not token:
                    meta_tags = soup.find_all("meta", attrs={"name": re.compile(r'token', re.I)})
                    for meta in meta_tags:
                        if meta.get("content"):
                            match = re.search(r'Bearer\s+([A-Za-z0-9\-_\.]+)|([A-Za-z0-9\-_\.]+)', meta.get("content"))
                            if match:
                                token = match.group(1) or match.group(2)
                                break

            if not token:
                print(f"[FEBWebScraper] No token found for match {match_code}. Headers: {response.headers}")
                html_file = f"match_page_{match_code}.html"
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(response.text)
                return None

            expiry = datetime.now() + timedelta(hours=24)
            self.token_cache[match_code] = (token, expiry)
            return token
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch token for match {match_code}: {e}")
            return None

    def fetch_shotchart(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """Fetch JSON shotchart data for the given match_code."""
        url = self.SHOTCHART_API_URL.format(match_code=match_code)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,gl;q=0.7",
            "Referer": "https://baloncestoenvivo.feb.es/",
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("SHOTCHART", [])
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                print(f"[FEBWebScraper] Unauthorized (401) for shotchart {match_code}: Invalid or expired token")
                if match_code in self.token_cache:
                    del self.token_cache[match_code]
                token = self.fetch_token(match_code, session)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        return data.get("SHOTCHART", [])
                    except requests.RequestException as retry_e:
                        print(f"[FEBWebScraper] Retry failed for shotchart {match_code}: {retry_e}")
                        return None
                return None
            print(f"[FEBWebScraper] HTTP error for shotchart {match_code}: {e}")
            return None
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch shotchart for match {match_code}: {e}")
            return None

    def fetch_playbyplay(self, match_code: str, session: requests.Session, token: str) -> Optional[List]:
        """Fetch JSON playbyplay data for the given match_code."""
        url = self.KEYFACTS_API_URL.format(match_code=match_code)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,gl;q=0.7",
            "Referer": "https://baloncestoenvivo.feb.es/",
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("PLAYBYPLAY", [])
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                print(f"[FEBWebScraper] Unauthorized (401) for playbyplay {match_code}: Invalid or expired token")
                if match_code in self.token_cache:
                    del self.token_cache[match_code]
                token = self.fetch_token(match_code, session)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        return data.get("PLAYBYPLAY", [])
                    except requests.RequestException as retry_e:
                        print(f"[FEBWebScraper] Retry failed for playbyplay {match_code}: {retry_e}")
                        return None
                return None
            print(f"[FEBWebScraper] HTTP error for playbyplay {match_code}: {e}")
            return None
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch playbyplay for match {match_code}: {e}")
            return None

    def fetch_boxscore(self, match_code: str, session: requests.Session) -> Optional[Dict]:
        """Fetch JSON boxscore data, add game_code as integer to HEADER, and include SHOTCHART and PLAYBYPLAY."""
        token = self.fetch_token(match_code, session)
        if not token:
            print(f"[FEBWebScraper] No valid token for match {match_code}")
            return None

        # Fetch boxscore
        url = self.BOXSCORE_API_URL.format(match_code=match_code)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            "Authorization": f"Bearer {token}",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8,gl;q=0.7",
            "Referer": "https://baloncestoenvivo.feb.es/",
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            if "HEADER" not in data:
                data["HEADER"] = {}
            data["HEADER"]["game_code"] = int(match_code)

            # Check for empty nodes in boxscore data
            for key in ["scoreboard", "teamstats", "banner"]:
                if key in data and not data[key]:
                    print(f"[FEBWebScraper] Empty node {key} for match {match_code}")

            # Fetch shotchart and add SHOTCHART node
            shotchart_data = self.fetch_shotchart(match_code, session, token)
            if shotchart_data is not None:
                data["SHOTCHART"] = shotchart_data

            # Fetch playbyplay and add PLAYBYPLAY node
            playbyplay_data = self.fetch_playbyplay(match_code, session, token)
            if playbyplay_data is not None:
                data["PLAYBYPLAY"] = playbyplay_data

            return data
        except requests.HTTPError as e:
            if e.response.status_code == 401:
                print(f"[FEBWebScraper] Unauthorized (401) for match {match_code}: Invalid or expired token")
                if match_code in self.token_cache:
                    del self.token_cache[match_code]
                token = self.fetch_token(match_code, session)
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    try:
                        response = requests.get(url, headers=headers, timeout=10)
                        response.raise_for_status()
                        data = response.json()
                        if "HEADER" not in data:
                            data["HEADER"] = {}
                        data["HEADER"]["game_code"] = int(match_code)

                        # Check for empty nodes in boxscore data
                        for key in ["scoreboard", "teamstats", "banner"]:
                            if key in data and not data[key]:
                                print(f"[FEBWebScraper] Empty node {key} for match {match_code}")

                        # Fetch shotchart with new token
                        shotchart_data = self.fetch_shotchart(match_code, session, token)
                        if shotchart_data is not None:
                            data["SHOTCHART"] = shotchart_data

                        # Fetch playbyplay with new token
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
        containers = soup.find_all("div", class_="tableLayout de dos columnas")
        for cont in containers:
            tables = cont.find_all("table")
            for table in tables:
                rows = table.find_all("tr")[1:]
                for row in rows:
                    res_cell = row.find("td", class_="resultado")
                    if res_cell:
                        link = res_cell.find("a", href=re.compile(r"p=\d+"))
                        if link:
                            res_text = link.get_text(strip=True)
                            if re.match(r"^\d+\s*-\s*\d+$", res_text):
                                m = re.search(r"p=(\d+)", link["href"])
                                if m:
                                    matches.append(m.group(1))
        return matches