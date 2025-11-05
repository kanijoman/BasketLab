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

        # AI Analysis Button
        self.ai_analysis_button = QPushButton("🤖 Análisis IA")
        self.ai_analysis_button.clicked.connect(self.on_view_ai_analysis)
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
        """)
        layout.addWidget(self.ai_analysis_button)

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
            teams = self._get_available_teams_for_collection(collection_name)
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
                QMessageBox.information(self, "Sin datos", "No se encontraron partidos para esta selección.")
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
                    print(f"[AI] Error processing boxscore for match {match_code}: {str(e)}")

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
                    print(f"[AI] Error fetching shotchart for match {match_code}: {str(e)}")

            # Hide progress bar
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)

            return True

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.progress_label.setVisible(False)
            QMessageBox.critical(self, "Error", f"Error actualizando datos: {str(e)}")
            return False

    def _get_available_teams_for_collection(self, collection_name: str) -> List[Dict]:
        """Extract available teams from a collection (mirrors ShotChartWindow logic)."""
        try:
            collection = self.db_handler.connection.get_collection(collection_name)
            if collection is None:
                return []

            documents = list(collection.find({}))
            teams_dict = {}

            for doc in documents:
                # Primary source: BOXSCORE.TEAM list
                if 'BOXSCORE' in doc and 'TEAM' in doc['BOXSCORE']:
                    teams = doc['BOXSCORE']['TEAM']
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict) and 'TOTAL' in team:
                                team_data = team['TOTAL']
                                team_code = team_data.get('teamCode', '')
                                team_name = team_data.get('name', '')
                                team_id = team_data.get('id', '')

                                if team_code and team_name and team_code not in teams_dict:
                                    teams_dict[team_code] = {
                                        'name': team_name,
                                        'code': team_code,
                                        'id': team_id,
                                        'team_index': None
                                    }

                # Fallback: HEADER.TEAM
                elif 'HEADER' in doc and 'TEAM' in doc['HEADER']:
                    teams = doc['HEADER']['TEAM']
                    if isinstance(teams, list):
                        for team in teams:
                            if isinstance(team, dict):
                                team_code = team.get('teamCode', '')
                                team_name = team.get('name', '')
                                team_id = team.get('id', '')

                                if team_code and team_name and team_code not in teams_dict:
                                    teams_dict[team_code] = {
                                        'name': team_name,
                                        'code': team_code,
                                        'id': team_id,
                                        'team_index': None
                                    }

            return sorted(teams_dict.values(), key=lambda x: x['name'])
        except Exception:
            return []

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
