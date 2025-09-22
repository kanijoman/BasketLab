import sys
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QComboBox, QLabel, QProgressBar, QPushButton, QApplication, QMessageBox
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
import re
from datetime import datetime, timedelta
import pymongo
from pymongo.errors import ConnectionFailure, PyMongoError

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

    @staticmethod
    def normalize_year(year: str) -> str:
        """Normalize year input to a 4-digit year string (e.g. '2024/25' -> '2024')."""
        y = str(year).strip()
        if "/" in y:
            try:
                start = int(y.split("/")[0])
                return str(start)
            except Exception:
                pass
        if len(y) == 2 and y.isdigit():
            return "20" + y
        if len(y) == 4 and y.isdigit():
            return y
        m = re.search(r"(\d{4}|\d{2})", y)
        if m:
            val = m.group(1)
            if len(val) == 2:
                return "20" + val
            return val
        return y

    @staticmethod
    def get_form_field_name(id_str: str) -> str:
        """Get the form field name by replacing _ with : after _ctl0."""
        return '_ctl0:' + id_str[6:].replace("_", ":")

    @staticmethod
    def get_event_target(id_str: str) -> str:
        """Get the event target for postback by replacing _ with $ after _ctl0."""
        return '_ctl0$' + id_str[6:].replace("_", "$")

    @classmethod
    def get_page_content(cls, year: str) -> tuple[BeautifulSoup, requests.Session]:
        """Fetch and parse the webpage content for the given year."""
        norm_year = cls.normalize_year(year)
        url = cls.BASE_URL.format(year=norm_year)
        try:
            session = requests.Session()
            response = session.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser"), session
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to fetch URL: {url} --> {e}")
            raise

    @classmethod
    def get_seasons(cls, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract season options from the page."""
        season_dropdown = soup.find("select", {"id": cls.SEASON_DROPDOWN_ID})
        if season_dropdown:
            return [(opt.text.strip(), opt.get("value", opt.text.strip())) for opt in season_dropdown.find_all("option") if opt.text.strip()]
        return []

    @classmethod
    def get_groups(cls, soup: BeautifulSoup) -> List[tuple[str, str]]:
        """Extract group options from the page."""
        group_dropdown = soup.find("select", {"id": cls.GROUP_DROPDOWN_ID})
        if group_dropdown:
            return [(opt.text.strip(), opt.get("value", "")) for opt in group_dropdown.find_all("option") if opt.text.strip()]
        return []

    @classmethod
    def select_season(cls, session: requests.Session, url: str, season_value: str, hidden_fields: Dict[str, str]) -> tuple[BeautifulSoup, Dict[str, str]]:
        """Perform a POST to select the season."""
        season_field_name = cls.get_form_field_name(cls.SEASON_DROPDOWN_ID)
        season_event_target = cls.get_event_target(cls.SEASON_DROPDOWN_ID)
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
            return soup, cls.get_hidden_fields(soup)
        except requests.RequestException as e:
            print(f"[FEBWebScraper] Failed to select season: {e}")
            raise

    @classmethod
    def select_group(cls, session: requests.Session, url: str, season_value: str, group_value: str, hidden_fields: Dict[str, str]) -> BeautifulSoup:
        """Perform a POST to select the group."""
        season_field_name = cls.get_form_field_name(cls.SEASON_DROPDOWN_ID)
        group_field_name = cls.get_form_field_name(cls.GROUP_DROPDOWN_ID)
        group_event_target = cls.get_event_target(cls.GROUP_DROPDOWN_ID)
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

    @classmethod
    def get_hidden_fields(cls, soup: BeautifulSoup) -> Dict[str, str]:
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


class BasketballSeasonApp(QMainWindow):
    """Main application class for the Basketball Season UI using PyQt6."""

    def __init__(self):
        """Initialize the application and set up the UI components."""
        super().__init__()
        self.setWindowTitle("Basketball Team Seasons")
        self.setMinimumSize(400, 400)
        self.seasons = []
        self.season_values = {}
        self.competitions = ["L.F. 2", "Primera Nacional"]
        self.group_options = {}
        self.group_values = {}
        self.scraper = FEBWebScraper()
        self.db_client = None
        self.initialize_data()
        self.setup_ui()

    def initialize_data(self) -> None:
        """Initialize seasons, group options, and MongoDB connection."""
        try:
            # Initialize MongoDB client with provided URI
            self.db_client = pymongo.MongoClient("mongodb+srv://kanijoman:S0p0rt3s@mycluster.g3slkjv.mongodb.net/")
            self.db_client.server_info()  # Test connection
        except ConnectionFailure as e:
            print(f"[App] Failed to connect to MongoDB: {e}")
            self.db_client = None

        try:
            initial_year = "2024"
            soup, _ = self.scraper.get_page_content(initial_year)
            seasons = self.scraper.get_seasons(soup)
            if seasons:
                self.seasons = [text for text, _ in seasons]
                self.season_values = {text: value for text, value in seasons}
            else:
                self.seasons = [f"{y}/{str(y+1)[-2:]}" for y in range(2015, 2026)]
                self.season_values = {text: self.scraper.normalize_year(text) for text in self.seasons}

            lf2_groups = self.scraper.get_groups(soup)
            self.group_options = {
                "L.F. 2": lf2_groups,
                "Primera Nacional": [("Grupo 1", "Grupo 1"), ("Grupo 2", "Grupo 2")]
            }
        except Exception as e:
            print(f"[App] Failed to initialize data: {str(e)}")
            self.seasons = [f"{y}/{str(y+1)[-2:]}" for y in range(2015, 2026)]
            self.season_values = {text: self.scraper.normalize_year(text) for text in self.seasons}
            self.group_options = {
                "L.F. 2": [],
                "Primera Nacional": [("Grupo 1", "Grupo 1"), ("Grupo 2", "Grupo 2")]
            }

    def setup_ui(self):
        """Set up the PyQt6 UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Season ComboBox
        self.season_combo = QComboBox()
        self.season_combo.addItems(self.seasons)
        self.season_combo.setCurrentIndex(0)
        self.season_combo.currentTextChanged.connect(self.on_season_select)
        layout.addWidget(self.season_combo)

        self.season_label = QLabel(f"Selected Season: {self.seasons[0]}")
        layout.addWidget(self.season_label)

        # Competition ComboBox
        self.competition_combo = QComboBox()
        self.competition_combo.addItems(self.competitions)
        self.competition_combo.setCurrentIndex(0)
        self.competition_combo.currentTextChanged.connect(self.on_competition_select)
        layout.addWidget(self.competition_combo)

        self.competition_label = QLabel(f"Selected Competition: {self.competitions[0]}")
        layout.addWidget(self.competition_label)

        # Group ComboBox
        self.group_combo = QComboBox()
        self.group_combo.currentTextChanged.connect(self.on_group_select)
        layout.addWidget(self.group_combo)

        self.group_label = QLabel("Selected Group: ")
        layout.addWidget(self.group_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Progress Label
        self.progress_label = QLabel("Progress: Waiting to start")
        layout.addWidget(self.progress_label)

        # Download Button
        self.download_button = QPushButton("Download")
        self.download_button.clicked.connect(self.on_download)
        layout.addWidget(self.download_button)

        # Apply basic styling for a modern look
        self.setStyleSheet("""
            QComboBox, QPushButton, QLabel {
                font-size: 14px;
                padding: 5px;
            }
            QComboBox {
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                background-color: #fff;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 5px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)

        self.update_group_options()

    def on_season_select(self, season: str) -> None:
        """Handle season selection event."""
        self.season_label.setText(f"Selected Season: {season}")
        if self.competition_combo.currentText() == "L.F. 2":
            try:
                start_year = self.scraper.normalize_year(season)
                soup, session = self.scraper.get_page_content(start_year)
                hidden_fields = self.scraper.get_hidden_fields(soup)
                season_value = self.season_values.get(season, self.scraper.normalize_year(season))
                soup, _ = self.scraper.select_season(session, self.scraper.BASE_URL.format(year=start_year), season_value, hidden_fields)
                self.group_options["L.F. 2"] = self.scraper.get_groups(soup)
                self.update_group_options()
            except Exception as e:
                print(f"[App] Failed to update groups: {str(e)}")

    def on_competition_select(self, competition: str) -> None:
        """Handle competition selection event."""
        self.competition_label.setText(f"Selected Competition: {competition}")
        self.update_group_options()

    def update_group_options(self) -> None:
        """Update the group dropdown."""
        selected_competition = self.competition_combo.currentText()
        groups = self.group_options.get(selected_competition, [])
        self.group_combo.clear()
        self.group_combo.addItems([text for text, value in groups])
        self.group_values = {text: value for text, value in groups}
        if groups:
            self.group_combo.setCurrentIndex(0)
            self.group_label.setText(f"Selected Group: {groups[0][0]}")
        else:
            self.group_combo.clear()
            self.group_label.setText("Selected Group: ")

    def on_group_select(self, group: str) -> None:
        """Handle group selection event."""
        self.group_label.setText(f"Selected Group: {group}")

    def on_download(self) -> None:
        """Handle download button click."""
        try:
            if not self.db_client:
                QMessageBox.critical(self, "Error", "No connection to MongoDB. Please check the server.")
                return

            season_text = self.season_combo.currentText()
            competition = self.competition_combo.currentText()
            group_text = self.group_combo.currentText()

            if not all([season_text, competition, group_text]):
                QMessageBox.warning(self, "Warning", "Please select all options before downloading.")
                return

            season_value = self.season_values.get(season_text, self.scraper.normalize_year(season_text))
            group_value = self.group_values.get(group_text, group_text)

            norm_year = self.scraper.normalize_year(season_text)
            url = self.scraper.BASE_URL.format(year=norm_year)

            soup, session = self.scraper.get_page_content(norm_year)
            hidden_fields = self.scraper.get_hidden_fields(soup)
            soup, hidden_fields = self.scraper.select_season(session, url, season_value, hidden_fields)

            groups = self.scraper.get_groups(soup)
            if group_value not in [g[1] for g in groups]:
                raise ValueError(f"Group {group_value} not available for season {season_value}")

            soup = self.scraper.select_group(session, url, season_value, group_value, hidden_fields)

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

            if not matches:
                QMessageBox.information(self, "Códigos de partidos", "No matches found.")
                return

            safe_group_text = re.sub(r'[\\/:*?"<>|]', '_', group_text)
            collection_name = f"{competition.replace('.', '_')}_{season_text.replace('/', '_')}_{safe_group_text}"
            db = self.db_client["FEB"]
            collection = db[collection_name]

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            self.progress_label.setText("Progress: Starting download...")
            QApplication.processEvents()

            successful_matches = []
            failed_matches = []
            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Progress: Processing match {match_code}")
                self.progress_bar.setValue(i)
                QApplication.processEvents()
                try:
                    if collection.find_one({"_id": int(match_code)}):
                        print(f"[App] Match {match_code} already exists, skipping.")
                        successful_matches.append(match_code)
                        continue
                    boxscore = self.scraper.fetch_boxscore(match_code, session)
                    if boxscore:
                        boxscore["_id"] = int(match_code)  # Use match_code as integer _id
                        collection.insert_one(boxscore)
                        successful_matches.append(match_code)
                    else:
                        failed_matches.append(match_code)
                except PyMongoError as e:
                    print(f"[App] Failed to save match {match_code} to MongoDB: {e}")
                    failed_matches.append(match_code)

            self.progress_label.setText("Progress: Download complete")
            self.progress_bar.setValue(len(matches))
            QApplication.processEvents()

            message = f"Found {len(matches)} matches.\n"
            if successful_matches:
                message += f"Saved {len(successful_matches)} boxscores to MongoDB collection '{collection_name}'\n"
            if failed_matches:
                message += f"Failed to fetch or save boxscores for {len(failed_matches)} matches: {', '.join(failed_matches)}\nPlease check the match page HTML (match_page_{failed_matches[0]}.html) or MongoDB connection."
            QMessageBox.information(self, "Códigos de partidos", message)

        except Exception as e:
            print(f"[App] Error in download: {str(e)}")
            QMessageBox.critical(self, "Error", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = BasketballSeasonApp()
    window.show()
    sys.exit(app.exec())