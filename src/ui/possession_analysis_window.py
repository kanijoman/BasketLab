"""Possession analysis display window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QTableWidget, QHeaderView, QPushButton,
                              QMessageBox, QTableWidgetItem, QLabel,
                              QProgressDialog, QApplication, QComboBox, QMenu)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QAction
from typing import List, Dict, Optional, Any
from datetime import datetime

from .table_items import NumericTableWidgetItem
from .ui_utils import set_app_icon
from .stats_config import calculate_quartiles
from .stats_exporter import StatsExporter

from src.utils.collection_utils import is_fbcyl as _is_fbcyl


class PossessionAnalysisWindow(QMainWindow):
    """Window to display possession analysis statistics."""

    def __init__(self, collection_name: str, db_handler: Any, parent: Optional[QWidget] = None):
        """
        Initialize the possession analysis window.

        Args:
            collection_name: Name of the collection for loading data
            db_handler: Database handler for accessing MongoDB
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("MfA - Análisis de Posesiones")
        self.setMinimumSize(1400, 700)

        set_app_icon(self)

        self.collection_name = collection_name
        self.db_handler = db_handler
        self.possession_data = []
        self.is_fbcyl = _is_fbcyl(collection_name)
        self.stats_exporter = StatsExporter(self)

        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("Análisis de Posesiones por Equipo")
        title_label.setStyleSheet("font-size: 16pt; font-weight: bold; margin: 10px;")
        layout.addWidget(title_label)

        # Info label
        info_label = QLabel(
            "Esta tabla muestra estadísticas sobre la duración y eficiencia de las posesiones de cada equipo.\n"
            "Las celdas están coloreadas por cuartiles: verde (mejor), amarillo, naranja, rojo (peor)."
        )
        info_label.setStyleSheet("font-size: 10pt; margin: 5px; color: #555;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Controls
        controls_layout = QHBoxLayout()

        # Export button with menu
        self.export_button = QPushButton("📤 Exportar")
        self.export_button.setToolTip("Exportar tabla en diferentes formatos")
        self.export_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        
        # Create menu for export options
        export_menu = QMenu(self)
        
        csv_action = QAction("📊 Exportar como CSV", self)
        csv_action.triggered.connect(self.export_to_csv)
        csv_action.setToolTip("Exportar a formato CSV")
        export_menu.addAction(csv_action)
        
        png_action = QAction("🖼️ Exportar como PNG", self)
        png_action.triggered.connect(self.export_to_png)
        png_action.setToolTip("Exportar como imagen PNG")
        export_menu.addAction(png_action)
        
        pdf_action = QAction("📄 Exportar como PDF", self)
        pdf_action.triggered.connect(self.export_to_pdf)
        pdf_action.setToolTip("Exportar a documento PDF")
        export_menu.addAction(pdf_action)
        
        self.export_button.setMenu(export_menu)
        controls_layout.addWidget(self.export_button)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Create table
        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "Equipo",
            "Tiempo Promedio\nPosesión (s)",
            "% Posesiones\nRápidas (≤8s)",
            "% Posesiones\nMedias (8-16s)",
            "% Posesiones\nLargas (>16s)",
            "OER Posesiones\nRápidas",
            "OER Posesiones\nMedias",
            "OER Posesiones\nLargas",
            "Δ Ritmo vs\nRival Promedio (s)",
            "Est. Posesiones\nen 40 min"
        ])

        # Configure table
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d0d0d0;
                background-color: white;
            }
            QTableWidget::item {
                padding: 5px;
            }
            QHeaderView::section {
                background-color: #2196F3;
                color: white;
                padding: 8px;
                border: 1px solid #1976D2;
                font-weight: bold;
            }
        """)

        # Make columns sortable
        self.table.setSortingEnabled(True)

        # Set column resize mode
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Team name
        for i in range(1, 10):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)

        layout.addWidget(self.table)

        # Status bar
        self.status_label = QLabel("Cargando datos...")
        self.status_label.setStyleSheet("font-size: 9pt; color: #666; margin: 5px;")
        layout.addWidget(self.status_label)
        
        # Load data automatically after UI setup
        QTimer.singleShot(100, self.load_data)

    def load_data(self):
        """Load possession data from database."""
        try:
            self.status_label.setText("Cargando datos de posesiones...")
            QApplication.processEvents()

            # Get all teams from collection
            self.status_label.setText("Obteniendo lista de equipos...")
            QApplication.processEvents()
            
            teams = self.get_teams_from_collection()

            if not teams:
                self.status_label.setText("No se encontraron equipos en la colección.")
                QMessageBox.warning(self, "Sin Datos", "No se encontraron equipos en la colección.")
                return

            self.status_label.setText(f"Encontrados {len(teams)} equipos. Iniciando análisis...")
            QApplication.processEvents()

            # Show progress dialog
            progress = QProgressDialog("Analizando posesiones...", "Cancelar", 0, len(teams), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setWindowTitle("Análisis de Posesiones")
            progress.setMinimumDuration(0)

            self.possession_data = []

            for idx, team in enumerate(teams):
                if progress.wasCanceled():
                    break

                progress.setValue(idx)
                progress.setLabelText(f"Analizando {team['name']}... ({idx+1}/{len(teams)})")
                QApplication.processEvents()

                try:
                    # Get possession stats for this team
                    team_stats = self.get_team_possession_stats(team['id'])

                    if team_stats and team_stats.get('total_possessions', 0) > 0:
                        # Calculate opponent pace comparison:
                        # - opponent_avg_pace: how opponents play in their other games
                        # - opponent_pace_vs_team: how opponents play against this team
                        opponent_avg_pace, opponent_pace_vs_team = self.calculate_opponent_pace_comparison(team['id'])

                        team_data = {
                            'team_name': team['name'],
                            'team_id': team['id'],
                            'avg_duration': team_stats['avg_duration'],
                            'total_possessions': team_stats['total_possessions'],
                            'pct_fast': self.calculate_percentage(
                                team_stats['possessions_by_duration']['<=8s']['count'],
                                team_stats['total_possessions']
                            ),
                            'pct_medium': self.calculate_percentage(
                                team_stats['possessions_by_duration']['8-16s']['count'],
                                team_stats['total_possessions']
                            ),
                            'pct_slow': self.calculate_percentage(
                                team_stats['possessions_by_duration']['>16s']['count'],
                                team_stats['total_possessions']
                            ),
                            'oer_fast': team_stats['possessions_by_duration']['<=8s']['oer'],
                            'oer_medium': team_stats['possessions_by_duration']['8-16s']['oer'],
                            'oer_slow': team_stats['possessions_by_duration']['>16s']['oer'],
                            'pace_diff': opponent_avg_pace - opponent_pace_vs_team if (opponent_avg_pace and opponent_pace_vs_team) else None,
                            'estimated_possessions_40min': self.estimate_possessions_per_game(team_stats['avg_duration'])
                        }
                        self.possession_data.append(team_data)
                
                except Exception as e:
                    print(f"Error analyzing team {team['name']}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Continue with next team

            progress.setValue(len(teams))

            if self.possession_data:
                self.populate_table()
                self.status_label.setText(f"Análisis completado: {len(self.possession_data)} equipos")
            else:
                self.status_label.setText("No se encontraron datos de posesiones.")
                QMessageBox.information(
                    self, "Sin Datos",
                    "No se encontraron datos de play-by-play para calcular posesiones."
                )

        except Exception as e:
            self.status_label.setText(f"Error al cargar datos: {str(e)}")
            QMessageBox.critical(self, "Error", f"Error al cargar datos de posesiones:\n{str(e)}")

    def get_teams_from_collection(self) -> List[Dict]:
        """Get list of teams from the collection."""
        try:
            from .team_utils import get_available_teams_from_collection
            teams = get_available_teams_from_collection(self.db_handler, self.collection_name)
            return teams
        except Exception as e:
            print(f"Error getting teams: {e}")
            return []

    def get_team_possession_stats(self, team_id: str) -> Optional[Dict]:
        """Get possession statistics for a team."""
        try:
            repo = self.db_handler.repository
            stats = repo.get_team_possession_stats(self.collection_name, team_id)
            return stats
        except Exception as e:
            print(f"Error getting possession stats for team {team_id}: {e}")
            return None

    def calculate_opponent_pace_comparison(self, team_id: str) -> tuple[Optional[float], Optional[float]]:
        """
        Calculate opponent pace comparison:
        - Average pace of opponents in their other games (NOT against this team)
        - Average pace of opponents when playing against this team

        Args:
            team_id: ID of the team

        Returns:
            Tuple of (opponent_avg_pace, opponent_pace_vs_team)
        """
        try:
            # Get all games where this team played
            team_games = self.db_handler.repository.get_games_for_team(self.collection_name, team_id)

            if not team_games:
                return None, None

            # Get opponent IDs
            opponent_ids = set()
            for game in team_games:
                if self.is_fbcyl:
                    stats = game.get('stats', {})
                    teams = stats.get('teams', [])
                    for team in teams:
                        opp_id = team.get('teamIdIntern') or team.get('teamIdExtern')
                        if str(opp_id) != str(team_id):
                            opponent_ids.add(str(opp_id))
                else:
                    header = game.get('HEADER', {})
                    teams = header.get('TEAM', [])
                    for team in teams:
                        opp_id = team.get('id')
                        if str(opp_id) != str(team_id):
                            opponent_ids.add(str(opp_id))

            if not opponent_ids:
                return None, None

            # Calculate average pace for opponents in their other games
            opponent_paces_other = []
            # Calculate average pace for opponents when playing against this team
            opponent_paces_vs_team = []
            
            for opp_id in opponent_ids:
                # Get games for this opponent NOT against our team
                opp_games_other = self.get_opponent_games_excluding_team(opp_id, team_id)
                if opp_games_other:
                    opp_stats_other = self.calculate_possession_stats_for_games(opp_id, opp_games_other)
                    if opp_stats_other and opp_stats_other.get('avg_duration'):
                        opponent_paces_other.append(opp_stats_other['avg_duration'])
                
                # Get games for this opponent AGAINST our team
                opp_games_vs_team = self.get_opponent_games_against_team(opp_id, team_id)
                if opp_games_vs_team:
                    opp_stats_vs_team = self.calculate_possession_stats_for_games(opp_id, opp_games_vs_team)
                    if opp_stats_vs_team and opp_stats_vs_team.get('avg_duration'):
                        opponent_paces_vs_team.append(opp_stats_vs_team['avg_duration'])

            opponent_avg_pace = sum(opponent_paces_other) / len(opponent_paces_other) if opponent_paces_other else None
            opponent_pace_vs_team = sum(opponent_paces_vs_team) / len(opponent_paces_vs_team) if opponent_paces_vs_team else None

            return opponent_avg_pace, opponent_pace_vs_team

        except Exception as e:
            print(f"Error calculating opponent pace comparison: {e}")
            return None, None

    def get_opponent_games_against_team(self, opponent_id: str, team_id: str) -> List[Dict]:
        """Get games for an opponent specifically against a given team."""
        try:
            all_games = self.db_handler.repository.get_games_for_team(self.collection_name, opponent_id)

            # Filter games that include the specified team
            filtered_games = []
            for game in all_games:
                if self.is_fbcyl:
                    stats = game.get('stats', {})
                    teams = stats.get('teams', [])
                    team_ids = [str(t.get('teamIdIntern') or t.get('teamIdExtern')) for t in teams]
                else:
                    header = game.get('HEADER', {})
                    teams = header.get('TEAM', [])
                    team_ids = [str(t.get('id')) for t in teams]

                if str(team_id) in team_ids:
                    filtered_games.append(game)

            return filtered_games

        except Exception as e:
            print(f"Error getting opponent games against team: {e}")
            return []

    def get_opponent_games_excluding_team(self, opponent_id: str, exclude_team_id: str) -> List[Dict]:
        """Get games for an opponent excluding games against a specific team."""
        try:
            all_games = self.db_handler.repository.get_games_for_team(self.collection_name, opponent_id)

            # Filter out games against the excluded team
            filtered_games = []
            for game in all_games:
                if self.is_fbcyl:
                    stats = game.get('stats', {})
                    teams = stats.get('teams', [])
                    team_ids = [str(t.get('teamIdIntern') or t.get('teamIdExtern')) for t in teams]
                else:
                    header = game.get('HEADER', {})
                    teams = header.get('TEAM', [])
                    team_ids = [str(t.get('id')) for t in teams]

                if str(exclude_team_id) not in team_ids:
                    filtered_games.append(game)

            return filtered_games

        except Exception as e:
            print(f"Error getting opponent games: {e}")
            return []

    def calculate_possession_stats_for_games(self, team_id: str, games: List[Dict]) -> Optional[Dict]:
        """Calculate possession statistics for a specific set of games."""
        try:
            from database.playbyplay_analyzer import PossessionAnalyzer

            all_possessions = []
            total_possessions = 0

            for game in games:
                try:
                    analyzer = PossessionAnalyzer(game, is_fbcyl=self.is_fbcyl)
                    game_stats = analyzer.calculate_possessions(team_id)

                    if game_stats and game_stats.get('total_possessions', 0) > 0:
                        # Weight by number of possessions
                        total_possessions += game_stats['total_possessions']
                        all_possessions.extend([game_stats['avg_duration']] * game_stats['total_possessions'])

                except Exception as e:
                    continue

            if all_possessions:
                return {
                    'avg_duration': sum(all_possessions) / len(all_possessions),
                    'total_possessions': total_possessions
                }

            return None

        except Exception as e:
            print(f"Error calculating possession stats for games: {e}")
            return None

    def calculate_percentage(self, count: int, total: int) -> float:
        """Calculate percentage."""
        if total == 0:
            return 0.0
        return (count / total) * 100

    def estimate_possessions_per_game(self, avg_duration: float) -> float:
        """
        Estimate number of possessions in a 40-minute game.

        Args:
            avg_duration: Average possession duration in seconds

        Returns:
            Estimated number of possessions for this team in 40 minutes
        """
        if avg_duration <= 0:
            return 0.0

        # 40 minutes = 2400 seconds total game time
        # Each team gets approximately half of the possessions
        # Formula: Total seconds / Average duration / 2 teams
        # Example: 2400 / 14.72 / 2 = 81.5 possessions
        return 2400 / avg_duration / 2

    def populate_table(self):
        """Populate table with possession data."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.possession_data))

        # Extract data for quartile calculation
        numeric_columns = {
            1: [d['avg_duration'] for d in self.possession_data],
            2: [d['pct_fast'] for d in self.possession_data],
            3: [d['pct_medium'] for d in self.possession_data],
            4: [d['pct_slow'] for d in self.possession_data],
            5: [d['oer_fast'] for d in self.possession_data],
            6: [d['oer_medium'] for d in self.possession_data],
            7: [d['oer_slow'] for d in self.possession_data],
            8: [d['pace_diff'] for d in self.possession_data if d['pace_diff'] is not None],
            9: [d['estimated_possessions_40min'] for d in self.possession_data]
        }

        # Calculate quartiles for each column
        quartiles = {}
        for col, values in numeric_columns.items():
            if values:
                quartiles[col] = calculate_quartiles(values)

        # Populate table
        for row, data in enumerate(self.possession_data):
            # Team name
            self.table.setItem(row, 0, QTableWidgetItem(data['team_name']))

            # Avg duration (lower is better for faster pace, but contextual)
            self.add_numeric_cell(row, 1, data['avg_duration'], quartiles.get(1), decimals=2, reverse=False)

            # Percentages
            self.add_numeric_cell(row, 2, data['pct_fast'], quartiles.get(2), decimals=1, reverse=False)
            self.add_numeric_cell(row, 3, data['pct_medium'], quartiles.get(3), decimals=1, reverse=False)
            self.add_numeric_cell(row, 4, data['pct_slow'], quartiles.get(4), decimals=1, reverse=False)

            # OERs (higher is better)
            self.add_numeric_cell(row, 5, data['oer_fast'], quartiles.get(5), decimals=2, reverse=True)
            self.add_numeric_cell(row, 6, data['oer_medium'], quartiles.get(6), decimals=2, reverse=True)
            self.add_numeric_cell(row, 7, data['oer_slow'], quartiles.get(7), decimals=2, reverse=True)

            # Pace difference (negative means opponents play slower against us)
            if data['pace_diff'] is not None:
                self.add_numeric_cell(row, 8, data['pace_diff'], quartiles.get(8), decimals=2, reverse=False, signed=True)
            else:
                item = QTableWidgetItem("N/A")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 8, item)

            # Estimated possessions
            self.add_numeric_cell(row, 9, data['estimated_possessions_40min'], quartiles.get(9), decimals=1, reverse=False)

        self.table.setSortingEnabled(True)

    def add_numeric_cell(self, row: int, col: int, value: float, quartile_info: Optional[tuple],
                         decimals: int = 2, reverse: bool = False, signed: bool = False):
        """
        Add a numeric cell with quartile coloring.

        Args:
            row: Row index
            col: Column index
            value: Numeric value
            quartile_info: Tuple of (q1, q2, q3) or None
            decimals: Number of decimal places
            reverse: If True, higher values get better colors (green), otherwise lower is better
            signed: If True, show + sign for positive values
        """
        format_str = f"{{:+.{decimals}f}}" if signed else f"{{:.{decimals}f}}"
        text = format_str.format(value)
        item = NumericTableWidgetItem(value, text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        # Apply quartile coloring
        if quartile_info:
            q1, q2, q3 = quartile_info
            if reverse:
                # Higher is better (green for high values)
                if value >= q3:
                    color = QColor(200, 255, 200)  # Light green
                elif value >= q2:
                    color = QColor(255, 255, 200)  # Light yellow
                elif value >= q1:
                    color = QColor(255, 220, 180)  # Light orange
                else:
                    color = QColor(255, 200, 200)  # Light red
            else:
                # Lower is better (green for low values)
                if value <= q1:
                    color = QColor(200, 255, 200)  # Light green
                elif value <= q2:
                    color = QColor(255, 255, 200)  # Light yellow
                elif value <= q3:
                    color = QColor(255, 220, 180)  # Light orange
                else:
                    color = QColor(255, 200, 200)  # Light red

            item.setBackground(color)

        self.table.setItem(row, col, item)

    def export_to_csv(self):
        """Export table data to CSV file."""
        table_name = "analisis_posesiones"
        subtitle = f"Colección: {self.collection_name}"
        self.stats_exporter.export_to_csv(self.table, table_name, subtitle)
    
    def export_to_png(self):
        """Export table to PNG image."""
        table_name = "analisis_posesiones"
        subtitle = f"Colección: {self.collection_name}"
        self.stats_exporter.export_to_png(self.table, table_name, subtitle)
    
    def export_to_pdf(self):
        """Export table to PDF format."""
        table_name = "analisis_posesiones"
        window_title = "MfA - Análisis de Posesiones"
        subtitle = f"Colección: {self.collection_name}"
        self.stats_exporter.export_to_pdf(self.table, table_name, window_title, subtitle)
