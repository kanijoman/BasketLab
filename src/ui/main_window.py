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
from .ai_analysis_window import AIAnalysisWindow
from .temporal_evolution_window import TemporalEvolutionWindow
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
        self.competitions = ["L.F. 2", "Primera Nacional"]
        self.group_options = {}
        self.group_values = {}
        self.setWindowTitle("MfA - Metrics for All")
        self.setMinimumSize(400, 400)

        # Set application icon
        set_app_icon(self)

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

    def on_competition_select(self, competition: str) -> None:
        """Handle competition selection event."""
        if not competition:  # If empty selection
            self.competition_label.setText("Competición seleccionada: ")
            self.season_combo.clear()
            self.season_combo.addItem("")
            self.season_combo.addItems(self.seasons)  # Show all seasons
            self.update_group_options()  # This will clear the group combo
            self._validate_selections()
            return

        self.competition_label.setText(f"Competición seleccionada: {competition}")
        # Reset season and group selections when competition changes
        self.season_combo.setCurrentText("")
        self._validate_selections()
        self.update_group_options()

    def on_season_select(self, season: str) -> None:
        """Handle season selection event."""
        if not season:  # If empty selection
            self.season_label.setText("Temporada seleccionada: ")
            self._validate_selections()
            return

        self.season_label.setText(f"Temporada seleccionada: {season}")
        self._validate_selections()
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
        self._validate_selections()

    def _validate_selections(self) -> None:
        """Validate that all required selections are made and enable/disable buttons accordingly."""
        competition = self.competition_combo.currentText()
        season = self.season_combo.currentText()
        group = self.group_combo.currentText()

        # Check if all fields have valid (non-empty) selections
        all_selected = bool(competition) and bool(season) and bool(group)

        # Enable or disable buttons based on selection status
        self.stats_button.setEnabled(all_selected)
        self.player_stats_button.setEnabled(all_selected)
        self.shotchart_button.setEnabled(all_selected)
        self.ai_analysis_button.setEnabled(all_selected)
        self.temporal_button.setEnabled(all_selected)

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
            group_text = self.group_combo.currentText()

            if not all([competition, season_text, group_text]):
                QMessageBox.warning(self, "Aviso", "Por favor, seleccione todas las opciones antes de continuar.")
                return

            # Update data first (same logic as on_view_stats)
            season_value = self.season_values.get(season_text, normalize_year(season_text))
            group_value = self.group_values.get(group_text, group_text)
            norm_year = normalize_year(season_text)
            session = requests.Session()

            # Update progress bar visibility
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)

            matches = self.scraper.get_matches(season_value, group_value, norm_year, session)
            if not matches:
                self.progress_bar.setVisible(False)
                self.progress_label.setVisible(False)
                QMessageBox.information(self, "Sin datos", "No se encontraron partidos para actualizar.")
                return

            collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            self.progress_label.setText("Progreso: Actualizando datos...")
            QApplication.processEvents()

            # Update matches
            for i, match_code in enumerate(matches, 1):
                self.progress_label.setText(f"Progreso: Procesando partido {match_code}")
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                        boxscore = self.scraper.fetch_boxscore(match_code, session)
                        if boxscore:
                            self.db_handler.insert_boxscore(collection_name, match_code, boxscore)
                except Exception as e:
                    print(f"[App] Error processing match {match_code}: {str(e)}")

            self.progress_label.setText("Progreso: Cargando estadísticas de jugadoras...")
            self.progress_bar.setValue(len(matches))
            QApplication.processEvents()

            # Get player statistics
            player_stats = self.db_handler.get_player_stats(collection_name)

            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            if not player_stats:
                QMessageBox.information(self, "Sin datos", "No hay estadísticas de jugadoras disponibles para las opciones seleccionadas.")
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
            group_text = self.group_combo.currentText()

            if not all([competition, season_text, group_text]):
                QMessageBox.warning(self, "Aviso",
                                  "Por favor, seleccione competición, temporada y grupo antes de ver los gráficos de lanzamiento.")
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
            group_text = self.group_combo.currentText()

            if not all([competition, season_text, group_text]):
                QMessageBox.warning(self, "Aviso",
                                  "Por favor, seleccione competición, temporada y grupo antes de realizar el análisis IA.")
                return

            # Get collection name
            collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

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
            # Prepare session and parameters
            season_value = self.season_values.get(season_text, normalize_year(season_text))
            group_value = self.group_values.get(group_text, group_text)
            norm_year = normalize_year(season_text)
            session = requests.Session()

            # Show progress bar
            self.progress_bar.setVisible(True)
            self.progress_label.setVisible(True)
            self.progress_label.setText("🤖 Paso 1/3: Obteniendo lista de partidos...")
            self.progress_bar.setMaximum(0)  # Indeterminate
            QApplication.processEvents()

            # Get matches
            matches = self.scraper.get_matches(season_value, group_value, norm_year, session)
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

            # Step 2: Update boxscores
            self.progress_label.setText(f"🤖 Paso 2/3: Actualizando estadísticas de {len(matches)} partidos...")
            self.progress_bar.setMaximum(len(matches))
            self.progress_bar.setValue(0)
            QApplication.processEvents()

            for i, match_code in enumerate(matches, 1):
                self.progress_bar.setValue(i)
                QApplication.processEvents()

                try:
                    # Only download if it doesn't exist or if it's the last match
                    if not self.db_handler.document_exists(collection_name, int(match_code)) or i == len(matches):
                        boxscore = self.scraper.fetch_boxscore(match_code, session)
                        if boxscore:
                            self.db_handler.insert_boxscore(collection_name, match_code, boxscore)
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
            group_text = self.group_combo.currentText()

            if not all([competition, season_text, group_text]):
                QMessageBox.warning(self, "Aviso",
                                  "Por favor, seleccione competición, temporada y grupo antes de ver la evolución temporal.")
                return

            # Get collection name
            collection_name = self.db_handler.get_collection_name(competition, season_text, group_text)

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
                parent=self
            )
            self.temporal_window.show()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error al abrir evolución temporal: {str(e)}")
