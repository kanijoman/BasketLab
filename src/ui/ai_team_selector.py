"""
AI Team Selector - Dialog for selecting a team for AI analysis and generating PDF reports.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QPushButton, QLabel, QMessageBox, QListWidgetItem,
                              QRadioButton, QButtonGroup, QGroupBox, QLineEdit,
                              QFileDialog, QProgressDialog, QApplication)
from PyQt6.QtCore import Qt
from typing import List, Dict
import numpy as np
import matplotlib.pyplot as plt
from shotcharts.zone_analysis import ZoneAnalyzer
from shotcharts.coordinate_utils import convert_shots_for_zone_analysis
from .numeric_utils import safe_float
from .ui_utils import set_app_icon
from .team_utils import get_team_index_in_document


def normalize_player_name(full_name: str) -> str:
    """Normalize player name to initial + surnames (e.g., 'MARIA GONZALEZ GARCIA' -> 'M GONZALEZ GARCIA')."""
    if not full_name:
        return ""
    words = full_name.strip().split()
    if len(words) < 2:
        return full_name
    # First letter of first word + last two words (surnames)
    initial = words[0][0] if words[0] else ""
    surnames = words[-2:] if len(words) >= 2 else words[-1:]
    return f"{initial} {' '.join(surnames)}"


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

        self.radio_individual = QRadioButton("👥 Scouting Individual - Informe DOCX con notas de IA")
        self.radio_individual.setStyleSheet("padding: 5px;")

        self.type_button_group = QButtonGroup()
        self.type_button_group.addButton(self.radio_own)
        self.type_button_group.addButton(self.radio_opponent)
        self.type_button_group.addButton(self.radio_individual)

        type_layout.addWidget(self.radio_own)
        type_layout.addWidget(self.radio_opponent)
        type_layout.addWidget(self.radio_individual)
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

        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Buscar:")
        search_label.setStyleSheet("font-weight: bold;")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Escriba para filtrar equipos...")
        self.search_box.textChanged.connect(self._filter_teams)
        self.search_box.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #9C27B0;
                border-radius: 5px;
                font-size: 12px;
            }
            QLineEdit:focus {
                border: 2px solid #7B1FA2;
            }
        """)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)

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

    def _filter_teams(self, text: str):
        """Filter team list based on search text."""
        search_text = text.lower()
        for i in range(self.team_list.count()):
            item = self.team_list.item(i)
            team_name = item.text().replace("🏀 ", "").lower()
            item.setHidden(search_text not in team_name)

    def on_team_selected(self):
        """Handle team selection and open AI analysis or generate individual scouting report."""
        current_item = self.team_list.currentItem()

        if not current_item:
            QMessageBox.warning(self, "Aviso", "Por favor, seleccione un equipo de la lista.")
            return

        team = current_item.data(Qt.ItemDataRole.UserRole)
        team_name = team.get('name', 'Unknown Team')
        team_code = team.get('teamCode', '')

        # Check if individual scouting was selected
        if self.radio_individual.isChecked():
            self._generate_individual_scouting_report(team_name, team_code)
            return

        # Otherwise, proceed with team analysis (own or opponent)
        try:
            # Get shot data for this team
            all_shots = []
            collection = self.db_handler.connection.get_collection(self.collection_name)

            # Detect if FBCYL or FEB
            is_fbcyl = self.collection_name.startswith('FBCYL_')

            if collection is not None:
                if is_fbcyl:
                    # FBCYL: Extract shots from player metadata (same as individual scouting)
                    # Filter by team name directly in MongoDB (OPTIMIZED)
                    matches = collection.find({"stats.teams.name": team_name})

                    for doc in matches:
                        if 'stats' not in doc or 'teams' not in doc['stats']:
                            continue

                        teams = doc['stats']['teams']
                        if not isinstance(teams, list):
                            continue

                        # Find the team by name
                        team_data = None
                        for t in teams:
                            if t.get('name') == team_name:
                                team_data = t
                                break

                        if not team_data:
                            continue

                        players = team_data.get('players', [])

                        for player in players:
                            if not isinstance(player, dict):
                                continue

                            player_name = player.get('name', '')
                            player_id = str(player.get('actorId', ''))
                            player_uuid = player.get('uuid', '')
                            player_dorsal = str(player.get('shirtNumber', ''))
                            normalized_name = normalize_player_name(player_name)

                            # Get player data section
                            player_data = player.get('data', {})
                            if not isinstance(player_data, dict):
                                continue

                            # Extract all shots for this player
                            for shot in player_data.get('shootingOfTwoSuccessfulPoint', []):
                                all_shots.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 1,
                                    'points': 2,
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'team': 0
                                })

                            for shot in player_data.get('shootingOfTwoFailedPoint', []):
                                all_shots.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 0,
                                    'points': 2,
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'team': 0
                                })

                            for shot in player_data.get('shootingOfThreeSuccessfulPoint', []):
                                all_shots.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 1,
                                    'points': 3,
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'team': 0
                                })

                            for shot in player_data.get('shootingOfThreeFailedPoint', []):
                                all_shots.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 0,
                                    'points': 3,
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'team': 0
                                })

                else:
                    # FEB: Extract shots from SHOTCHART
                    # Filter by team ID directly in MongoDB (OPTIMIZED)
                    matches = list(collection.find({
                        "HEADER.TEAM.id": team_code,
                        "SHOTCHART.SHOTS": {"$exists": True, "$ne": []}
                    }))

                    for match in matches:
                        shotchart = match.get('SHOTCHART', {})
                        shots_list = shotchart.get('SHOTS', [])

                        if not shots_list:
                            continue

                        # Find team index using utility function
                        team_index = get_team_index_in_document(match, team_code)

                        if team_index is not None:
                            # Filter shots for this team
                            team_shots = [s for s in shots_list if int(s.get('team', -1)) == team_index]
                            all_shots.extend(team_shots)

            if not all_shots:
                QMessageBox.information(
                    self,
                    "Sin Datos",
                    f"No se encontraron datos de lanzamientos para {team_name}."
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

            # Ask where to save the PDF report
            analysis_type_text = "Rival" if analysis_type == 'opponent' else "Propio"
            default_filename = f"Informe_Scouting_{analysis_type_text}_{team_name.replace(' ', '_')}.pdf"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                f"Guardar Informe de Scouting {analysis_type_text}",
                default_filename,
                "PDF Files (*.pdf)"
            )

            if not file_path:
                return  # User cancelled

            # Generate report directly
            self._generate_team_pdf_report(team_name, combined_stats, zone_stats, analysis_type, file_path)

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

            # Find this team's stats
            for team_stat in team_stats_list:
                if team_stat.get('team_name') == team_name:
                    # Extract ALL available stats from the database
                    result = {
                        # Basic info
                        'games_played': safe_float(team_stat.get('total_games', 0)),

                        # Per-game stats (from basic_stats.py)
                        'points_per_game': safe_float(team_stat.get('points_per_game', 0)),
                        'points_allowed_per_game': safe_float(team_stat.get('points_allowed_per_game', 0)),
                        'rebounds_per_game': safe_float(team_stat.get('rebounds_per_game', 0)),
                        'assists_per_game': safe_float(team_stat.get('assists_per_game', 0)),
                        'steals_per_game': safe_float(team_stat.get('steals_per_game', 0)),
                        'turnovers_per_game': safe_float(team_stat.get('turnovers_per_game', 0)),
                        'blocks_per_game': safe_float(team_stat.get('blocks_per_game', 0)),
                        'possessions_per_game': safe_float(team_stat.get('possessions_per_game', 0)),

                        # Shooting percentages (from basic_stats.py)
                        'fg2_percentage': safe_float(team_stat.get('fg2_percentage', 0)),
                        'fg3_percentage': safe_float(team_stat.get('fg3_percentage', 0)),
                        'ft_percentage': safe_float(team_stat.get('ft_percentage', 0)),

                        # Four Factors (from advanced_stats.py)
                        'effective_fg_percentage': safe_float(team_stat.get('efg_percentage', 0)),
                        'true_shooting_percentage': safe_float(team_stat.get('true_shooting', 0)),
                        'turnover_rate': safe_float(team_stat.get('turnover_rate', 0)),
                        'offensive_rebound_rate': safe_float(team_stat.get('offensive_rebound_rate', 0)),
                        'free_throw_rate': safe_float(team_stat.get('free_throw_rate', 0)),

                        # Advanced shooting metrics (from advanced_stats.py)
                        'three_point_rate': safe_float(team_stat.get('three_point_rate', 0)),

                        # Playmaking metrics (from advanced_stats.py)
                        'assist_rate': safe_float(team_stat.get('assist_rate', 0)),
                        'assist_fg_rate': safe_float(team_stat.get('assist_fg_rate', 0)),
                        'steal_rate': safe_float(team_stat.get('steal_rate', 0)),
                        'block_rate': safe_float(team_stat.get('block_rate', 0)),

                        # Rebounding metrics (from advanced_stats.py)
                        'defensive_rebound_rate': safe_float(team_stat.get('defensive_rebound_rate', 0)),

                        # Efficiency ratings (from advanced_stats.py)
                        'offensive_rating': safe_float(team_stat.get('offensive_rating', 0)),
                        'defensive_rating': safe_float(team_stat.get('defensive_rating', 0)),
                        'net_rating': safe_float(team_stat.get('net_rating', 0)),

                        # Additional calculated stats
                        'pace': safe_float(team_stat.get('possessions_per_game', 0)),  # Pace is possessions per game

                        # Raw totals (for reference)
                        'total_points': safe_float(team_stat.get('points_scored', 0)),
                        'total_rebounds': safe_float(team_stat.get('total_rebounds', 0)),
                        'offensive_rebounds': safe_float(team_stat.get('rebounds_off', 0)),
                        'defensive_rebounds': safe_float(team_stat.get('rebounds_def', 0)),
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

                    # Calculate quartiles using numpy.percentile
                    q1_value = np.percentile(values, 25)
                    q2_value = np.percentile(values, 50)
                    q3_value = np.percentile(values, 75)

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

    def _generate_team_pdf_report(self, team_name: str, stats: dict, zone_stats: dict,
                                   analysis_type: str, file_path: str):
        """Generate PDF report for team analysis with AI insights."""
        from ai import TeamAnalyzer, AnalysisConfig
        from io import BytesIO

        try:
            # Check API key
            if not AnalysisConfig.has_api_key('groq'):
                QMessageBox.warning(
                    self,
                    "API Key Requerida",
                    "No se ha configurado una API key de Groq.\n\n"
                    "Vaya a la ventana de Análisis IA y configure su API key de Groq (gratis)."
                )
                return

            # Create progress dialog
            progress = QProgressDialog("Generando informe...", "Cancelar", 0, 100, self)
            progress.setWindowTitle("Generando Informe PDF")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setValue(0)
            QApplication.processEvents()

            # Create shot chart image
            progress.setLabelText("Generando gráfico de lanzamientos...")
            progress.setValue(20)
            QApplication.processEvents()

            fig = self.zone_analyzer.plot_zone_analysis(
                zone_stats,
                title=f"{team_name} - Análisis por Zonas",
                figsize=(10, 10)
            )

            # Convert figure to bytes
            buf = BytesIO()
            fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            shot_chart_bytes = buf.getvalue()
            buf.close()
            plt.close(fig)

            if progress.wasCanceled():
                return

            # Generate AI analysis
            progress.setLabelText("Generando análisis con IA...")
            progress.setValue(40)
            QApplication.processEvents()

            analyzer = TeamAnalyzer(provider='groq', model='fast')
            analysis_text = analyzer.analyze_team_performance(
                team_name=team_name,
                stats=stats,
                shot_chart_image=shot_chart_bytes,
                include_recommendations=True,
                analysis_type=analysis_type
            )

            if progress.wasCanceled():
                return

            # Clean up HTML if AI wrapped it in markdown code blocks
            if '```html' in analysis_text:
                analysis_text = analysis_text.replace('```html', '').replace('```', '').strip()
            elif analysis_text.startswith('```'):
                lines = analysis_text.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                analysis_text = '\n'.join(lines).strip()

            # Generate PDF
            progress.setLabelText("Creando documento PDF...")
            progress.setValue(70)
            QApplication.processEvents()

            from .pdf_generator import PDFGenerator

            PDFGenerator.generate_from_html(
                file_path=file_path,
                html_content=analysis_text,
                team_name=team_name,
                shot_chart_figure=fig
            )

            progress.setValue(100)
            progress.close()

            QMessageBox.information(
                self,
                "Informe Generado",
                f"Informe PDF guardado exitosamente en:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Error al generar informe PDF:\n{str(e)}"
            )

    def _generate_individual_scouting_report(self, team_name: str, team_code: str):
        """Generate individual scouting report with AI-powered notes for each player."""
        from .scouting_report_generator import ScoutingReportGenerator
        from .advanced_stats_calculator import AdvancedStatsCalculator
        from ai import TeamAnalyzer, AnalysisConfig

        try:
            # Primero, verificar que hay API key configurada
            if not AnalysisConfig.has_api_key('groq'):
                QMessageBox.warning(
                    self,
                    "API Key Requerida",
                    "Para generar notas de IA, necesita configurar una API key de Groq.\n\n"
                    "Vaya a la ventana de Análisis IA y configure su API key (gratis)."
                )
                return

            # Solicitar ubicación para guardar el archivo
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Informe de Scouting Individual",
                f"Informe_Scouting_Individual_{team_name.replace(' ', '_')}.docx",
                "Documentos Word (*.docx)"
            )

            if not file_path:
                return

            # Asegurar extensión .docx
            if not file_path.lower().endswith('.docx'):
                file_path += '.docx'

            # Crear diálogo de progreso
            progress = QProgressDialog("Inicializando...", "Cancelar", 0, 100, self)
            progress.setWindowTitle("Generando Informe de Scouting Individual")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

            # Obtener estadísticas de jugadores del equipo
            progress.setLabelText("Obteniendo estadísticas de jugadores...")
            QApplication.processEvents()

            player_stats = self.db_handler.get_player_stats(self.collection_name)

            if not player_stats:
                progress.close()
                QMessageBox.warning(self, "Sin Datos", "No se pudieron obtener estadísticas de jugadores.")
                return

            # Filtrar jugadores del equipo seleccionado
            team_players = [p for p in player_stats if p.get('team_name') == team_name]

            if not team_players:
                progress.close()
                QMessageBox.warning(self, "Sin Datos", f"No se encontraron jugadores para {team_name}.")
                return

            # Calcular estadísticas avanzadas
            progress.setLabelText("Calculando estadísticas avanzadas...")
            progress.setValue(10)
            QApplication.processEvents()

            # Group players by team to get team and opponent stats
            teams = {}
            for player in player_stats:
                team = player['team_name']
                if team not in teams:
                    teams[team] = {
                        'team_stats': self.db_handler.get_aggregated_team_stats(
                            self.collection_name, team
                        ),
                        'opp_stats': self.db_handler.get_aggregated_opponent_stats(
                            self.collection_name, team
                        )
                    }

            # Calculate advanced stats for each player
            calculator = AdvancedStatsCalculator()
            for player in player_stats:
                team = player['team_name']
                team_data = teams.get(team, {})
                team_stats = team_data.get('team_stats', {})
                opp_stats = team_data.get('opp_stats', {})

                # Calculate shooting percentages first
                fg2_made = player.get('total_p2m', 0)
                fg2_attempted = player.get('total_p2a', 0)
                fg3_made = player.get('total_p3m', 0)
                fg3_attempted = player.get('total_p3a', 0)
                ft_made = player.get('total_p1m', 0)
                ft_attempted = player.get('total_p1a', 0)
                games = player.get('games_played', 0)

                player['fg2_pct'] = (fg2_made / fg2_attempted * 100) if fg2_attempted > 0 else 0
                player['fg3_pct'] = (fg3_made / fg3_attempted * 100) if fg3_attempted > 0 else 0
                player['ft_pct'] = (ft_made / ft_attempted * 100) if ft_attempted > 0 else 0

                # Calculate per-game stats
                player['mpg'] = (player.get('total_minutes', 0) / 60 / games) if games > 0 else 0
                player['ppg'] = player.get('total_pts', 0) / games if games > 0 else 0
                player['val_pg'] = player.get('total_val', 0) / games if games > 0 else 0

                # Calculate advanced stats that don't need team data
                fga = fg2_attempted + fg3_attempted
                player['efg'] = calculator.calculate_effective_fg_percentage(player)
                player['ts'] = calculator.calculate_true_shooting_percentage(player)
                player['ftr'] = calculator.calculate_ftr(player)
                player['three_pr'] = calculator.calculate_3pr(player)

                # Calculate rebound percentages (simple version without team data)
                total_reb = player.get('total_ro', 0) + player.get('total_rd', 0)
                player['orb_pct'] = (player.get('total_ro', 0) / total_reb * 100) if total_reb > 0 else 0.0
                player['drb_pct'] = (player.get('total_rd', 0) / total_reb * 100) if total_reb > 0 else 0.0
                player['trb_pct'] = player['orb_pct'] + player['drb_pct']

                # Calculate other percentages based on possessions estimate
                possessions_est = fga + 0.44 * ft_attempted + player.get('total_to', 0)
                player['ast_pct'] = (player.get('total_as', player.get('total_assist', 0)) / possessions_est * 100) if possessions_est > 0 else 0.0
                player['tov_pct'] = (player.get('total_to', 0) / possessions_est * 100) if possessions_est > 0 else 0.0
                player['stl_pct'] = (player.get('total_st', 0) / possessions_est * 100) if possessions_est > 0 else 0.0
                player['blk_pct'] = (player.get('total_bl', player.get('total_bs', 0)) / possessions_est * 100) if possessions_est > 0 else 0.0

                # Calculate team-dependent stats if data is available
                if team_stats and opp_stats:
                    # Override with more accurate calculations using team data
                    full_advanced_stats = calculator.calculate_all_advanced_stats(player, team_stats, opp_stats)
                    player.update(full_advanced_stats)
                else:
                    # Approximations for team-dependent stats
                    player['usage'] = (possessions_est / games) if games > 0 else 0.0
                    player['orating'] = (player.get('total_pts', 0) / possessions_est * 100) if possessions_est > 0 else 0.0
                    # Defensive rating approximation (lower is better, league average ~110)
                    defensive_contrib = player.get('total_st', 0) + player.get('total_bl', player.get('total_bs', 0)) + player.get('total_rd', 0)
                    player['drating'] = max(80, 120 - (defensive_contrib / games * 2)) if games > 0 else 110.0

                # Calculate additional ratios
                total_ast = player.get('total_assist', player.get('total_as', 0))
                total_to = player.get('total_to', 0)
                player['ast_to_ratio'] = total_ast / total_to if total_to > 0 else 0

                ast_pct = player.get('ast_pct', 0)
                usage = player.get('usage', 0)
                player['ast_usg'] = (ast_pct / usage * 100) if usage > 0 else 0
                player['ast_ratio'] = ast_pct  # Already calculated above

            # Calcular cuartiles de liga para comparación
            progress.setLabelText("Calculando cuartiles de liga...")
            progress.setValue(20)
            QApplication.processEvents()

            league_quartiles = self._calculate_league_quartiles()

            # Generar notas de IA para cada jugador
            progress.setLabelText("Generando notas de IA...")
            progress.setValue(30)
            QApplication.processEvents()

            # Inicializar analizador de IA con Groq
            try:
                analyzer = TeamAnalyzer(provider='groq', model='fast')
            except Exception as e:
                progress.close()
                QMessageBox.critical(
                    self,
                    "Error",
                    f"No se pudo inicializar el analizador de IA:\n{str(e)}\n\n"
                    "Verifique su API key en la ventana de Análisis IA."
                )
                return

            # Generar notas para cada jugador del equipo
            ai_notes = {}
            total_players = len(team_players)

            import time

            for i, player in enumerate(team_players, 1):
                player_name = player.get('player_name', '')

                if progress.wasCanceled():
                    return

                progress.setLabelText(f"Generando notas de IA para {player_name}... ({i}/{total_players})")
                progress.setValue(30 + int((i / total_players) * 40))
                QApplication.processEvents()

                try:
                    # Generar notas de IA para este jugador
                    notes = analyzer.analyze_player_for_scouting(
                        player_name=player_name,
                        player_stats=player,
                        league_stats=league_quartiles
                    )
                    ai_notes[player_name] = notes

                    # Pequeño delay para evitar rate limits (solo entre jugadores, no después del último)
                    if i < total_players:
                        time.sleep(0.5)

                except Exception as e:
                    # Si falla para un jugador, continuar con los demás
                    ai_notes[player_name] = f"Error generando notas: {str(e)}"

            # Obtener datos de tiros
            progress.setLabelText("Obteniendo datos de tiros...")
            progress.setValue(75)
            QApplication.processEvents()

            shots_data = []
            collection = self.db_handler.connection.get_collection(self.collection_name)

            # Detect if FBCYL or FEB
            is_fbcyl = self.collection_name.startswith('FBCYL_')

            if collection is not None:
                if is_fbcyl:
                    # FBCYL: Extract shots from player metadata (not from moves!)
                    # Filter by team name directly in MongoDB (OPTIMIZED)
                    matches = collection.find({"stats.teams.name": team_name})

                    doc_idx = 0
                    matches_found = 0
                    for doc in matches:
                        doc_idx += 1
                        if 'stats' not in doc:
                            continue
                        if 'teams' not in doc['stats']:
                            continue

                        teams = doc['stats']['teams']
                        if not isinstance(teams, list):
                            continue

                        # Find the team by name (same as shotchart_window)
                        team_data = None
                        for t in teams:
                            if t.get('name') == team_name:
                                team_data = t
                                matches_found += 1
                                break

                        if not team_data:
                            continue

                        players = team_data.get('players', [])

                        doc_shot_count = 0
                        for player_idx, player in enumerate(players):
                            if not isinstance(player, dict):
                                continue

                            player_name = player.get('name', '')
                            player_id = str(player.get('actorId', ''))
                            player_uuid = player.get('uuid', '')
                            player_dorsal = str(player.get('shirtNumber', ''))
                            normalized_name = normalize_player_name(player_name)

                            # Get player data section
                            player_data = player.get('data', {})
                            if not isinstance(player_data, dict):
                                continue

                            # Check available shot arrays
                            two_made = player_data.get('shootingOfTwoSuccessfulPoint', [])
                            two_missed = player_data.get('shootingOfTwoFailedPoint', [])
                            three_made = player_data.get('shootingOfThreeSuccessfulPoint', [])
                            three_missed = player_data.get('shootingOfThreeFailedPoint', [])

                            player_shots_count = len(two_made) + len(two_missed) + len(three_made) + len(three_missed)
                            doc_shot_count += player_shots_count

                            # Extract 2-point successful shots
                            for shot in two_made:
                                shots_data.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 1,  # made
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'quarter': shot.get('period', 1),
                                    'team': 0
                                })

                            # Extract 2-point failed shots
                            for shot in two_missed:
                                shots_data.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 0,  # missed
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'quarter': shot.get('period', 1),
                                    'team': 0
                                })

                            # Extract 3-point successful shots
                            for shot in three_made:
                                shots_data.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 1,  # made
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'quarter': shot.get('period', 1),
                                    'team': 0
                                })

                            # Extract 3-point failed shots
                            for shot in three_missed:
                                shots_data.append({
                                    'x': shot.get('xnormalize', 0),
                                    'y': shot.get('ynormalize', 0),
                                    'm': 0,  # missed
                                    'player': player_dorsal,
                                    'player_id': player_id,
                                    'player_uuid': player_uuid,
                                    'player_name': player_name,
                                    'normalized_name': normalized_name,
                                    'quarter': shot.get('period', 1),
                                    'team': 0
                                })

                else:
                    # FEB: Extract shots from SHOTCHART
                    matches = collection.find({
                        "HEADER.TEAM.name": team_name,
                        "SHOTCHART.SHOTS": {"$exists": True}
                    })

                    for match in matches:
                        if 'SHOTCHART' not in match or not match['SHOTCHART']:
                            continue

                        shotchart = match['SHOTCHART']

                        if 'SHOTS' not in shotchart:
                            continue

                        # Crear mapeo de (team_idx, dorsal) -> player_id
                        player_id_map = {}
                        if 'TEAM' in shotchart and isinstance(shotchart['TEAM'], list):
                            for team_idx, team_data in enumerate(shotchart['TEAM']):
                                if 'PLAYER' in team_data and isinstance(team_data['PLAYER'], list):
                                    for player in team_data['PLAYER']:
                                        dorsal = str(player.get('no', '')).lstrip('0') or player.get('no', '')
                                        player_id = player.get('id', '')
                                        player_name = player.get('name', '')

                                        if dorsal and player_id:
                                            key = (team_idx, str(dorsal))
                                            player_id_map[key] = {
                                                'id': player_id,
                                                'name': player_name
                                            }

                        # Agregar player_id a cada tiro (FEB: suficiente con player_id)
                        match_shots = shotchart['SHOTS']
                        if isinstance(match_shots, list):
                            for shot in match_shots:
                                shot_copy = shot.copy()
                                team_idx = int(shot.get('team', -1))
                                dorsal = str(shot.get('player', ''))
                                key = (team_idx, dorsal)

                                if key in player_id_map:
                                    shot_copy['player_id'] = player_id_map[key]['id']
                                    shot_copy['player_name'] = player_id_map[key]['name']

                                shots_data.append(shot_copy)

            # Generar informe DOCX
            progress.setLabelText("Generando documento DOCX...")
            progress.setValue(85)
            QApplication.processEvents()

            def update_docx_progress(current: int, total: int, player_name: str):
                if progress.wasCanceled():
                    return
                percentage = 85 + int((current / total) * 15)
                progress.setValue(percentage)
                progress.setLabelText(f"Generando página para {player_name}... ({current}/{total})")
                QApplication.processEvents()

            generator = ScoutingReportGenerator(self.db_handler, self.collection_name)

            success = generator.generate_team_scouting_report(
                team_name=team_name,
                collection_name=self.collection_name,
                output_path=file_path,
                player_stats=player_stats,
                all_player_stats=player_stats,
                shots_data=shots_data if shots_data else None,
                progress_callback=update_docx_progress,
                ai_notes=ai_notes
            )

            progress.setValue(100)
            progress.close()

            if success:
                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Informe de scouting individual generado correctamente:\n\n{file_path}\n\n"
                    f"Se generaron notas de IA para {len(ai_notes)} jugadoras."
                )
                # Cerrar el diálogo
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "Error",
                    "No se pudo generar el informe completo. Revise los logs para más detalles."
                )

        except Exception as e:
            if 'progress' in locals():
                progress.close()
            QMessageBox.critical(
                self,
                "Error",
                f"Error al generar informe de scouting individual:\n{str(e)}"
            )
            import traceback
            traceback.print_exc()
