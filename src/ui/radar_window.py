"""Window for displaying radar chart visualization of player statistics."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QLabel, QComboBox, QMessageBox)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from typing import List, Dict, Optional, Any

from .ui_utils import set_app_icon
from visualization.radar_chart import RadarChart


class RadarChartWindow(QMainWindow):
    """Window to display radar chart visualization for player statistics."""

    def __init__(self, all_players: List[Dict[str, Any]],
                 selected_player: Optional[Dict[str, Any]] = None,
                 parent: Optional[QWidget] = None):
        """
        Initialize the radar chart window.

        Args:
            all_players: List of all player statistics (for league comparison)
            selected_player: Initially selected player data
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("MfA - Gráfico Radar de Jugador")
        self.setMinimumSize(1000, 800)

        # Set application icon
        set_app_icon(self)

        self.all_players = all_players
        self.selected_player = selected_player
        self.radar_chart = RadarChart(figsize=(10, 8))

        # Get list of players sorted by name
        self.players_list = sorted(all_players, key=lambda x: x.get('player_name', ''))

        self.setup_ui()

        # Show initial chart if a player is selected
        if self.selected_player:
            self.update_chart()

    def setup_ui(self):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("Análisis Radar - Comparación con Competición")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(title_label)

        # Controls section
        controls_layout = QHBoxLayout()

        # Player selector
        player_label = QLabel("Seleccionar Jugador:")
        player_label.setStyleSheet("font-weight: bold;")
        controls_layout.addWidget(player_label)

        self.player_combo = QComboBox()
        self.player_combo.setMinimumWidth(250)

        # Populate player combo box
        for player in self.players_list:
            player_name = player.get('player_name', 'Unknown')
            team_name = player.get('team_name', '')
            display_text = f"{player_name} ({team_name})"
            self.player_combo.addItem(display_text, player)

        # Set initial selection if provided
        if self.selected_player:
            selected_name = self.selected_player.get('player_name', '')
            for i in range(self.player_combo.count()):
                player = self.player_combo.itemData(i)
                if player.get('player_name') == selected_name:
                    self.player_combo.setCurrentIndex(i)
                    break

        self.player_combo.currentIndexChanged.connect(self._on_player_changed)
        self.player_combo.currentIndexChanged.connect(self.update_chart)
        controls_layout.addWidget(self.player_combo)

        controls_layout.addStretch()

        main_layout.addLayout(controls_layout)

        # Chart canvas
        self.canvas = None
        self.chart_layout = QVBoxLayout()
        main_layout.addLayout(self.chart_layout)

    def _on_player_changed(self, index: int):
        """Handle player selection change."""
        if index >= 0:
            self.selected_player = self.player_combo.itemData(index)

    def update_chart(self):
        """Update the radar chart with current player data."""
        if not self.selected_player:
            QMessageBox.warning(self, "Sin selección",
                              "Por favor selecciona un jugador.")
            return

        try:
            # Calculate metrics for the selected player
            player_metrics = self.radar_chart.calculate_metrics_from_stats(self.selected_player)

            # Calculate metrics for all players (for comparison)
            league_metrics = []
            for player in self.all_players:
                metrics = self.radar_chart.calculate_metrics_from_stats(player)
                league_metrics.append(metrics)

            # Get player name
            player_name = self.selected_player.get('player_name', 'Desconocido')
            team_name = self.selected_player.get('team_name', '')
            title = f"Análisis Radar - {player_name} ({team_name})"

            # Create the chart
            fig = self.radar_chart.create_chart(player_metrics, league_metrics,
                                                player_name, title)

            # Clear previous chart if exists and close old figure
            if self.canvas:
                # Close the old figure to free memory
                old_fig = self.canvas.figure
                if old_fig:
                    import matplotlib.pyplot as plt
                    plt.close(old_fig)

                self.chart_layout.removeWidget(self.canvas)
                self.canvas.deleteLater()

            # Create new canvas with the figure
            self.canvas = FigureCanvas(fig)

            # Add to layout
            self.chart_layout.addWidget(self.canvas)

            self.canvas.draw()

        except Exception as e:
            QMessageBox.critical(self, "Error",
                               f"Error al generar el gráfico: {str(e)}")
            print(f"[RadarChartWindow] Error creating chart: {e}")
            import traceback
            traceback.print_exc()

    def keyPressEvent(self, event):
        """Handle key press events for shortcuts."""
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QKeySequence

        # Ctrl+S to save/export
        if event.key() == Qt.Key.Key_S and event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            self.export_chart()
        else:
            super().keyPressEvent(event)

    def export_chart(self):
        """Export the current chart as an image."""
        if not self.canvas:
            QMessageBox.warning(self, "Sin gráfico",
                              "No hay ningún gráfico para exportar.")
            return

        try:
            from PyQt6.QtWidgets import QFileDialog

            player_name = self.selected_player.get('player_name', 'jugador')
            default_filename = f"radar_{player_name.replace(' ', '_')}.png"

            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Guardar Gráfico",
                default_filename,
                "PNG Files (*.png);;PDF Files (*.pdf);;All Files (*)"
            )

            if filename:
                self.canvas.figure.savefig(filename, dpi=300, bbox_inches='tight')
                QMessageBox.information(self, "Éxito",
                                      f"Gráfico guardado en:\n{filename}")

        except Exception as e:
            QMessageBox.critical(self, "Error",
                               f"Error al exportar el gráfico: {str(e)}")
            print(f"[RadarChartWindow] Error exporting chart: {e}")
