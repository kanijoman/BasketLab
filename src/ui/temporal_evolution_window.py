"""Temporal evolution analysis window for tracking team statistics over time."""

from typing import List, Dict, Optional
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QComboBox, QLabel, QPushButton, QMessageBox, QFileDialog)
from PyQt6.QtCore import Qt
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.figure import Figure
import numpy as np

from database import MongoDBHandler
from database.aggregation.pipeline_builder import AggregationPipelineBuilder
from ui.stats_calculator import StatsCalculator
from ui.stats_config import TEMPORAL_STATS_OPTIONS


class TemporalEvolutionWindow(QMainWindow):
    """Window for analyzing temporal evolution of team statistics."""

    def __init__(self, collection_name: str, db_handler: MongoDBHandler, is_fbcyl: bool = False, parent=None):
        """
        Initialize temporal evolution window.

        Args:
            collection_name: Name of the collection to query
            db_handler: Database handler instance
            is_fbcyl: Whether this is FBCYL data format (True) or FEB format (False)
            parent: Parent widget
        """
        super().__init__(parent)
        self.collection_name = collection_name
        self.db_handler = db_handler
        self.is_fbcyl = is_fbcyl
        self.stats_calculator = StatsCalculator()
        self.all_teams = []
        self.match_data = []

        self.setWindowTitle("MfA - Evolución Temporal")
        self.setMinimumSize(1000, 700)

        self.setup_ui()
        self.load_teams()

    def setup_ui(self):
        """Setup the user interface."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Selection controls
        controls_layout = QHBoxLayout()

        # Team selector
        controls_layout.addWidget(QLabel("Equipo:"))
        self.team_combo = QComboBox()
        self.team_combo.currentTextChanged.connect(self.on_team_changed)
        controls_layout.addWidget(self.team_combo)

        # Statistic selector
        controls_layout.addWidget(QLabel("Estadística:"))
        self.stat_combo = QComboBox()
        self.stat_combo.addItems(sorted(TEMPORAL_STATS_OPTIONS.keys()))
        controls_layout.addWidget(self.stat_combo)

        # Generate button
        self.generate_btn = QPushButton("📈 Generar Gráfico")
        self.generate_btn.clicked.connect(self.generate_plot)
        self.generate_btn.setEnabled(False)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        controls_layout.addWidget(self.generate_btn)

        # Export buttons
        self.export_png_btn = QPushButton("💾 Exportar PNG")
        self.export_png_btn.clicked.connect(self.export_as_png)
        self.export_png_btn.setEnabled(False)
        self.export_png_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 9pt;
                padding: 8px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        controls_layout.addWidget(self.export_png_btn)

        self.export_pdf_btn = QPushButton("📄 Exportar PDF")
        self.export_pdf_btn.clicked.connect(self.export_as_pdf)
        self.export_pdf_btn.setEnabled(False)
        self.export_pdf_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                font-size: 9pt;
                padding: 8px 15px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)
        controls_layout.addWidget(self.export_pdf_btn)

        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

        # Matplotlib figure
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)

        # Info label
        self.info_label = QLabel("Seleccione un equipo y una estadística para visualizar su evolución temporal.")
        self.info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.info_label.setStyleSheet("color: gray; font-style: italic; padding: 10px;")
        main_layout.addWidget(self.info_label)

    def load_teams(self):
        """Load all teams from the database."""
        try:
            self.all_teams = self.db_handler.get_all_teams(self.collection_name)
            if self.all_teams:
                self.team_combo.addItems(self.all_teams)
                self.info_label.setText(f"{len(self.all_teams)} equipos disponibles")
            else:
                self.info_label.setText("No se encontraron equipos en la base de datos")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar equipos: {str(e)}")

    def on_team_changed(self, team_name: str):
        """Handle team selection change."""
        if team_name:
            self.generate_btn.setEnabled(True)
            self.load_team_matches(team_name)
        else:
            self.generate_btn.setEnabled(False)

    def load_team_matches(self, team_name: str):
        """Load all matches for the selected team."""
        try:
            # Get pipeline from builder based on data format
            if self.is_fbcyl:
                pipeline = AggregationPipelineBuilder.build_team_matches_timeline_pipeline_fbcyl(team_name)
            else:
                pipeline = AggregationPipelineBuilder.build_team_matches_timeline_pipeline(team_name)

            # Execute aggregation
            collection = self.db_handler.repository.connection.get_collection(self.collection_name)
            self.match_data = list(collection.aggregate(pipeline))
            self.info_label.setText(f"{len(self.match_data)} partidos encontrados para {team_name}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al cargar partidos: {str(e)}")
            self.match_data = []

    def calculate_stat_for_match(self, match: Dict, stat_field: str) -> Optional[float]:
        """Calculate a specific statistic for a match using StatsCalculator."""
        try:
            team_data = match.get('team_data', {})
            opponent_data = match.get('opponent_data', {})

            # Use StatsCalculator to get the stat value
            return self.stats_calculator.calculate_stat_value(team_data, opponent_data, stat_field)

        except Exception as e:
            print(f"Error calculating stat: {e}")
            return None

    def generate_plot(self):
        """Generate the temporal evolution plot."""
        if not self.match_data:
            QMessageBox.warning(self, "Sin datos", "No hay datos de partidos disponibles")
            return

        team_name = self.team_combo.currentText()
        stat_name = self.stat_combo.currentText()
        stat_field, lower_is_better = TEMPORAL_STATS_OPTIONS[stat_name]

        # Calculate stat for each match
        dates = []
        values = []

        for match in self.match_data:
            stat_value = self.calculate_stat_for_match(match, stat_field)
            if stat_value is not None:
                dates.append(match['date'])
                values.append(stat_value)

        if not values:
            QMessageBox.warning(self, "Sin datos", "No se pudieron calcular estadísticas")
            return

        # Calculate cumulative season average (from game 1 to current game)
        cumulative_avg = []
        for i in range(len(values)):
            cumulative_avg.append(np.mean(values[:i+1]))

        # Calculate cumulative league average for each matchday
        league_avg_cumulative = self.calculate_league_average_cumulative(stat_field, dates)

        # Clear previous plot
        self.figure.clear()
        ax = self.figure.add_subplot(111)

        # Plot data
        x_indices = list(range(len(dates)))

        # Plot individual match values
        ax.plot(x_indices, values, 'o-', alpha=0.5, label='Por partido',
                color='#2196F3', linewidth=1.5, markersize=6)

        # Plot cumulative season average
        ax.plot(x_indices, cumulative_avg, '-', label='Promedio de temporada',
                color='#FF5722', linewidth=2.5)

        # Plot league average cumulative if available
        if league_avg_cumulative and len(league_avg_cumulative) == len(x_indices):
            ax.plot(x_indices, league_avg_cumulative, '--', label='Promedio de liga',
                    color='green', linewidth=2, alpha=0.7)

        # Styling
        ax.set_xlabel('Partido (cronológico)', fontsize=11, fontweight='bold')
        ax.set_ylabel(stat_name, fontsize=11, fontweight='bold')
        ax.set_title(f'Evolución Temporal: {team_name} - {stat_name}',
                    fontsize=13, fontweight='bold', pad=15)

        # Place legend outside the plot area (to the right)
        ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5), framealpha=0.9, fontsize=10)
        ax.grid(True, alpha=0.3, linestyle='--')

        # Add margins to prevent first point from being cut off
        ax.margins(x=0.02)

        # Format x-axis labels
        if len(dates) > 20:
            # Show fewer labels if too many matches
            step = len(dates) // 10
            ax.set_xticks(x_indices[::step])
            ax.set_xticklabels([f"P{i+1}" for i in x_indices[::step]], rotation=45)
        else:
            ax.set_xticks(x_indices)
            ax.set_xticklabels([f"P{i+1}" for i in x_indices], rotation=45)

        # Add stats text box (respecting lower_is_better logic)
        textstr = f'Partidos: {len(values)}\n'
        textstr += f'Media: {np.mean(values):.2f}\n'

        # For lower_is_better stats, "best" is minimum, otherwise maximum
        if lower_is_better:
            textstr += f'Mejor: {np.min(values):.2f}\n'
            textstr += f'Peor: {np.max(values):.2f}'
        else:
            textstr += f'Mejor: {np.max(values):.2f}\n'
            textstr += f'Peor: {np.min(values):.2f}'

        if league_avg_cumulative and len(league_avg_cumulative) > 0:
            league_final_avg = league_avg_cumulative[-1]
            diff = np.mean(values) - league_final_avg
            # For lower_is_better, negative diff is good
            textstr += f'\nDif. Liga: {diff:+.2f}'

        props = dict(boxstyle='round', facecolor='wheat', alpha=0.8)
        # Position text box outside the plot area (below)
        ax.text(0.5, -0.25, textstr, transform=ax.transAxes, fontsize=9,
                verticalalignment='top', horizontalalignment='center', bbox=props)

        self.figure.tight_layout()
        self.canvas.draw()

        # Enable export buttons
        self.export_png_btn.setEnabled(True)
        self.export_pdf_btn.setEnabled(True)

        self.info_label.setText(f"Gráfico generado: {len(values)} partidos analizados")

    def calculate_league_average_cumulative(self, stat_field: str, dates: List) -> Optional[List[float]]:
        """
        Calculate cumulative league average for each matchday.

        For each date in the input list, calculates the average of the statistic
        across all teams considering only matches played up to that date.

        Args:
            stat_field: The statistic field to calculate
            dates: List of dates (one per match) to calculate averages for

        Returns:
            List of cumulative league averages, one per date, or None if error
        """
        try:
            collection = self.db_handler.repository.connection.get_collection(self.collection_name)

            # Get all teams in the league
            all_teams = self.all_teams
            if not all_teams:
                return None

            league_averages = []

            # For each date, calculate the league average up to that date
            for target_date in dates:
                date_values = []

                # For each team, get their stats up to this date
                for team_name in all_teams:
                    # Get pipeline for this team based on data format
                    if self.is_fbcyl:
                        pipeline = AggregationPipelineBuilder.build_team_matches_timeline_pipeline_fbcyl(team_name)
                    else:
                        pipeline = AggregationPipelineBuilder.build_team_matches_timeline_pipeline(team_name)

                    # Add a filter to only include matches up to target_date
                    pipeline.append({
                        "$match": {
                            "date": {"$lte": target_date}
                        }
                    })

                    team_matches = list(collection.aggregate(pipeline))

                    # Calculate stat for each match and get average
                    team_values = []
                    for match in team_matches:
                        stat_value = self.calculate_stat_for_match(match, stat_field)
                        if stat_value is not None:
                            team_values.append(stat_value)

                    # Add team's average to league values
                    if team_values:
                        date_values.append(np.mean(team_values))

                # Calculate league average for this date
                if date_values:
                    league_averages.append(np.mean(date_values))
                else:
                    league_averages.append(None)

            # Return None if no valid values
            if all(v is None for v in league_averages):
                return None

            return league_averages

        except Exception as e:
            print(f"Error calculating cumulative league average: {e}")
            return None

    def export_as_png(self):
        """Export the current plot as PNG."""
        try:
            from PyQt6.QtWidgets import QFileDialog

            team_name = self.team_combo.currentText()
            stat_name = self.stat_combo.currentText()

            default_name = f"evolucion_{team_name.replace(' ', '_')}_{stat_name.replace(' ', '_').replace('/', '_')}.png"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar gráfico como PNG",
                default_name,
                "Imágenes PNG (*.png)"
            )

            if file_path:
                self.figure.savefig(file_path, dpi=300, bbox_inches='tight')
                QMessageBox.information(self, "Éxito", f"Gráfico guardado en:\n{file_path}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al exportar PNG: {str(e)}")

    def export_as_pdf(self):
        """Export the current plot as PDF."""
        try:
            from PyQt6.QtWidgets import QFileDialog

            team_name = self.team_combo.currentText()
            stat_name = self.stat_combo.currentText()

            default_name = f"evolucion_{team_name.replace(' ', '_')}_{stat_name.replace(' ', '_').replace('/', '_')}.pdf"

            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar gráfico como PDF",
                default_name,
                "Documentos PDF (*.pdf)"
            )

            if file_path:
                self.figure.savefig(file_path, format='pdf', bbox_inches='tight')
                QMessageBox.information(self, "Éxito", f"Gráfico guardado en:\n{file_path}")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al exportar PDF: {str(e)}")
