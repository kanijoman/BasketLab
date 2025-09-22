import requests
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QComboBox, QLabel, QProgressBar, QPushButton, QMessageBox
from typing import List, Dict, Optional
from scraper import FEBWebScraper
from database import MongoDBHandler
from utils import normalize_year

class BasketballSeasonApp(QMainWindow):
    """Main application class for the Basketball Season UI using PyQt6."""

    def __init__(self, scraper: FEBWebScraper, db_handler: MongoDBHandler):
        """Initialize the application with scraper and db handler."""
        super().__init__()
        self.scraper = scraper
        self.db_handler = db_handler
        self.seasons = []
        self.season_values = {}
        self.competitions = ["L.F. 2", "Primera Nacional"]
        self.group_options = {}
        self.group_values = {}
        self.setWindowTitle("Basketball Team Seasons")
        self.setMinimumSize(400, 400)
        self.initialize_data()
        self.setup_ui()

    def initialize_data(self) -> None:
        """Initialize seasons and group options."""
        try:
            initial_year = "2024"
            soup, _ = self.scraper.get_page_content(initial_year)
            seasons = self.scraper.get_seasons(soup)
            if seasons:
                self.seasons = [text for text, _ in seasons]
                self.season_values = {text: value for text, value in seasons}
            else:
                self.seasons = [f"{y}/{str(y+1)[-2:]}" for y in range(2015, 2026)]
                self.season_values = {text: normalize_year(text) for text in self.seasons}

            lf2_groups = self.scraper.get_groups(soup)
            self.group_options = {
                "L.F. 2": lf2_groups,
                "Primera Nacional": [("Grupo 1", "Grupo 1"), ("Grupo 2", "Grupo 2")]
            }
        except Exception as e:
            print(f"[App] Failed to initialize data: {str(e)}")
            self.seasons = [f"{y}/{str(y+1)[-2:]}" for y in range(2015, 2026)]
            self.season_values = {text: normalize_year(text) for text in self.seasons}
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
                start_year = normalize_year(season)
                soup, session = self.scraper.get_page_content(start_year)
                hidden_fields = self.scraper.get_hidden_fields(soup)
                season_value = self.season_values.get(season, normalize_year(season))
                soup, _ = self.scraper.select_season(session, self.scraper.BASE_URL.format(year=start_year), season_value, hidden_fields)
                self.group_options["L.F. 2"] = self.scraper.get_groups(soup)
                self.update_group_options()
            except Exception as e:
                print(f"[App] Failed to update groups: {str(e)}")

    def on_competition_select(self, competition: str) -> None:
        """Handle competition selection event."""
        self.competition_label.setText(f"Selected Competition: {competition}")
        self.update_group_options()

    def on_group_select(self, group: str) -> None:
        """Handle group selection event."""
        self.group_label.setText(f"Selected Group: {group}")

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

    def on_download(self) -> None:
        """Handle download button click."""
        from PyQt6.QtWidgets import QApplication
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No connection to MongoDB. Please check the server.")
                return

            season_text = self.season_combo.currentText()
            competition = self.competition_combo.currentText()
            group_text = self.group_combo.currentText()

            if not all([season_text, competition, group_text]):
                QMessageBox.warning(self, "Warning", "Please select all options before downloading.")
                return

            season_value = self.season_values.get(season_text, normalize_year(season_text))
            group_value = self.group_values.get(group_text, group_text)
            norm_year = normalize_year(season_text)
            session = requests.Session()

            matches = self.scraper.get_matches(season_value, group_value, norm_year, session)
            if not matches:
                QMessageBox.information(self, "Códigos de partidos", "No matches found.")
                return

            collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

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
                    if self.db_handler.document_exists(collection_name, int(match_code)):
                        print(f"[App] Match {match_code} already exists, skipping.")
                        successful_matches.append(match_code)
                        continue
                    boxscore = self.scraper.fetch_boxscore(match_code, session)
                    if boxscore:
                        if self.db_handler.insert_boxscore(collection_name, match_code, boxscore):
                            successful_matches.append(match_code)
                        else:
                            failed_matches.append(match_code)
                    else:
                        failed_matches.append(match_code)
                except Exception as e:
                    print(f"[App] Error processing match {match_code}: {str(e)}")
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