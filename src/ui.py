import requests
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QComboBox, QLabel,
                           QProgressBar, QPushButton, QMessageBox, QTableWidget,
                           QTableWidgetItem, QHeaderView, QHBoxLayout, QApplication)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
import numpy as np
from typing import List, Dict, Optional
from scraper import FEBWebScraper
from database import MongoDBHandler
from utils import normalize_year

class TeamStatsWindow(QMainWindow):
    """Window to display team statistics."""

    def __init__(self, team_stats: List[Dict], parent=None):
        """Initialize the team stats window."""
        super().__init__(parent)
        self.setWindowTitle("Estadísticas de Equipo")
        # Set a reasonable minimum window size considering all columns
        self.setMinimumSize(1200, 600)
        self.setup_ui(team_stats)

    def get_quartile_color(self, value: float, quartiles: List[float], reverse: bool = False) -> QColor:
        """Get color based on quartile value."""
        if reverse:
            if value <= quartiles[0]:
                return QColor(144, 238, 144)  # Light green
            elif value <= quartiles[1]:
                return QColor(255, 255, 153)  # Light yellow
            elif value <= quartiles[2]:
                return QColor(255, 200, 87)   # Light orange
            else:
                return QColor(255, 153, 153)  # Light red
        else:
            if value >= quartiles[2]:
                return QColor(144, 238, 144)  # Light green
            elif value >= quartiles[1]:
                return QColor(255, 255, 153)  # Light yellow
            elif value >= quartiles[0]:
                return QColor(255, 200, 87)   # Light orange
            else:
                return QColor(255, 153, 153)  # Light red

    def calculate_quartiles(self, values: List[float]) -> List[float]:
        """Calculate quartiles for a list of values."""
        return [np.percentile(values, q) for q in [25, 50, 75]]

    def setup_ui(self, team_stats: List[Dict]):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Create table
        self.table = QTableWidget()
        layout.addWidget(self.table)

        # Define columns
        columns = [
            "Equipo", "Total Partidos", "Local", "Visitante",
            "Puntos a Favor", "Puntos en Contra", "Puntos/Partido", "Puntos Contra/Partido",
            "% T2", "% T3", "% TL", "Reb. Tot.", "Reb. Def.", "Reb. Of.",
            "Asistencias", "Robos", "Pérdidas", "Tapones"
        ]

        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        # Enable sorting
        self.table.setSortingEnabled(True)

        # Set all columns to auto-resize to content
        header = self.table.horizontalHeader()
        for i in range(len(columns)):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        # Calculate quartiles for numeric columns and ensure all values are float
        def safe_float(value):
            try:
                return float(value) if value is not None else 0.0
            except (ValueError, TypeError):
                return 0.0

        numeric_data = {
            'points_scored': ([safe_float(team['points_scored']) for team in team_stats], False),
            'points_received': ([safe_float(team['points_received']) for team in team_stats], True),
            'points_per_game': ([safe_float(team['points_per_game']) for team in team_stats], False),
            'points_against_per_game': ([safe_float(team['points_against_per_game']) for team in team_stats], True),
            'fg2_percentage': ([safe_float(team['fg2_percentage']) for team in team_stats], False),
            'fg3_percentage': ([safe_float(team['fg3_percentage']) for team in team_stats], False),
            'ft_percentage': ([safe_float(team['ft_percentage']) for team in team_stats], False),
            'total_rebounds': ([safe_float(team['total_rebounds']) for team in team_stats], False),
            'rebounds_def': ([safe_float(team['rebounds_def']) for team in team_stats], False),
            'rebounds_off': ([safe_float(team['rebounds_off']) for team in team_stats], False),
            'assists': ([safe_float(team['assists']) for team in team_stats], False),
            'steals': ([safe_float(team['steals']) for team in team_stats], False),
            'turnovers': ([float(team['turnovers']) for team in team_stats], True),  # True because fewer turnovers is better
            'blocks': ([safe_float(team['blocks']) for team in team_stats], False)
        }

        quartiles = {key: self.calculate_quartiles(values) for key, (values, _) in numeric_data.items()}

        # Custom QTableWidgetItem class for proper numeric sorting
        class NumericTableWidgetItem(QTableWidgetItem):
            def __init__(self, value, text, is_numeric=True):
                super().__init__(text)
                self.is_numeric = is_numeric
                self._numeric_value = self._convert_to_numeric(value) if is_numeric else None

            def _convert_to_numeric(self, value):
                """Convert value to float."""
                if value is None:
                    return 0.0
                try:
                    return float(str(value).strip().replace(',', '.'))
                except (ValueError, TypeError, AttributeError):
                    return 0.0

            def __lt__(self, other):
                if not isinstance(other, NumericTableWidgetItem):
                    return super().__lt__(other)

                if self.is_numeric and other.is_numeric:
                    return self._numeric_value > other._numeric_value

                return self.text() < other.text()

        # Populate table
        self.table.setRowCount(len(team_stats))
        for row, team in enumerate(team_stats):

            # Team name - no color (text sorting)
            self.table.setItem(row, 0, NumericTableWidgetItem(team["team_name"], team["team_name"], False))

            # Games columns - no color (numeric sorting)
            self.table.setItem(row, 1, NumericTableWidgetItem(team["total_games"], str(team["total_games"])))
            self.table.setItem(row, 2, NumericTableWidgetItem(team["games_home"], str(team["games_home"])))
            self.table.setItem(row, 3, NumericTableWidgetItem(team["games_away"], str(team["games_away"])))

            # Points columns with colors
            def process_numeric_value(value, key):
                """Convert value to numeric and format for display."""
                try:
                    num_value = float(str(value).strip().replace(',', '.'))
                    # Display integers without decimal places
                    if num_value.is_integer():
                        return num_value, str(int(num_value))
                    return num_value, f"{num_value:.1f}"
                except (ValueError, TypeError):
                    return 0.0, "0"

            numeric_cols = []

            # Process each column with proper numeric conversion
            stats_config = [
                (4, 'points_scored', team["points_scored"]),
                (5, 'points_received', team["points_received"]),
                (6, 'points_per_game', team['points_per_game']),
                (7, 'points_against_per_game', team['points_against_per_game']),
                (8, 'fg2_percentage', team['fg2_percentage']),
                (9, 'fg3_percentage', team['fg3_percentage']),
                (10, 'ft_percentage', team['ft_percentage']),
                (11, 'total_rebounds', team["total_rebounds"]),
                (12, 'rebounds_def', team["rebounds_def"]),
                (13, 'rebounds_off', team["rebounds_off"]),
                (14, 'assists', team["assists"]),
                (15, 'steals', team["steals"]),
                (16, 'turnovers', team["turnovers"]),
                (17, 'blocks', team["blocks"])
            ]

            for idx, key, raw_value in stats_config:
                num_value, display_value = process_numeric_value(raw_value, key)
                # Add percentage symbol for percentage stats
                if key in ['fg2_percentage', 'fg3_percentage', 'ft_percentage']:
                    display_value = f"{display_value}%"
                numeric_cols.append((idx, key, num_value, display_value))

            for col_idx, key, value, value_str in numeric_cols:
                item = NumericTableWidgetItem(value, value_str)
                color = self.get_quartile_color(
                    float(value),
                    quartiles[key],
                    numeric_data[key][1]  # Get reverse flag
                )
                item.setBackground(color)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col_idx, item)

        # Configure scrollbars
        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Allow table to update and calculate its dimensions
        self.table.updateGeometry()

        # Calculate total size needed
        scrollbar_width = 30 if self.table.verticalScrollBar().isVisible() else 0
        scrollbar_height = 30 if self.table.horizontalScrollBar().isVisible() else 0

        # Add additional margins to ensure all content is visible
        margin = 50  # Extra margin to avoid scrolling

        table_width = self.table.horizontalHeader().length() + scrollbar_width + margin
        table_height = (self.table.verticalHeader().length() +
                       self.table.horizontalHeader().height() +
                       scrollbar_height + margin)

        # Adjust window size considering the frame
        frame_width = self.frameGeometry().width() - self.geometry().width()
        frame_height = self.frameGeometry().height() - self.geometry().height()

        # Set window size with increased maximum limits
        window_width = min(table_width + frame_width, 1800)  # Increased to 1800
        window_height = min(table_height + frame_height, 1200)  # Increased to 1200

        # Ensure size is not smaller than minimum
        window_width = max(window_width, self.minimumWidth())
        window_height = max(window_height, self.minimumHeight())

        self.resize(window_width, window_height)

        # Center window on screen
        self.setGeometry(
            (self.screen().availableGeometry().width() - window_width) // 2,
            (self.screen().availableGeometry().height() - window_height) // 2,
            window_width,
            window_height
        )

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
        self.stats_button = QPushButton("Actualizar y Ver Estadísticas")
        self.stats_button.clicked.connect(self.on_view_stats)
        layout.addWidget(self.stats_button)

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
                    # Solo descargamos si no existe o si es el último partido (para posibles actualizaciones)
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

