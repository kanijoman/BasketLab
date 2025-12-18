"""Main application window for basketball season selection."""

import requests
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QComboBox, QLabel,
                              QProgressBar, QPushButton, QMessageBox, QApplication, QDialog)
from PyQt6.QtCore import QThread
from typing import List, Dict

from scraper import FEBWebScraper, FBCYLWebScraper
from database import MongoDBHandler
from utils import normalize_year
from .stats_window import TeamStatsWindow
from .shotchart_window import ShotChartWindow
from .temporal_evolution_window import TemporalEvolutionWindow
from .ranking_window import PlayerRankingWindow
from .weekly_report_dialog import WeeklyReportDialog
from .weekly_report_generator import WeeklyReportGenerator
from .ui_utils import set_app_icon
from .team_utils import get_available_teams_from_collection


class BasketballSeasonApp(QMainWindow):
    """Main application class for the Basketball Season UI using PyQt6."""

    def __init__(self, scraper: FEBWebScraper, db_handler: MongoDBHandler):
        """
        Initialize the application with scraper and db handler.

        Args:
            scraper: FEBWebScraper instance for data collection
            db_handler: MongoDBHandler instance for database operations
        """
        super().__init__()
        self.scraper = scraper
        self.db_handler = db_handler
        self.seasons = []
        self.season_values = {}
        self.scopes = ["FEB", "FBCYL"]
        self.current_scope = ""
        self.competitions = []  # Will be loaded from selected scope
        self.competition_urls = {}  # Map competition names to their results URLs
        self.group_options = {}
        self.group_values = {}

        # Initialize FBCYL scraper
        from scraper import WebClient
        self.fbcyl_scraper = FBCYLWebScraper(WebClient())

        # FBCYL specific variables
        self.fbcyl_genders = []
        self.fbcyl_gender_values = {}
        self.fbcyl_territories = []
        self.fbcyl_territory_values = {}
        self.fbcyl_categories = []
        self.fbcyl_category_values = {}
        self.fbcyl_competitions = []
        self.fbcyl_competition_values = {}

        self.setWindowTitle("MfA - Metrics for All")
        self.setMinimumSize(450, 600)

        # Set application icon
        set_app_icon(self)

        self.initialize_data()
        self.setup_ui()

    def initialize_data(self) -> None:
        """Initialize seasons."""
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
        except Exception as e:
            self.seasons = [f"{y}/{str(y+1)[-2:]}" for y in range(2015, 2026)]
            self.season_values = {text: normalize_year(text) for text in self.seasons}

    def setup_ui(self):
        """Set up the PyQt6 UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Scope ComboBox
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("")  # Add empty item by default
        self.scope_combo.addItems(self.scopes)
        self.scope_combo.currentTextChanged.connect(self.on_scope_select)
        layout.addWidget(self.scope_combo)

        self.scope_label = QLabel("Ámbito seleccionado: ")
        layout.addWidget(self.scope_label)

        # Season ComboBox
        self.season_combo = QComboBox()
        self.season_combo.addItem("")  # Add empty item
        self.season_combo.addItems(self.seasons)
        self.season_combo.currentTextChanged.connect(self.on_season_select)
        self.season_combo.setVisible(False)  # Hidden until scope is selected
        layout.addWidget(self.season_combo)

        self.season_label = QLabel("Temporada seleccionada: ")
        self.season_label.setVisible(False)
        layout.addWidget(self.season_label)

        # FBCYL-specific dropdowns (initially hidden)
        # Gender ComboBox
        self.gender_combo = QComboBox()
        self.gender_combo.currentTextChanged.connect(self.on_gender_select)
        self.gender_combo.setVisible(False)
        layout.addWidget(self.gender_combo)

        self.gender_label = QLabel("Género seleccionado: ")
        self.gender_label.setVisible(False)
        layout.addWidget(self.gender_label)

        # Territory ComboBox
        self.territory_combo = QComboBox()
        self.territory_combo.currentTextChanged.connect(self.on_territory_select)
        self.territory_combo.setVisible(False)
        layout.addWidget(self.territory_combo)

        self.territory_label = QLabel("Territorio seleccionado: ")
        self.territory_label.setVisible(False)
        layout.addWidget(self.territory_label)

        # Category ComboBox
        self.category_combo = QComboBox()
        self.category_combo.currentTextChanged.connect(self.on_category_select)
        self.category_combo.setVisible(False)
        layout.addWidget(self.category_combo)

        self.category_label = QLabel("Categoría seleccionada: ")
        self.category_label.setVisible(False)
        layout.addWidget(self.category_label)

        # Competition ComboBox (for FEB appears early, for FBCYL appears after category)
        self.competition_combo = QComboBox()
        self.competition_combo.addItem("")  # Add empty item
        self.competition_combo.currentTextChanged.connect(self.on_competition_select)
        self.competition_combo.setVisible(False)  # Hidden until scope is selected
        layout.addWidget(self.competition_combo)

        self.competition_label = QLabel("Competición seleccionada: ")
        self.competition_label.setVisible(False)
        layout.addWidget(self.competition_label)

        # Group ComboBox (only for FEB)
        self.group_combo = QComboBox()
        self.group_combo.currentTextChanged.connect(self.on_group_select)
        self.group_combo.setVisible(False)  # Hidden until needed
        layout.addWidget(self.group_combo)

        self.group_label = QLabel("Grupo seleccionado: ")
        self.group_label.setVisible(False)
        layout.addWidget(self.group_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Progress Label
        self.progress_label = QLabel("Progreso: Esperando para comenzar")
        layout.addWidget(self.progress_label)

        # View Team Stats Button
        self.stats_button = QPushButton("📊 Estadísticas de Equipo")
        self.stats_button.clicked.connect(self.on_view_stats)
        self.stats_button.setEnabled(False)  # Disabled by default
        self.stats_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        layout.addWidget(self.stats_button)

        # View Player Stats Button
        self.player_stats_button = QPushButton("👤 Estadísticas Individuales")
        self.player_stats_button.clicked.connect(self.on_view_player_stats)
        self.player_stats_button.setEnabled(False)  # Disabled by default
        self.player_stats_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        layout.addWidget(self.player_stats_button)

        # Temporal Evolution Button
        self.temporal_button = QPushButton("📈 Evolución Temporal")
        self.temporal_button.clicked.connect(self.on_view_temporal_evolution)
        self.temporal_button.setEnabled(False)  # Disabled by default
        self.temporal_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        layout.addWidget(self.temporal_button)

        # Shot Chart Button
        self.shotchart_button = QPushButton("🎯 Gráficos de Tiro")
        self.shotchart_button.clicked.connect(self.on_view_shotcharts)
        self.shotchart_button.setEnabled(False)  # Disabled by default
        self.shotchart_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        layout.addWidget(self.shotchart_button)

        # AI Analysis Button
        self.ai_analysis_button = QPushButton("🤖 Análisis IA")
        self.ai_analysis_button.clicked.connect(self.on_view_ai_analysis)
        self.ai_analysis_button.setEnabled(False)  # Disabled by default
        self.ai_analysis_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        layout.addWidget(self.ai_analysis_button)

        # Rankings Button
        self.rankings_button = QPushButton("🏆 Ránkings")
        self.rankings_button.clicked.connect(self.on_view_rankings)
        self.rankings_button.setEnabled(False)  # Disabled by default
        self.rankings_button.setStyleSheet("""
            QPushButton {
                background-color: #E91E63;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #C2185B;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        layout.addWidget(self.rankings_button)

        # Weekly Report Button
        self.weekly_report_button = QPushButton("📋 Informe Semanal")
        self.weekly_report_button.clicked.connect(self.on_generate_weekly_report)
        self.weekly_report_button.setEnabled(False)  # Disabled by default
        self.weekly_report_button.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border-radius: 5px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        layout.addWidget(self.weekly_report_button)

        # Apply basic styling for a modern look
        self.setStyleSheet("""
            QComboBox, QLabel {
                font-size: 14px;
                padding: 5px;
            }
            QComboBox {
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                background-color: #fff;
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

    def on_scope_select(self, scope: str) -> None:
        """Handle scope selection event."""
        if not scope:  # If empty selection
            self.scope_label.setText("Ámbito seleccionado: ")
            self.current_scope = ""
            # Hide all dropdowns
            self.season_combo.setVisible(False)
            self.season_label.setVisible(False)
            self.competition_combo.setVisible(False)
            self.competition_label.setVisible(False)
            self.group_combo.setVisible(False)
            self.group_label.setVisible(False)
            # Clear competitions
            self.competition_combo.clear()
            self.competition_combo.addItem("")
            self.competitions = []
            # Hide FBCYL-specific dropdowns
            self.gender_combo.setVisible(False)
            self.gender_label.setVisible(False)
            self.territory_combo.setVisible(False)
            self.territory_label.setVisible(False)
            self.category_combo.setVisible(False)
            self.category_label.setVisible(False)
            # Clear FBCYL dropdowns
            self.gender_combo.clear()
            self.territory_combo.clear()
            self.category_combo.clear()
            # Reset window size
            self.setMinimumSize(450, 600)
            self._validate_selections()
            return

        self.scope_label.setText(f"Ámbito seleccionado: {scope}")
        self.current_scope = scope

        if scope == "FEB":
            # Show FEB dropdowns
            self.season_combo.setVisible(True)
            self.season_label.setVisible(True)
            self.competition_combo.setVisible(True)
            self.competition_label.setVisible(True)
            self.group_combo.setVisible(True)
            self.group_label.setVisible(True)

            # Hide FBCYL-specific dropdowns
            self.gender_combo.setVisible(False)
            self.gender_label.setVisible(False)
            self.territory_combo.setVisible(False)
            self.territory_label.setVisible(False)
            self.category_combo.setVisible(False)
            self.category_label.setVisible(False)

            # Clear FBCYL dropdowns
            self.gender_combo.clear()
            self.territory_combo.clear()
            self.category_combo.clear()

            # Reset window size for FEB
            self.setMinimumSize(450, 650)

            # Load FEB seasons
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

                self.season_combo.clear()
                self.season_combo.addItem("")
                self.season_combo.addItems(self.seasons)
            except Exception as e:
                self.seasons = [f"{y}/{str(y+1)[-2:]}" for y in range(2015, 2026)]
                self.season_values = {text: normalize_year(text) for text in self.seasons}
                self.season_combo.clear()
                self.season_combo.addItem("")
                self.season_combo.addItems(self.seasons)

            # Load FEB competitions dynamically
            try:
                feb_competitions = self.scraper.get_feb_competitions()
                self.competitions = [comp["name"] for comp in feb_competitions]
                # Store the mapping of competition names to their URLs
                self.competition_urls = {comp["name"]: comp["results_url"] for comp in feb_competitions}
                self.competition_combo.clear()
                self.competition_combo.addItem("")  # Add empty item
                self.competition_combo.addItems(self.competitions)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudieron cargar las competiciones de FEB: {str(e)}")
                self.competitions = []
                self.competition_urls = {}

            # Clear group combo
            self.group_combo.clear()
            self.group_combo.addItem("")

        elif scope == "FBCYL":
            # Show season dropdown
            self.season_combo.setVisible(True)
            self.season_label.setVisible(True)

            # Show FBCYL-specific dropdowns
            self.gender_combo.setVisible(True)
            self.gender_label.setVisible(True)
            self.territory_combo.setVisible(True)
            self.territory_label.setVisible(True)
            self.category_combo.setVisible(True)
            self.category_label.setVisible(True)

            # Show competition dropdown (will be filled later)
            self.competition_combo.setVisible(True)
            self.competition_label.setVisible(True)

            # Hide group dropdown (FBCYL uses competition/grupo combined)
            self.group_combo.setVisible(False)
            self.group_label.setVisible(False)

            # Clear FBCYL dropdowns
            self.gender_combo.clear()
            self.gender_combo.addItem("")
            self.territory_combo.clear()
            self.territory_combo.addItem("")
            self.category_combo.clear()
            self.category_combo.addItem("")

            # Adjust window size for FBCYL (more dropdowns)
            self.setMinimumSize(450, 800)

            # Load FBCYL initial data (seasons)
            try:
                soup, session = self.fbcyl_scraper.get_page_content()

                # Get seasons
                seasons = self.fbcyl_scraper.get_seasons(soup)
                if seasons:
                    self.seasons = [text for text, _ in seasons]
                    self.season_values = {text: value for text, value in seasons}
                    self.season_combo.clear()
                    self.season_combo.addItem("")
                    self.season_combo.addItems(self.seasons)

                # Clear competition combo for FBCYL (will be filled after other selections)
                self.competition_combo.clear()
                self.competition_combo.addItem("")

            except Exception as e:
                QMessageBox.warning(self, "Error", f"No se pudieron cargar los datos de FBCYL: {str(e)}")

        # Reset other selections
        self.competition_combo.setCurrentText("")
        self._validate_selections()

    def on_competition_select(self, competition: str) -> None:
        """Handle competition selection event."""
        if not competition:  # If empty selection
            self.competition_label.setText("Competición seleccionada: ")
            self.update_group_options()  # This will clear the group combo
            self._validate_selections()
            return

        self.competition_label.setText(f"Competición seleccionada: {competition}")

        # For FEB: Load groups if season is already selected
        if self.current_scope == "FEB":
            season = self.season_combo.currentText()
            if season:
                # Load groups for this competition
                self._load_feb_groups(competition)
            else:
                # Clear groups until season is selected
                if competition in self.group_options:
                    del self.group_options[competition]
                self.update_group_options()

        self._validate_selections()

    def _load_feb_groups(self, competition: str) -> None:
        """Load groups for a FEB competition."""
        try:
            # Clear existing groups for this competition before loading new ones
            if competition in self.group_options:
                del self.group_options[competition]

            # Get the specific URL for this competition
            if competition not in self.competition_urls:
                return

            competition_url = self.competition_urls[competition]

            # Fetch the competition page directly
            response = self.scraper.web_client.get(competition_url)
            if not response:
                raise Exception(f"Failed to fetch competition page: {competition_url}")

            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")

            # Get groups from the competition page
            groups = self.scraper.get_groups(soup)

            # Store groups using the actual competition name selected
            self.group_options[competition] = groups
            self.update_group_options()
        except Exception as e:
            pass

    def on_season_select(self, season: str) -> None:
        """Handle season selection event."""
        if not season:  # If empty selection
            self.season_label.setText("Temporada seleccionada: ")
            self._validate_selections()
            return

        self.season_label.setText(f"Temporada seleccionada: {season}")
        self._validate_selections()
        competition = self.competition_combo.currentText()

        if not competition or not self.current_scope:
            # For FBCYL, load genders when season is selected
            if self.current_scope == "FBCYL":
                self._load_fbcyl_genders()
            return

        # Load groups dynamically for FEB competitions
        if self.current_scope == "FEB":
            self._load_feb_groups(competition)
        elif self.current_scope == "FBCYL":
            # Load genders for FBCYL
            self._load_fbcyl_genders()

    def on_group_select(self, group: str) -> None:
        """Handle group selection event."""
        self.group_label.setText(f"Grupo seleccionado: {group}")
        self._validate_selections()

    def on_gender_select(self, gender: str) -> None:
        """Handle gender selection event (FBCYL specific)."""
        if not gender:
            self.gender_label.setText("Género seleccionado: ")
            self._validate_selections()
            return

        self.gender_label.setText(f"Género seleccionado: {gender}")
        self._validate_selections()

        # Load territories based on season and gender selection
        season = self.season_combo.currentText()
        if season and self.current_scope == "FBCYL":
            self._load_fbcyl_territories()

    def on_territory_select(self, territory: str) -> None:
        """Handle territory selection event (FBCYL specific)."""
        if not territory:
            self.territory_label.setText("Territorio seleccionado: ")
            self._validate_selections()
            return

        self.territory_label.setText(f"Territorio seleccionado: {territory}")
        self._validate_selections()

        # Load categories based on previous selections
        if self.current_scope == "FBCYL":
            self._load_fbcyl_categories()

    def on_category_select(self, category: str) -> None:
        """Handle category selection event (FBCYL specific)."""
        if not category:
            self.category_label.setText("Categoría seleccionada: ")
            self._validate_selections()
            return

        self.category_label.setText(f"Categoría seleccionada: {category}")
        self._validate_selections()

        # Load competitions based on previous selections
        if self.current_scope == "FBCYL":
            self._load_fbcyl_competitions()

    def _hide_fbcyl_dropdowns(self) -> None:
        """Hide FBCYL-specific dropdown widgets and reset window size."""
        self.gender_combo.setVisible(False)
        self.gender_label.setVisible(False)
        self.territory_combo.setVisible(False)
        self.territory_label.setVisible(False)
        self.category_combo.setVisible(False)
        self.category_label.setVisible(False)
        # Reset window size
        self.setMinimumSize(450, 650)

    def _show_fbcyl_dropdowns(self) -> None:
        """Show FBCYL-specific dropdown widgets and adjust window size."""
        self.gender_combo.setVisible(True)
        self.gender_label.setVisible(True)
        self.territory_combo.setVisible(True)
        self.territory_label.setVisible(True)
        self.category_combo.setVisible(True)
        self.category_label.setVisible(True)
        # Adjust window size for more dropdowns
        self.setMinimumSize(450, 800)

    def _load_fbcyl_genders(self) -> None:
        """Load gender options for FBCYL based on season selection."""
        try:
            season = self.season_combo.currentText()
            if not season:
                return

            # TODO: Implement actual logic to fetch genders from FBCYL
            # For now, using placeholder
            soup, session = self.fbcyl_scraper.get_page_content()
            genders = self.fbcyl_scraper.get_genders(soup)

            if genders:
                self.fbcyl_genders = [text for text, _ in genders]
                self.fbcyl_gender_values = {text: value for text, value in genders}
                self.gender_combo.clear()
                self.gender_combo.addItem("")
                self.gender_combo.addItems(self.fbcyl_genders)
            self._validate_selections()
        except Exception as e:
            pass

    def _load_fbcyl_territories(self) -> None:
        """Load territory options for FBCYL based on season and gender selection."""
        try:
            # TODO: Implement actual logic to fetch territories from FBCYL
            soup, session = self.fbcyl_scraper.get_page_content()
            territories = self.fbcyl_scraper.get_territories(soup)

            if territories:
                self.fbcyl_territories = [text for text, _ in territories]
                self.fbcyl_territory_values = {text: value for text, value in territories}
                self.territory_combo.clear()
                self.territory_combo.addItem("")
                self.territory_combo.addItems(self.fbcyl_territories)
            self._validate_selections()
        except Exception as e:
            pass

    def _load_fbcyl_categories(self) -> None:
        """Load category options for FBCYL based on previous selections."""
        try:
            # Get current selections
            season = self.season_combo.currentText()
            gender = self.gender_combo.currentText()
            territory = self.territory_combo.currentText()

            if not season or not gender or not territory:
                return

            # Get season value from mapping
            season_value = self.season_values.get(season, "")
            if not season_value:
                return

            # Get gender and territory values
            gender_value = self.fbcyl_gender_values.get(gender, "")
            territory_value = self.fbcyl_territory_values.get(territory, "0")

            # Fetch categories via AJAX
            categories = self.fbcyl_scraper.fetch_categories_ajax(
                temporada=season_value,
                genere=gender_value,
                territorial=territory_value
            )

            self.category_combo.clear()
            self.category_combo.addItem("")

            if categories:
                self.fbcyl_categories = [text for text, _ in categories]
                self.fbcyl_category_values = {text: value for text, value in categories}
                self.category_combo.addItems(self.fbcyl_categories)
            else:
                # Add informative placeholder when no data available
                self.category_combo.addItem("(No hay categorías disponibles)")

            # Validate selections to enable buttons if all required fields are selected
            self._validate_selections()
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()

    def _load_fbcyl_competitions(self) -> None:
        """Load competition options for FBCYL based on previous selections."""
        try:
            # Get current selections
            season = self.season_combo.currentText()
            gender = self.gender_combo.currentText()
            territory = self.territory_combo.currentText()
            category = self.category_combo.currentText()

            if not season or not gender or not territory or not category:
                return

            # Get values from mappings
            gender_value = self.fbcyl_gender_values.get(gender, "")
            territory_value = self.fbcyl_territory_values.get(territory, "0")
            category_value = self.fbcyl_category_values.get(category, "")

            if not category_value:
                return

            # Fetch competitions via AJAX
            competitions = self.fbcyl_scraper.fetch_competitions_ajax(
                categoria=category_value,
                genere=gender_value,
                territorial=territory_value
            )

            self.competition_combo.clear()
            self.competition_combo.addItem("")

            if competitions:
                self.fbcyl_competitions = [text for text, _ in competitions]
                self.fbcyl_competition_values = {text: value for text, value in competitions}
                self.competition_combo.addItems(self.fbcyl_competitions)
            else:
                # Add informative placeholder when no data available
                self.competition_combo.addItem("(No hay competiciones disponibles)")

            # Validate selections to enable buttons if all required fields are selected
            self._validate_selections()
        except Exception as e:
            pass
            import traceback
            traceback.print_exc()

    def _validate_selections(self) -> None:
        """Validate that all required selections are made and enable/disable buttons accordingly."""
        season = self.season_combo.currentText()

        # Helper function to check if a selection is valid (not empty and not a placeholder)
        def is_valid_selection(text: str) -> bool:
            if not text:
                return False
            # Exclude placeholder texts
            if text.startswith("(") and text.endswith(")"):
                return False
            return True

        if self.current_scope == "FEB":
            # FEB requires: competition, season, group
            competition = self.competition_combo.currentText()
            group = self.group_combo.currentText()
            all_selected = is_valid_selection(competition) and is_valid_selection(season) and is_valid_selection(group)
        elif self.current_scope == "FBCYL":
            # FBCYL requires: season, gender, territory, category, competition
            gender = self.gender_combo.currentText()
            territory = self.territory_combo.currentText()
            category = self.category_combo.currentText()
            competition = self.competition_combo.currentText()
            all_selected = (is_valid_selection(season) and
                          is_valid_selection(gender) and
                          is_valid_selection(territory) and
                          is_valid_selection(category) and
                          is_valid_selection(competition))

        else:
            # No scope selected
            all_selected = False

        # Enable or disable buttons based on selection status
        self.stats_button.setEnabled(all_selected)
        self.player_stats_button.setEnabled(all_selected)
        self.shotchart_button.setEnabled(all_selected)
        self.ai_analysis_button.setEnabled(all_selected)
        self.temporal_button.setEnabled(all_selected)
        self.rankings_button.setEnabled(all_selected)
        self.weekly_report_button.setEnabled(all_selected)

    def on_view_stats(self) -> None:
        """Handle stats button click - downloads latest data and shows statistics."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()

            # Validate selections based on scope
            if self.current_scope == "FEB":
                group_text = self.group_combo.currentText()
                if not all([competition, season_text, group_text]):
                    QMessageBox.warning(self, "Aviso", "Por favor, seleccione todas las opciones antes de continuar.")
                    return
            elif self.current_scope == "FBCYL":
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()
                if not all([competition, season_text, gender, territory, category]):
                    QMessageBox.warning(self, "Aviso", "Por favor, seleccione todas las opciones antes de continuar.")
                    return
                # For FBCYL, group is not used, set a default value
                group_text = "default"
            else:
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione un ámbito (FEB o FBCYL).")
                return

            # Update data first
            if self.current_scope == "FEB":
                season_value = self.season_values.get(season_text, normalize_year(season_text))
                group_value = self.group_values.get(group_text, group_text)
                norm_year = normalize_year(season_text)
                session = requests.Session()

                # Update progress bar visibility
                self.progress_bar.setVisible(True)
                self.progress_label.setVisible(True)

                # Get the URL for this competition
                competition_url = self.competition_urls.get(competition)
                if not competition_url:
                    QMessageBox.warning(self, "Error", f"No se encontró URL para la competición: {competition}")
                    return

                matches = self.scraper.get_matches(season_value, group_value, norm_year, session, competition_url)
                if not matches:
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para actualizar.")
                    return

                collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

            elif self.current_scope == "FBCYL":
                # Get competition ID from mapping
                competition_id = self.fbcyl_competition_values.get(competition)
                if not competition_id:
                    QMessageBox.warning(self, "Error", f"No se encontró ID para la competición: {competition}")
                    return

                # Update progress bar visibility
                self.progress_bar.setVisible(True)
                self.progress_label.setVisible(True)
                self.progress_label.setText("Progreso: Obteniendo lista de partidos...")
                QApplication.processEvents()

                # Get match UUIDs from FBCYL
                matches = self.fbcyl_scraper.get_matches(competition_id, round_number=0)
                if not matches:
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para esta competición.")
                    return

                # For FBCYL, create a descriptive collection name format:
                # FBCYL_{Gender}_{Territory}_{Category}_{Season}
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()

                # Sanitize names for MongoDB collection naming (remove special chars, spaces)
                import re
                safe_gender = re.sub(r'[^\w]', '', gender.replace(' ', '_'))
                safe_territory = re.sub(r'[^\w]', '', territory.replace(' ', '_'))
                safe_category = re.sub(r'[^\w]', '', category.replace(' ', '_'))
                safe_season = re.sub(r'[^\w]', '', season_text.replace(' ', '_').replace('/', '_'))

                collection_name = f"FBCYL_{safe_gender}_{safe_territory}_{safe_category}_{safe_season}"
            else:
                return

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            self.progress_label.setText("Progreso: Actualizando datos...")
            QApplication.processEvents()

            successful_matches = []
            failed_matches = []

            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Progreso: Procesando partido {i}/{len(matches)}")
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    if self.current_scope == "FEB":
                        # FEB: match_code is a string number, check with int
                        if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                            boxscore = self.scraper.fetch_boxscore(match_code, session)
                            if boxscore and self.db_handler.insert_boxscore(collection_name, match_code, boxscore):
                                successful_matches.append(match_code)
                            else:
                                failed_matches.append(match_code)
                        else:
                            successful_matches.append(match_code)

                    elif self.current_scope == "FBCYL":
                        # FBCYL: match_code is a UUID string
                        # Check if document already exists in the collection
                        if not self.db_handler.document_exists(collection_name, match_code) or i == len(matches):
                            # Fetch complete match data (both moves and stats)
                            match_complete_data = self.fbcyl_scraper.get_match_complete_data(match_code)

                            if match_complete_data:
                                # Insert FBCYL match data into database
                                # The document will have: {uuid, moves: {...}, stats: {...}}
                                if self.db_handler.insert_fbcyl_match(collection_name, match_code, match_complete_data):
                                    successful_matches.append(match_code)
                                else:
                                    failed_matches.append(match_code)
                            else:
                                failed_matches.append(match_code)
                        else:
                            successful_matches.append(match_code)

                except Exception as e:
                    failed_matches.append(match_code)

            self.progress_label.setText("Progreso: Cargando estadísticas...")
            self.progress_bar.setValue(len(matches))
            QApplication.processEvents()

            # Now get and display the statistics
            team_stats = self.db_handler.get_team_stats(collection_name)
            if not team_stats:
                QMessageBox.information(self, "Sin datos", "No hay estadísticas disponibles para las opciones seleccionadas.")
                return

            # Get opponent statistics
            opponent_stats = self.db_handler.get_opponent_stats(collection_name)

            # Hide progress elements after completion
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            # Create reload callback function
            def reload_stats(coll_name: str, date_filter: dict = None, venue_filter: bool = None, result_filter: str = None):
                team_data = self.db_handler.get_team_stats(coll_name, date_filter, venue_filter, result_filter)
                opponent_data = self.db_handler.get_opponent_stats(coll_name, date_filter, venue_filter, result_filter)
                return team_data, opponent_data

            # Create and show the stats window with both team and opponent stats
            self.stats_window = TeamStatsWindow(
                team_stats,
                opponent_stats,
                collection_name=collection_name,
                reload_callback=reload_stats,
                db_handler=self.db_handler,
                parent=self
            )
            self.stats_window.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar las estadísticas: {str(e)}")

    def on_view_player_stats(self) -> None:
        """Handle player stats button click - downloads latest data and shows player statistics."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()

            # Validate selections based on scope
            if self.current_scope == "FEB":
                group_text = self.group_combo.currentText()
                if not all([competition, season_text, group_text]):
                    QMessageBox.warning(self, "Aviso", "Por favor, seleccione todas las opciones antes de continuar.")
                    return
            elif self.current_scope == "FBCYL":
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()
                if not all([competition, season_text, gender, territory, category]):
                    QMessageBox.warning(self, "Aviso", "Por favor, seleccione todas las opciones antes de continuar.")
                    return
                group_text = "default"  # FBCYL doesn't use groups
            else:
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione un ámbito (FEB o FBCYL).")
                return

            # Update data first
            session = requests.Session()

            # Update progress bar visibility
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)

            if self.current_scope == "FEB":
                season_value = self.season_values.get(season_text, normalize_year(season_text))
                group_value = self.group_values.get(group_text, group_text)
                norm_year = normalize_year(season_text)

                # Get competition URL
                competition_url = self.competition_urls.get(competition)
                if not competition_url:
                    QMessageBox.warning(self, "Error", f"No se encontró URL para la competición: {competition}")
                    return

                matches = self.scraper.get_matches(season_value, group_value, norm_year, session, competition_url)
                if not matches:
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para actualizar.")
                    return

                collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

            elif self.current_scope == "FBCYL":
                # Get competition ID from mapping
                competition_id = self.fbcyl_competition_values.get(competition)
                if not competition_id:
                    QMessageBox.warning(self, "Error", f"No se encontró ID para la competición: {competition}")
                    return

                self.progress_label.setText("Progreso: Obteniendo lista de partidos...")
                QApplication.processEvents()

                # Get match UUIDs from FBCYL
                matches = self.fbcyl_scraper.get_matches(competition_id, round_number=0)
                if not matches:
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para esta competición.")
                    return

                # Create collection name for FBCYL
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()

                import re
                safe_gender = re.sub(r'[^\w]', '', gender.replace(' ', '_'))
                safe_territory = re.sub(r'[^\w]', '', territory.replace(' ', '_'))
                safe_category = re.sub(r'[^\w]', '', category.replace(' ', '_'))
                safe_season = re.sub(r'[^\w]', '', season_text.replace(' ', '_').replace('/', '_'))

                collection_name = f"FBCYL_{safe_gender}_{safe_territory}_{safe_category}_{safe_season}"
            else:
                return

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            self.progress_label.setText("Progreso: Actualizando datos...")
            QApplication.processEvents()

            # Update matches based on scope
            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Progreso: Procesando partido {i}/{len(matches)}")
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    if self.current_scope == "FEB":
                        if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                            boxscore = self.scraper.fetch_boxscore(match_code, session)
                            if boxscore:
                                self.db_handler.insert_boxscore(collection_name, match_code, boxscore)
                    elif self.current_scope == "FBCYL":
                        if not self.db_handler.document_exists(collection_name, match_code) or i == len(matches):
                            match_complete_data = self.fbcyl_scraper.get_match_complete_data(match_code)
                            if match_complete_data:
                                self.db_handler.insert_fbcyl_match(collection_name, match_code, match_complete_data)
                except Exception as e:
                    pass

            self.progress_label.setText("Progreso: Cargando estadísticas de jugadoras...")
            self.progress_bar.setValue(len(matches))
            QApplication.processEvents()

            # Get player statistics
            player_stats = self.db_handler.get_player_stats(collection_name)

            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            if not player_stats:
                QMessageBox.information(
                    self,
                    "Sin datos",
                    "No hay estadísticas de jugadoras disponibles para las opciones seleccionadas.\n\n"
                    "Esto puede ocurrir si:\n"
                    "• No se han descargado datos para esta competición aún\n"
                    "• Los partidos no tienen jugadoras con tiempo de juego registrado\n"
                    "• La descarga de datos no se completó correctamente\n\n"
                    f"Colección: {collection_name}"
                )
                return

            # Import here to avoid circular imports
            from .player_stats_window import PlayerStatsWindow

            # Create reload callback function for player stats
            def reload_player_stats(coll_name: str, date_filter: dict = None, venue_filter: bool = None, result_filter: str = None):
                return self.db_handler.get_player_stats(coll_name, date_filter, venue_filter, result_filter)

            # Create and show the player stats window
            self.player_stats_window = PlayerStatsWindow(
                player_stats,
                collection_name=collection_name,
                reload_callback=reload_player_stats,
                db_handler=self.db_handler,
                parent=self
            )
            self.player_stats_window.show()

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error al cargar las estadísticas de jugadoras: {str(e)}")

    def on_view_shotcharts(self) -> None:
        """Handle shot chart button click."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()

            # Validate selections based on scope
            if self.current_scope == "FEB":
                group_text = self.group_combo.currentText()
                if not all([competition, season_text, group_text]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de ver los gráficos de lanzamiento.")
                    return
            elif self.current_scope == "FBCYL":
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()
                if not all([competition, season_text, gender, territory, category]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de ver los gráficos de lanzamiento.")
                    return
                group_text = "default"
            else:
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione un ámbito (FEB o FBCYL).")
                return

            # Update data first
            session = requests.Session()

            # Update progress bar visibility
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)

            if self.current_scope == "FEB":
                season_value = self.season_values.get(season_text, normalize_year(season_text))
                group_value = self.group_values.get(group_text, group_text)
                norm_year = normalize_year(season_text)

                competition_url = self.competition_urls.get(competition)
                if not competition_url:
                    QMessageBox.warning(self, "Error", f"No se encontró URL para la competición: {competition}")
                    return

                matches = self.scraper.get_matches(season_value, group_value, norm_year, session, competition_url)
                if not matches:
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para actualizar.")
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    return

                collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

            elif self.current_scope == "FBCYL":
                competition_id = self.fbcyl_competition_values.get(competition)
                if not competition_id:
                    QMessageBox.warning(self, "Error", f"No se encontró ID para la competición: {competition}")
                    return

                matches = self.fbcyl_scraper.get_matches(competition_id, round_number=0)
                if not matches:
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para esta competición.")
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    return

                # Create collection name for FBCYL
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()

                import re
                safe_gender = re.sub(r'[^\w]', '', gender.replace(' ', '_'))
                safe_territory = re.sub(r'[^\w]', '', territory.replace(' ', '_'))
                safe_category = re.sub(r'[^\w]', '', category.replace(' ', '_'))
                safe_season = re.sub(r'[^\w]', '', season_text.replace(' ', '_').replace('/', '_'))

                collection_name = f"FBCYL_{safe_gender}_{safe_territory}_{safe_category}_{safe_season}"
            else:
                return

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            self.progress_label.setText("Progreso: Actualizando datos...")
            QApplication.processEvents()

            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Progreso: Procesando partido {i}/{len(matches)}")
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    if self.current_scope == "FEB":
                        if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                            boxscore = self.scraper.fetch_boxscore(match_code, session)
                            if boxscore:
                                self.db_handler.insert_boxscore(collection_name, match_code, boxscore)
                    elif self.current_scope == "FBCYL":
                        if not self.db_handler.document_exists(collection_name, match_code) or i == len(matches):
                            match_complete_data = self.fbcyl_scraper.get_match_complete_data(match_code)
                            if match_complete_data:
                                self.db_handler.insert_fbcyl_match(collection_name, match_code, match_complete_data)
                except Exception as e:
                    pass

            self.progress_label.setText("Progreso: Cargando gráficos de lanzamiento...")
            self.progress_bar.setValue(len(matches))
            QApplication.processEvents()

            # Hide progress elements
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            # Create and show shot chart window
            self.shotchart_window = ShotChartWindow(
                self.db_handler,
                self.scraper,
                collection_name,
                self
            )
            self.shotchart_window.show()

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error al abrir ventana de gráficos de lanzamiento: {str(e)}")

    def on_view_ai_analysis(self) -> None:
        """Handle AI analysis button click - auto-loads all required data."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()

            # Validate selections based on scope
            if self.current_scope == "FEB":
                group_text = self.group_combo.currentText()
                if not all([competition, season_text, group_text]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de realizar el análisis IA.")
                    return
                collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)
            elif self.current_scope == "FBCYL":
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()
                if not all([competition, season_text, gender, territory, category]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de realizar el análisis IA.")
                    return
                group_text = "default"

                # Create collection name for FBCYL
                import re
                safe_gender = re.sub(r'[^\w]', '', gender.replace(' ', '_'))
                safe_territory = re.sub(r'[^\w]', '', territory.replace(' ', '_'))
                safe_category = re.sub(r'[^\w]', '', category.replace(' ', '_'))
                safe_season = re.sub(r'[^\w]', '', season_text.replace(' ', '_').replace('/', '_'))
                collection_name = f"FBCYL_{safe_gender}_{safe_territory}_{safe_category}_{safe_season}"
            else:
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione un ámbito (FEB o FBCYL).")
                return

            # Update all data first (boxscores + shotcharts)
            success = self._update_data_for_ai_analysis(competition, season_text, group_text, collection_name)

            if not success:
                return  # Error message already shown by _update_data_for_ai_analysis

            # Build team list from collection documents
            teams = get_available_teams_from_collection(self.db_handler, collection_name)
            if not teams:
                QMessageBox.warning(self, "Sin Datos", "No hay equipos disponibles en esta selección.")
                return

            # Adapt to selector expected structure (name + teamCode)
            teams_data = [
                {"name": t.get("name", ""), "teamCode": t.get("code", ""), "id": t.get("id", "")}
                for t in teams
            ]

            # Import here to avoid circular imports
            from .ai_team_selector import AITeamSelector

            # Show team selector dialog
            selector = AITeamSelector(teams_data, collection_name, self.db_handler, parent=self)
            selector.show()

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error al abrir análisis IA: {str(e)}")

    def _update_data_for_ai_analysis(self, competition: str, season_text: str, group_text: str, collection_name: str) -> bool:
        """
        Update boxscore and shotchart data for AI analysis.
        Returns True if successful, False otherwise.
        """
        try:
            session = requests.Session()

            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)
            self.progress_label.setText("🤖 Paso 1/3: Obteniendo lista de partidos...")
            self.progress_bar.setMaximum(0)  # Indeterminate
            QApplication.processEvents()

            # Get matches based on scope
            if self.current_scope == "FEB":
                season_value = self.season_values.get(season_text, normalize_year(season_text))
                group_value = self.group_values.get(group_text, group_text)
                norm_year = normalize_year(season_text)

                competition_url = self.competition_urls.get(competition)
                if not competition_url:
                    QMessageBox.warning(self, "Error", f"No se encontró URL para la competición: {competition}")
                    return False

                matches = self.scraper.get_matches(season_value, group_value, norm_year, session, competition_url)
                if not matches:
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    QMessageBox.information(
                        self,
                        "Sin datos",
                        f"No se encontraron partidos para {group_text}.\n\n"
                        f"Esto puede ocurrir si:\n"
                        f"• Los partidos aún no se han jugado\n"
                        f"• Los resultados no están publicados en la web de la FEB\n"
                        f"• El grupo seleccionado no tiene calendario disponible"
                    )
                    return False

            elif self.current_scope == "FBCYL":
                competition_id = self.fbcyl_competition_values.get(competition)
                if not competition_id:
                    QMessageBox.warning(self, "Error", f"No se encontró ID para la competición: {competition}")
                    return False

                matches = self.fbcyl_scraper.get_matches(competition_id, round_number=0)
                if not matches:
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para esta competición.")
                    return False
            else:
                return False

            # Step 2: Update boxscores
            self.progress_label.setText(f"🤖 Paso 2/3: Actualizando estadísticas de {len(matches)} partidos...")
            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            QApplication.processEvents()

            for i, match_code in enumerate(matches, 1):
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    if self.current_scope == "FEB":
                        if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                            boxscore = self.scraper.fetch_boxscore(match_code, session)
                            if boxscore:
                                self.db_handler.insert_boxscore(collection_name, match_code, boxscore)
                    elif self.current_scope == "FBCYL":
                        if not self.db_handler.document_exists(collection_name, match_code) or i == len(matches):
                            match_complete_data = self.fbcyl_scraper.get_match_complete_data(match_code)
                            if match_complete_data:
                                self.db_handler.insert_fbcyl_match(collection_name, match_code, match_complete_data)
                except Exception as e:
                    pass  # Silently continue with other matches

            # Step 3: Update shotcharts
            self.progress_label.setText(f"🤖 Paso 3/3: Actualizando datos de lanzamientos...")
            self.progress_bar.setValue(0)
            QApplication.processEvents()

            collection = self.db_handler.connection.get_collection(collection_name)
            if collection is None:
                self.progress_bar.setVisible(False)
                self.progress_label.setVisible(False)
                QMessageBox.warning(self, "Error", "No se pudo acceder a la colección de datos.")
                return False

            documents = list(collection.find({}))
            self.progress_bar.setMaximum(len(documents))

            updated_shotcharts = 0
            for i, doc in enumerate(documents, 1):
                match_code = str(doc.get('_id', ''))
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                # Skip if shotchart already exists
                if 'SHOTCHART' in doc and doc['SHOTCHART']:
                    continue

                try:
                    token = self.scraper.token_manager.get_token()
                    shotchart_data = self.scraper.fetch_shotchart(match_code, session, token)

                    if shotchart_data:
                        collection.update_one(
                            {'_id': int(match_code)},
                            {'$set': {'SHOTCHART': shotchart_data}}
                        )
                        updated_shotcharts += 1
                except Exception as e:
                    pass  # Silently continue with other matches

            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            return True

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error actualizando datos: {str(e)}")
            return False

    def update_group_options(self) -> None:
        """Update the group dropdown."""
        selected_competition = self.competition_combo.currentText()
        self.group_combo.clear()

        if not selected_competition:  # If no competition selected
            self.group_label.setText("Selected Group: ")
            self._validate_selections()
            return

        groups = self.group_options.get(selected_competition, [])
        if groups:
            self.group_combo.addItem("")  # Add empty item first
            self.group_combo.addItems([text for text, value in groups])
            self.group_values = {text: value for text, value in groups}
            self.group_label.setText("Selected Group: ")
        else:
            self.group_label.setText("Selected Group: ")

        self._validate_selections()

    def on_view_temporal_evolution(self) -> None:
        """Handle temporal evolution button click."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()

            # Validate selections based on scope
            if self.current_scope == "FEB":
                group_text = self.group_combo.currentText()
                if not all([competition, season_text, group_text]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de ver la evolución temporal.")
                    return
                collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)
            elif self.current_scope == "FBCYL":
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()
                if not all([competition, season_text, gender, territory, category]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de ver la evolución temporal.")
                    return

                # Create collection name for FBCYL
                import re
                safe_gender = re.sub(r'[^\w]', '', gender.replace(' ', '_'))
                safe_territory = re.sub(r'[^\w]', '', territory.replace(' ', '_'))
                safe_category = re.sub(r'[^\w]', '', category.replace(' ', '_'))
                safe_season = re.sub(r'[^\w]', '', season_text.replace(' ', '_').replace('/', '_'))
                collection_name = f"FBCYL_{safe_gender}_{safe_territory}_{safe_category}_{safe_season}"
                group_text = "default"
            else:
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione un ámbito (FEB o FBCYL).")
                return

            # Check if collection has data
            try:
                collection = self.db_handler.connection.get_collection(collection_name)
                if collection is None or collection.count_documents({}) == 0:
                    QMessageBox.information(
                        self,
                        "Sin datos",
                        f"No hay datos disponibles para {group_text}.\n\n"
                        f"Por favor, use primero el botón '📊 Estadísticas' para descargar los datos."
                    )
                    return
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Error",
                    f"Error al verificar datos: {str(e)}\n\n"
                    f"Por favor, use primero el botón '📊 Estadísticas' para descargar los datos."
                )
                return

            # Create and show temporal evolution window
            self.temporal_window = TemporalEvolutionWindow(
                collection_name=collection_name,
                db_handler=self.db_handler,
                is_fbcyl=(self.current_scope == "FBCYL"),
                parent=self
            )
            self.temporal_window.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir evolución temporal: {str(e)}")

    def on_view_rankings(self) -> None:
        """Handle rankings button click."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()

            # Validate selections based on scope
            if self.current_scope == "FEB":
                group_text = self.group_combo.currentText()
                if not all([competition, season_text, group_text]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de ver los ránkings.")
                    return
                collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)
            elif self.current_scope == "FBCYL":
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()
                if not all([competition, season_text, gender, territory, category]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de ver los ránkings.")
                    return

                # Create collection name for FBCYL
                import re
                safe_gender = re.sub(r'[^\w]', '', gender.replace(' ', '_'))
                safe_territory = re.sub(r'[^\w]', '', territory.replace(' ', '_'))
                safe_category = re.sub(r'[^\w]', '', category.replace(' ', '_'))
                safe_season = re.sub(r'[^\w]', '', season_text.replace(' ', '_').replace('/', '_'))
                collection_name = f"FBCYL_{safe_gender}_{safe_territory}_{safe_category}_{safe_season}"
                group_text = "default"
            else:
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione un ámbito (FEB o FBCYL).")
                return

            # Get player stats
            self.progress_label.setText("Cargando estadísticas de jugadores...")
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)
            QApplication.processEvents()

            player_stats = self.db_handler.get_player_stats(collection_name)

            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            if not player_stats:
                QMessageBox.information(self, "Sin datos",
                                      "No hay datos de jugadores disponibles. Por favor, actualice los datos primero.")
                return

            # Create and show rankings window
            self.rankings_window = PlayerRankingWindow(
                player_stats=player_stats,
                collection_name=collection_name,
                db_handler=self.db_handler,
                parent=self
            )
            self.rankings_window.show()

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error al cargar los ránkings: {str(e)}")

    def on_generate_weekly_report(self) -> None:
        """Handle weekly report button click."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()

            # Validate selections based on scope
            if self.current_scope == "FEB":
                group_text = self.group_combo.currentText()
                if not all([competition, season_text, group_text]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de generar el informe.")
                    return
                collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)
            elif self.current_scope == "FBCYL":
                gender = self.gender_combo.currentText()
                territory = self.territory_combo.currentText()
                category = self.category_combo.currentText()
                if not all([competition, season_text, gender, territory, category]):
                    QMessageBox.warning(self, "Aviso",
                                      "Por favor, seleccione todas las opciones antes de generar el informe.")
                    return

                # Create collection name for FBCYL
                import re
                safe_gender = re.sub(r'[^\w]', '', gender.replace(' ', '_'))
                safe_territory = re.sub(r'[^\w]', '', territory.replace(' ', '_'))
                safe_category = re.sub(r'[^\w]', '', category.replace(' ', '_'))
                safe_season = re.sub(r'[^\w]', '', season_text.replace(' ', '_').replace('/', '_'))
                collection_name = f"FBCYL_{safe_gender}_{safe_territory}_{safe_category}_{safe_season}"
                group_text = "default"
            else:
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione un ámbito (FEB o FBCYL).")
                return

            # Update data first to ensure we have the latest information
            session = requests.Session()

            # Update progress bar visibility
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)

            if self.current_scope == "FEB":
                season_value = self.season_values.get(season_text, normalize_year(season_text))
                group_value = self.group_values.get(group_text, group_text)
                norm_year = normalize_year(season_text)

                competition_url = self.competition_urls.get(competition)
                if not competition_url:
                    QMessageBox.warning(self, "Error", f"No se encontró URL para la competición: {competition}")
                    return

                self.progress_label.setText("Actualizando datos desde FEB...")
                QApplication.processEvents()

                matches = self.scraper.get_matches(season_value, group_value, norm_year, session, competition_url)
                if not matches:
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para actualizar.")
                    return

            elif self.current_scope == "FBCYL":
                competition_id = self.fbcyl_competition_values.get(competition)
                if not competition_id:
                    QMessageBox.warning(self, "Error", f"No se encontró ID para la competición: {competition}")
                    return

                self.progress_label.setText("Actualizando datos desde FBCYL...")
                QApplication.processEvents()

                matches = self.fbcyl_scraper.get_matches(competition_id, round_number=0)
                if not matches:
                    self.progress_bar.setVisible(False)
                    self.progress_label.setVisible(False)
                    QMessageBox.information(self, "Sin datos", "No se encontraron partidos para esta competición.")
                    return
            else:
                return

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            QApplication.processEvents()

            # Update matches based on scope
            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Actualizando partido {i}/{len(matches)}...")
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    if self.current_scope == "FEB":
                        if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                            boxscore = self.scraper.fetch_boxscore(match_code, session)
                            if boxscore:
                                self.db_handler.insert_boxscore(collection_name, match_code, boxscore)
                    elif self.current_scope == "FBCYL":
                        if not self.db_handler.document_exists(collection_name, match_code) or i == len(matches):
                            match_complete_data = self.fbcyl_scraper.get_match_complete_data(match_code)
                            if match_complete_data:
                                self.db_handler.insert_fbcyl_match(collection_name, match_code, match_complete_data)
                except Exception as e:
                    pass

            # Get available teams
            self.progress_label.setText("Cargando equipos disponibles...")
            self.progress_bar.setValue(0)
            QApplication.processEvents()

            teams = get_available_teams_from_collection(self.db_handler, collection_name)
            team_names = [team['name'] for team in teams]

            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            if not team_names:
                QMessageBox.information(self, "Sin equipos",
                                      "No hay equipos disponibles en la base de datos.")
                return

            # Show dialog to select teams and output folder
            dialog = WeeklyReportDialog(team_names, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            config = dialog.get_configuration()
            if not config:
                return

            # Create progress dialog
            progress_dialog = QMessageBox(self)
            progress_dialog.setIcon(QMessageBox.Icon.Information)
            progress_dialog.setWindowTitle("Generando Informe Semanal")
            progress_dialog.setText("Generando informes, por favor espere...")
            progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
            progress_dialog.show()
            QApplication.processEvents()

            # Generate report (pass scraper instance)
            generator = WeeklyReportGenerator(self.db_handler, collection_name, self.scraper, self)

            # Connect signals
            def on_progress(message: str, percentage: int):
                progress_dialog.setText(f"{message}\n\nProgreso: {percentage}%")
                QApplication.processEvents()

            def on_completed(success: bool, message: str):
                # Close progress dialog first
                progress_dialog.close()
                progress_dialog.deleteLater()
                QApplication.processEvents()

                # Then show result message
                if success:
                    QMessageBox.information(self, "Informe Completado", message)
                else:
                    QMessageBox.critical(self, "Error", message)

            generator.progress_updated.connect(on_progress)
            generator.report_completed.connect(on_completed)

            # Start generation
            generator.generate_report(
                config['team_a'],
                config['team_b'],
                config['output_folder']
            )

            # Ensure dialog is closed after generation completes
            if progress_dialog.isVisible():
                progress_dialog.close()
                progress_dialog.deleteLater()

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error al cargar los ránkings: {str(e)}")
