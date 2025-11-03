"""Main application window for basketball season selection."""

import requests
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QComboBox, QLabel,
                              QProgressBar, QPushButton, QMessageBox, QApplication)
from typing import List, Dict

from scraper import FEBWebScraper
from database import MongoDBHandler
from utils import normalize_year
from .stats_window import TeamStatsWindow
from .shotchart_window import ShotChartWindow


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

        # Competition ComboBox
        self.competition_combo = QComboBox()
        self.competition_combo.addItem("")  # Add empty item
        self.competition_combo.addItems(self.competitions)
        self.competition_combo.currentTextChanged.connect(self.on_competition_select)
        layout.addWidget(self.competition_combo)

        self.competition_label = QLabel("Competición seleccionada: ")
        layout.addWidget(self.competition_label)

        # Season ComboBox
        self.season_combo = QComboBox()
        self.season_combo.addItem("")  # Add empty item
        self.season_combo.addItems(self.seasons)
        self.season_combo.currentTextChanged.connect(self.on_season_select)
        layout.addWidget(self.season_combo)

        self.season_label = QLabel("Temporada seleccionada: ")
        layout.addWidget(self.season_label)

        # Group ComboBox
        self.group_combo = QComboBox()
        self.group_combo.currentTextChanged.connect(self.on_group_select)
        layout.addWidget(self.group_combo)

        self.group_label = QLabel("Grupo seleccionado: ")
        layout.addWidget(self.group_label)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Progress Label
        self.progress_label = QLabel("Progreso: Esperando para comenzar")
        layout.addWidget(self.progress_label)

        # View Stats Button
        self.stats_button = QPushButton("📊 Estadísticas")
        self.stats_button.clicked.connect(self.on_view_stats)
        layout.addWidget(self.stats_button)

        # Shot Chart Button
        self.shotchart_button = QPushButton("🎯 Gráficos de Tiro")
        self.shotchart_button.clicked.connect(self.on_view_shotcharts)
        self.shotchart_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border-radius: 5px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        layout.addWidget(self.shotchart_button)

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

    def on_competition_select(self, competition: str) -> None:
        """Handle competition selection event."""
        if not competition:  # If empty selection
            self.competition_label.setText("Competición seleccionada: ")
            self.season_combo.clear()
            self.season_combo.addItem("")
            self.season_combo.addItems(self.seasons)  # Show all seasons
            self.update_group_options()  # This will clear the group combo
            return

        self.competition_label.setText(f"Competición seleccionada: {competition}")
        # Reset season and group selections when competition changes
        self.season_combo.setCurrentText("")
        self.update_group_options()

    def on_season_select(self, season: str) -> None:
        """Handle season selection event."""
        if not season:  # If empty selection
            self.season_label.setText("Temporada seleccionada: ")
            return

        self.season_label.setText(f"Temporada seleccionada: {season}")
        competition = self.competition_combo.currentText()

        if not competition:
            return

        if competition == "L.F. 2":
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

    def on_group_select(self, group: str) -> None:
        """Handle group selection event."""
        self.group_label.setText(f"Grupo seleccionado: {group}")

    def on_view_stats(self) -> None:
        """Handle stats button click - downloads latest data and shows statistics."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()
            group_text = self.group_combo.currentText()

            if not all([competition, season_text, group_text]):
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione todas las opciones antes de continuar.")
                return

            # Update data first
            season_value = self.season_values.get(season_text, normalize_year(season_text))
            group_value = self.group_values.get(group_text, group_text)
            norm_year = normalize_year(season_text)
            session = requests.Session()

            # Update progress bar visibility
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)

            matches = self.scraper.get_matches(season_value, group_value, norm_year, session)
            if not matches:
                QMessageBox.information(self, "Sin datos", "No se encontraron partidos para actualizar.")
                return

            collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            self.progress_label.setText("Progreso: Actualizando datos...")
            QApplication.processEvents()

            successful_matches = []
            failed_matches = []
            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Progreso: Procesando partido {match_code}")
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    # Only download if it doesn't exist or if it's the last match (for possible updates)
                    if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                        boxscore = self.scraper.fetch_boxscore(match_code, session)
                        if boxscore and self.db_handler.insert_boxscore(collection_name, match_code, boxscore):
                            successful_matches.append(match_code)
                        else:
                            failed_matches.append(match_code)
                    else:
                        successful_matches.append(match_code)
                except Exception as e:
                    print(f"[App] Error processing match {match_code}: {str(e)}")
                    failed_matches.append(match_code)

            self.progress_label.setText("Progreso: Cargando estadísticas...")
            self.progress_bar.setValue(len(matches))
            QApplication.processEvents()

            # Now get and display the statistics
            team_stats = self.db_handler.get_team_stats(collection_name)
            if not team_stats:
                QMessageBox.information(self, "Sin datos", "No hay estadísticas disponibles para las opciones seleccionadas.")
                return

            # Hide progress elements after completion
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            # Create and show the stats window
            self.stats_window = TeamStatsWindow(team_stats, self)
            self.stats_window.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al cargar las estadísticas: {str(e)}")

    def on_view_shotcharts(self) -> None:
        """Handle shot chart button click."""
        try:
            if not self.db_handler.is_connected():
                QMessageBox.critical(self, "Error", "No hay conexión con MongoDB. Por favor, verifique el servidor.")
                return

            competition = self.competition_combo.currentText()
            season_text = self.season_combo.currentText()
            group_text = self.group_combo.currentText()

            if not all([competition, season_text, group_text]):
                QMessageBox.warning(self, "Aviso", 
                                  "Por favor, seleccione competición, temporada y grupo antes de ver shot charts.")
                return

            # Update data first (same as on_view_stats)
            season_value = self.season_values.get(season_text, normalize_year(season_text))
            group_value = self.group_values.get(group_text, group_text)
            norm_year = normalize_year(season_text)
            session = requests.Session()

            # Update progress bar visibility
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)

            matches = self.scraper.get_matches(season_value, group_value, norm_year, session)
            if not matches:
                QMessageBox.information(self, "Sin datos", "No se encontraron partidos para actualizar.")
                self.progress_bar.setVisible(False)
                self.progress_label.setVisible(False)
                return

            collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            self.progress_label.setText("Progreso: Actualizando datos...")
            QApplication.processEvents()

            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Progreso: Procesando partido {match_code}")
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    # Only download if it doesn't exist or if it's the last match (for possible updates)
                    if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                        boxscore = self.scraper.fetch_boxscore(match_code, session)
                        if boxscore:
                            self.db_handler.insert_boxscore(collection_name, match_code, boxscore)
                except Exception as e:
                    print(f"[App] Error processing match {match_code}: {str(e)}")

            self.progress_label.setText("Progreso: Cargando shot charts...")
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
            QMessageBox.critical(self, "Error", f"Error al abrir ventana de shot charts: {str(e)}")

    def update_group_options(self) -> None:
        """Update the group dropdown."""
        selected_competition = self.competition_combo.currentText()
        self.group_combo.clear()

        if not selected_competition:  # If no competition selected
            self.group_label.setText("Selected Group: ")
            return

        groups = self.group_options.get(selected_competition, [])
        if groups:
            self.group_combo.addItem("")  # Add empty item first
            self.group_combo.addItems([text for text, value in groups])
            self.group_values = {text: value for text, value in groups}
            self.group_label.setText("Selected Group: ")
        else:
            self.group_label.setText("Selected Group: ")
