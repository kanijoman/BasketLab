"""
AI Team Selector - Dialog for selecting a team for AI analysis.
"""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QPushButton, QLabel, QMessageBox, QListWidgetItem,
                              QRadioButton, QButtonGroup, QGroupBox, QLineEdit)
from PyQt6.QtCore import Qt
from typing import List, Dict
import numpy as np
from shotcharts.zone_analysis import ZoneAnalyzer
from .numeric_utils import safe_float
from shotcharts.coordinate_utils import convert_shots_for_zone_analysis
from .ai_analysis_window import AIAnalysisWindow
from .ui_utils import set_app_icon
from .team_utils import get_team_index_in_document
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
            matches = list(collection.find({})) if collection is not None else []

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

    def _generate_individual_scouting_report(self, team_name: str, team_code: str):
        """Generate individual scouting report with AI-powered notes for each player."""
        from PyQt6.QtWidgets import QFileDialog, QProgressDialog, QApplication
        from PyQt6.QtCore import Qt
        from .scouting_report_generator import ScoutingReportGenerator
        from .advanced_stats_calculator import AdvancedStatsCalculator
        from ai import TeamAnalyzer, AnalysisConfig

        try:
            # Primero, verificar que hay API key configurada
            if not AnalysisConfig.has_api_key('gemini') and not AnalysisConfig.has_api_key('openai'):
                QMessageBox.warning(
                    self,
                    "API Key Requerida",
                    "Para generar notas de IA, necesita configurar una API key.\n\n"
                    "Vaya a la ventana de Análisis IA y configure su API key de Google Gemini (gratis) o OpenAI."
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
            for player in player_stats:
                team = player['team_name']
                team_data = teams.get(team, {})
                team_stats = team_data.get('team_stats', {})
                opp_stats = team_data.get('opp_stats', {})

                if team_stats and opp_stats:
                    advanced_stats = AdvancedStatsCalculator.calculate_all_advanced_stats(
                        player, team_stats, opp_stats
                    )
                    player.update(advanced_stats)

                    # Calculate additional metrics needed for radar chart
                    player['trb_pct'] = player.get('orb_pct', 0) + player.get('drb_pct', 0)

                    # Shooting percentages
                    fg2_made = player.get('total_p2m', 0)
                    fg2_attempted = player.get('total_p2a', 0)
                    player['fg2_pct'] = (fg2_made / fg2_attempted * 100) if fg2_attempted > 0 else 0

                    fg3_made = player.get('total_p3m', 0)
                    fg3_attempted = player.get('total_p3a', 0)
                    player['fg3_pct'] = (fg3_made / fg3_attempted * 100) if fg3_attempted > 0 else 0

                    ft_made = player.get('total_p1m', 0)
                    ft_attempted = player.get('total_p1a', 0)
                    player['ft_pct'] = (ft_made / ft_attempted * 100) if ft_attempted > 0 else 0

                    # Ratios
                    total_ast = player.get('total_assist', 0)
                    total_to = player.get('total_to', 0)
                    total_fga = player.get('total_p2a', 0) + player.get('total_p3a', 0)
                    total_fta = player.get('total_p1a', 0)

                    possessions = total_fga + (0.44 * total_fta) + total_ast + total_to
                    player['ast_ratio'] = (100 * total_ast / possessions) if possessions > 0 else 0
                    player['ast_to_ratio'] = total_ast / total_to if total_to > 0 else 0

                    ast_pct = player.get('ast_pct', 0)
                    usage = player.get('usage', 0)
                    player['ast_usg'] = (ast_pct / usage * 100) if usage > 0 else 0

            # Calcular cuartiles de liga para comparación
            progress.setLabelText("Calculando cuartiles de liga...")
            progress.setValue(20)
            QApplication.processEvents()

            league_quartiles = self._calculate_league_quartiles()

            # Generar notas de IA para cada jugador
            progress.setLabelText("Generando notas de IA...")
            progress.setValue(30)
            QApplication.processEvents()

            # Inicializar analizador de IA (preferir Gemini por ser gratis)
            provider = 'gemini' if AnalysisConfig.has_api_key('gemini') else 'openai'
            model = 'flash'  # Usar modelo rápido para múltiples llamadas

            try:
                analyzer = TeamAnalyzer(provider=provider, model=model)
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
                except Exception as e:
                    # Si falla para un jugador, continuar con los demás
                    ai_notes[player_name] = f"Error generando notas: {str(e)}"

            # Obtener datos de tiros
            progress.setLabelText("Obteniendo datos de tiros...")
            progress.setValue(75)
            QApplication.processEvents()

            shots_data = []
            collection = self.db_handler.connection.get_collection(self.collection_name)

            if collection is not None:
                matches = collection.find({
                    "HEADER.TEAM.name": team_name,
                    "SHOTCHART.SHOTS": {"$exists": True}
                })

                for match in matches:
                    if 'SHOTCHART' in match and 'SHOTS' in match['SHOTCHART']:
                        match_shots = match['SHOTCHART']['SHOTS']
                        if isinstance(match_shots, list):
                            shots_data.extend(match_shots)

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
