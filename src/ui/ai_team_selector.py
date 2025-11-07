"""
AI Team Selector - Dialog for selecting a team for AI analysis.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QPushButton, QLabel, QMessageBox, QListWidgetItem,
                              QRadioButton, QButtonGroup, QGroupBox)
from PyQt6.QtCore import Qt
from typing import List, Dict
from shotcharts.zone_analysis import ZoneAnalyzer
from shotcharts.coordinate_utils import convert_shots_for_zone_analysis
from .ai_analysis_window import AIAnalysisWindow
from .ui_utils import set_app_icon
import matplotlib.pyplot as plt


class AITeamSelector(QDialog):
    """Dialog for selecting a team to analyze with AI."""

    def __init__(self, teams_data: List[Dict], collection_name: str, db_handler, parent=None):
        """
        Initialize team selector dialog.

        Args:
            teams_data: List of team documents from database
            collection_name: MongoDB collection name
            db_handler: Database handler instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.teams_data = teams_data
        self.collection_name = collection_name
        self.db_handler = db_handler
        self.zone_analyzer = ZoneAnalyzer(detail_level='detailed')
        self.analysis_type = 'own'  # 'own' or 'opponent'

        self.setup_ui()

    def setup_ui(self):
        """Setup the dialog UI."""
        self.setWindowTitle("MfA - Seleccionar Equipo para Análisis IA")
        self.setMinimumSize(400, 500)

        # Set application icon
        set_app_icon(self)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel("🤖 Análisis IA - Seleccione un Equipo")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        # Instructions
        instructions = QLabel(
            "Seleccione un equipo de la lista para generar un análisis completo\n"
            "basado en estadísticas de zonas y rendimiento."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("padding: 5px; color: #666;")
        layout.addWidget(instructions)

        # Analysis Type Selection
        type_group = QGroupBox("Tipo de Análisis")
        type_layout = QVBoxLayout()

        self.radio_own = QRadioButton("💡 Scouting Propio - Mejora de mi equipo")
        self.radio_own.setChecked(True)
        self.radio_own.setStyleSheet("padding: 5px;")

        self.radio_opponent = QRadioButton("⚔️ Scouting Rival - Estrategia contra oponente")
        self.radio_opponent.setStyleSheet("padding: 5px;")

        self.type_button_group = QButtonGroup()
        self.type_button_group.addButton(self.radio_own)
        self.type_button_group.addButton(self.radio_opponent)

        type_layout.addWidget(self.radio_own)
        type_layout.addWidget(self.radio_opponent)
        type_group.setLayout(type_layout)
        type_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #9C27B0;
                border-radius: 5px;
                margin-top: 10px;
                padding: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        layout.addWidget(type_group)

        # Team list
        self.team_list = QListWidget()
        self.team_list.itemDoubleClicked.connect(self.on_team_selected)

        # Populate team list
        for team in self.teams_data:
            team_name = team.get('name', 'Unknown Team')
            item = QListWidgetItem(f"🏀 {team_name}")
            item.setData(Qt.ItemDataRole.UserRole, team)
            self.team_list.addItem(item)

        layout.addWidget(self.team_list)

        # Buttons
        button_layout = QHBoxLayout()

        self.analyze_btn = QPushButton("🤖 Analizar Equipo")
        self.analyze_btn.clicked.connect(self.on_team_selected)
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        button_layout.addWidget(self.analyze_btn)

        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Apply dialog styling
        self.setStyleSheet("""
            QDialog {
                background-color: #f5f5f5;
            }
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 5px;
                background-color: white;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:hover {
                background-color: #e3f2fd;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
        """)

    def on_team_selected(self):
        """Handle team selection and open AI analysis."""
        current_item = self.team_list.currentItem()

        if not current_item:
            QMessageBox.warning(self, "Aviso", "Por favor, seleccione un equipo de la lista.")
            return

        team = current_item.data(Qt.ItemDataRole.UserRole)
        team_name = team.get('name', 'Unknown Team')
        team_code = team.get('teamCode', '')

        try:
            # Get shot data for this team
            all_shots = []
            collection = self.db_handler.connection.get_collection(self.collection_name)
            matches = list(collection.find({})) if collection is not None else []

            for match in matches:
                shotchart = match.get('SHOTCHART', {})
                shots_list = shotchart.get('SHOTS', [])

                if not shots_list:
                    continue

                # Find team index - check both BOXSCORE.TEAM and HEADER.TEAM
                team_index = None

                # First try BOXSCORE.TEAM
                if 'BOXSCORE' in match and 'TEAM' in match['BOXSCORE']:
                    teams = match['BOXSCORE']['TEAM']
                    if isinstance(teams, list):
                        for idx, team_data in enumerate(teams):
                            if isinstance(team_data, dict) and 'TOTAL' in team_data:
                                if team_data['TOTAL'].get('teamCode', '') == team_code:
                                    team_index = idx
                                    break

                # Fallback to HEADER.TEAM
                if team_index is None and 'HEADER' in match and 'TEAM' in match['HEADER']:
                    teams = match['HEADER']['TEAM']
                    if isinstance(teams, list):
                        for idx, team_data in enumerate(teams):
                            if isinstance(team_data, dict):
                                if team_data.get('teamCode', '') == team_code:
                                    team_index = idx
                                    break

                if team_index is not None:
                    # Filter shots for this team
                    team_shots = [s for s in shots_list if int(s.get('team', -1)) == team_index]
                    all_shots.extend(team_shots)

            if not all_shots:
                QMessageBox.information(
                    self,
                    "Sin Datos",
                    f"No se encontraron datos de lanzamientos para {team_name}.\n"
                    f"Se revisaron {len(matches)} partidos."
                )
                return

            # Process shots for zone analysis
            processed_shots = convert_shots_for_zone_analysis(all_shots)
            zone_stats = self.zone_analyzer.analyze_zone_performance(processed_shots)

            # Get team's overall statistics from the database
            team_season_stats = self._get_team_season_stats(team_name)

            # Calculate league-wide quartiles for comparison
            league_quartiles = self._calculate_league_quartiles()

            # Combine zone stats with overall team stats and league quartiles
            combined_stats = {
                'zone_stats': zone_stats.get('zone_stats', {}),
                'total_shots': zone_stats.get('total_shots', 0),
                'unclassified_shots': zone_stats.get('unclassified_shots', 0),
                'team_stats': team_season_stats,  # Team's individual stats
                'league_stats': league_quartiles  # League-wide quartiles for comparison
            }

            # Determine analysis type
            analysis_type = 'opponent' if self.radio_opponent.isChecked() else 'own'

            # Create shot chart visualization
            fig = self.zone_analyzer.plot_zone_analysis(
                zone_stats,
                title=f"{team_name} - Análisis por Zonas",
                figsize=(10, 10)
            )

            # Open AI analysis window
            ai_window = AIAnalysisWindow(
                team_name=team_name,
                stats=combined_stats,
                shot_chart_figure=fig,
                analysis_type=analysis_type,
                parent=self.parent()
            )
            ai_window.show()

            # Close this dialog
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al cargar datos del equipo: {str(e)}"
            )

    def _get_team_season_stats(self, team_name: str) -> dict:
        """Get team's overall season statistics from database."""
        try:
            # Get aggregated team stats
            team_stats_list = self.db_handler.get_team_stats(self.collection_name)

            # Helper function to safely get numeric value
            def safe_get(data, key, default=0):
                """Get value from dict, converting None to default."""
                value = data.get(key, default)
                return default if value is None else value

            # Find this team's stats
            for team_stat in team_stats_list:
                if team_stat.get('team_name') == team_name:
                    # Extract ALL available stats from the database
                    result = {
                        # Basic info
                        'games_played': safe_get(team_stat, 'total_games'),

                        # Per-game stats (from basic_stats.py)
                        'points_per_game': safe_get(team_stat, 'points_per_game'),
                        'points_allowed_per_game': safe_get(team_stat, 'points_allowed_per_game'),
                        'rebounds_per_game': safe_get(team_stat, 'rebounds_per_game'),
                        'assists_per_game': safe_get(team_stat, 'assists_per_game'),
                        'steals_per_game': safe_get(team_stat, 'steals_per_game'),
                        'turnovers_per_game': safe_get(team_stat, 'turnovers_per_game'),
                        'blocks_per_game': safe_get(team_stat, 'blocks_per_game'),
                        'possessions_per_game': safe_get(team_stat, 'possessions_per_game'),

                        # Shooting percentages (from basic_stats.py)
                        'fg2_percentage': safe_get(team_stat, 'fg2_percentage'),
                        'fg3_percentage': safe_get(team_stat, 'fg3_percentage'),
                        'ft_percentage': safe_get(team_stat, 'ft_percentage'),

                        # Four Factors (from advanced_stats.py)
                        'effective_fg_percentage': safe_get(team_stat, 'efg_percentage'),
                        'true_shooting_percentage': safe_get(team_stat, 'true_shooting'),
                        'turnover_rate': safe_get(team_stat, 'turnover_rate'),
                        'offensive_rebound_rate': safe_get(team_stat, 'offensive_rebound_rate'),
                        'free_throw_rate': safe_get(team_stat, 'free_throw_rate'),

                        # Advanced shooting metrics (from advanced_stats.py)
                        'three_point_rate': safe_get(team_stat, 'three_point_rate'),

                        # Playmaking metrics (from advanced_stats.py)
                        'assist_rate': safe_get(team_stat, 'assist_rate'),
                        'assist_fg_rate': safe_get(team_stat, 'assist_fg_rate'),
                        'steal_rate': safe_get(team_stat, 'steal_rate'),
                        'block_rate': safe_get(team_stat, 'block_rate'),

                        # Rebounding metrics (from advanced_stats.py)
                        'defensive_rebound_rate': safe_get(team_stat, 'defensive_rebound_rate'),

                        # Efficiency ratings (from advanced_stats.py)
                        'offensive_rating': safe_get(team_stat, 'offensive_rating'),
                        'defensive_rating': safe_get(team_stat, 'defensive_rating'),
                        'net_rating': safe_get(team_stat, 'net_rating'),

                        # Additional calculated stats
                        'pace': safe_get(team_stat, 'possessions_per_game'),  # Pace is possessions per game

                        # Raw totals (for reference)
                        'total_points': safe_get(team_stat, 'points_scored'),
                        'total_rebounds': safe_get(team_stat, 'total_rebounds'),
                        'offensive_rebounds': safe_get(team_stat, 'rebounds_off'),
                        'defensive_rebounds': safe_get(team_stat, 'rebounds_def'),
                    }

                    return result

            # Return empty dict if team not found
            return {}

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {}

    def _calculate_league_quartiles(self) -> dict:
        """Calculate quartiles for all statistics across the league.

        Returns:
            Dictionary with stat names as keys, each containing q1, q2 (median), q3, min, max
        """
        try:
            # Get all teams' stats
            team_stats_list = self.db_handler.get_team_stats(self.collection_name)

            if not team_stats_list:
                return {}

            # Stat fields to calculate quartiles for (comprehensive list from basic_stats + advanced_stats)
            stat_fields = [
                # Per-game stats
                'points_per_game', 'points_allowed_per_game', 'rebounds_per_game',
                'assists_per_game', 'steals_per_game', 'turnovers_per_game', 'blocks_per_game',
                'possessions_per_game',
                # Shooting percentages
                'fg2_percentage', 'fg3_percentage', 'ft_percentage',
                # Four Factors
                'efg_percentage', 'true_shooting', 'turnover_rate',
                'offensive_rebound_rate', 'free_throw_rate',
                # Advanced shooting
                'three_point_rate',
                # Playmaking
                'assist_rate', 'assist_fg_rate', 'steal_rate', 'block_rate',
                # Rebounding
                'defensive_rebound_rate',
                # Efficiency
                'offensive_rating', 'defensive_rating', 'net_rating'
            ]

            quartiles = {}

            for stat_field in stat_fields:
                # Extract values for this stat from all teams
                values = []
                for team_stat in team_stats_list:
                    value = team_stat.get(stat_field, None)
                    if value is not None:  # Include zero values, just exclude None/missing
                        try:
                            values.append(float(value))
                        except (ValueError, TypeError):
                            pass  # Skip invalid values

                if len(values) >= 4:  # Need at least 4 teams for meaningful quartiles
                    values.sort()
                    n = len(values)

                    # Calculate quartiles using linear interpolation (same as numpy.percentile)
                    # Q1 = 25th percentile, Q2 = 50th percentile (median), Q3 = 75th percentile
                    def percentile(sorted_values, p):
                        """Calculate percentile using linear interpolation"""
                        k = (len(sorted_values) - 1) * p
                        f = int(k)
                        c = f + 1
                        if c >= len(sorted_values):
                            return sorted_values[-1]
                        if f < 0:
                            return sorted_values[0]
                        d0 = sorted_values[f] * (c - k)
                        d1 = sorted_values[c] * (k - f)
                        return d0 + d1

                    q1_value = percentile(values, 0.25)
                    q2_value = percentile(values, 0.50)
                    q3_value = percentile(values, 0.75)

                    quartiles[stat_field] = {
                        'min': values[0],
                        'q1': q1_value,
                        'q2': q2_value,  # median
                        'q3': q3_value,
                        'max': values[-1],
                        'count': n
                    }

            return quartiles

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {}
            import traceback
            traceback.print_exc()
            return {}

