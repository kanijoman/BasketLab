"""Shot chart visualization window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QLabel, QPushButton, QMessageBox, QComboBox,
                              QProgressBar, QApplication, QRadioButton, QButtonGroup, QDialog)
from PyQt6.QtCore import Qt
from typing import List, Dict, Optional
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from shotcharts import ShotChartVisualizer
from shotcharts.zone_analysis import ZoneAnalyzer
from shotcharts.coordinate_utils import convert_shots_for_zone_analysis
from .ui_utils import set_app_icon
from .team_selector_dialog import TeamSelectorDialog
from .team_utils import get_available_teams_from_collection, get_team_index_in_document, extract_player_names_from_boxscore


class ShotChartWindow(QMainWindow):
    """Window to display shot charts for teams."""

    def __init__(self, db_handler, scraper, collection_name: str, parent=None):
        """
        Initialize the shot chart window.

        Args:
            db_handler: MongoDBHandler instance
            scraper: FEBWebScraper instance
            collection_name: Name of the MongoDB collection
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_handler = db_handler
        self.scraper = scraper
        self.collection_name = collection_name
        self.visualizer = ShotChartVisualizer()
        self.zone_analyzer = ZoneAnalyzer(detail_level='detailed')
        self.current_shots = []
        self.current_team: Optional[Dict] = None
        self.current_players: List[Dict] = []  # Store player info
        self.players_info: Dict[str, str] = {}  # Map dorsal to name
        self.player_id_map: Dict[tuple, Dict] = {}  # Map (team_idx, dorsal) -> {id, name}

        self.setWindowTitle("MfA - Gráficos de Lanzamiento")
        self.setMinimumSize(900, 700)

        # Set application icon
        set_app_icon(self)

        # Get available teams
        self.teams = get_available_teams_from_collection(self.db_handler, self.collection_name)

        self.setup_ui()

        # Show initial message (after setup_ui creates status_label)
        if not self.teams:
            self.status_label.setText("No se encontraron equipos. Los datos se actualizarán automáticamente.")
        else:
            self.status_label.setText(f"{len(self.teams)} equipos disponibles. Seleccione uno para comenzar.")

    def setup_ui(self):
        """Set up the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Control panel
        control_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)

        # Team selection
        control_layout.addWidget(QLabel("Equipo:"))
        self.team_label = QLabel("-- Sin seleccionar --")
        self.team_label.setStyleSheet("font-weight: bold; padding: 5px;")
        control_layout.addWidget(self.team_label)

        self.select_team_button = QPushButton("Seleccionar Equipo")
        self.select_team_button.clicked.connect(self.on_select_team_clicked)
        control_layout.addWidget(self.select_team_button)

        # Player filter
        control_layout.addWidget(QLabel("Jugador:"))
        self.player_combo = QComboBox()
        self.player_combo.addItem("Todos los jugadores")
        self.player_combo.currentIndexChanged.connect(self.on_player_filter_changed)
        self.player_combo.setEnabled(False)  # Disabled until team is selected
        control_layout.addWidget(self.player_combo)

        control_layout.addStretch()

        # Shot filter panel
        filter_layout = QHBoxLayout()
        main_layout.addLayout(filter_layout)

        filter_layout.addWidget(QLabel("Mostrar:"))

        # Radio buttons for shot filtering
        self.filter_group = QButtonGroup(self)

        self.radio_all = QRadioButton("Todos")
        self.radio_all.setChecked(True)
        self.radio_all.toggled.connect(self.on_filter_changed)
        self.filter_group.addButton(self.radio_all)
        filter_layout.addWidget(self.radio_all)

        self.radio_made = QRadioButton("Aciertos")
        self.radio_made.toggled.connect(self.on_filter_changed)
        self.filter_group.addButton(self.radio_made)
        filter_layout.addWidget(self.radio_made)

        self.radio_missed = QRadioButton("Fallos")
        self.radio_missed.toggled.connect(self.on_filter_changed)
        self.filter_group.addButton(self.radio_missed)
        filter_layout.addWidget(self.radio_missed)

        filter_layout.addStretch()

        # Visualization type panel
        viz_layout = QHBoxLayout()
        main_layout.addLayout(viz_layout)

        viz_layout.addWidget(QLabel("Tipo de visualización:"))

        # Radio buttons for visualization type
        self.viz_group = QButtonGroup(self)

        self.radio_scatter = QRadioButton("Scatter Plot")
        self.radio_scatter.setChecked(True)
        self.radio_scatter.toggled.connect(self.on_filter_changed)
        self.viz_group.addButton(self.radio_scatter)
        viz_layout.addWidget(self.radio_scatter)

        self.radio_heatmap = QRadioButton("Mapa de Calor")
        self.radio_heatmap.toggled.connect(self.on_filter_changed)
        self.viz_group.addButton(self.radio_heatmap)
        viz_layout.addWidget(self.radio_heatmap)

        self.radio_zones = QRadioButton("Zonas de Rendimiento")
        self.radio_zones.toggled.connect(self.on_filter_changed)
        self.viz_group.addButton(self.radio_zones)
        viz_layout.addWidget(self.radio_zones)

        viz_layout.addStretch()

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = QLabel("Seleccione un equipo para comenzar")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.status_label)

        # Matplotlib canvas
        self.figure = plt.figure(figsize=(10, 10))
        self.canvas = FigureCanvas(self.figure)
        main_layout.addWidget(self.canvas)

        # Apply styling
        self.setStyleSheet("""
            QComboBox, QPushButton, QLabel {
                font-size: 12px;
                padding: 5px;
            }
            QComboBox {
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
                background-color: #fff;
                min-width: 200px;
            }
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 8px 15px;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
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

    def refresh_teams(self):
        """Refresh the list of available teams."""
        try:
            self.teams = get_available_teams_from_collection(self.db_handler, self.collection_name)

            # Clear current selection
            self.current_team = None
            self.team_label.setText("-- Sin seleccionar --")
            self.status_label.setText(f"Lista actualizada: {len(self.teams)} equipos encontrados")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al actualizar lista de equipos: {str(e)}")

    def on_select_team_clicked(self):
        """Show team selector dialog."""
        if not self.teams:
            QMessageBox.warning(self, "Sin equipos", "No hay equipos disponibles en la base de datos.")
            return

        # Show team selector dialog
        team_names = [team['name'] for team in self.teams]
        dialog = TeamSelectorDialog(team_names, self)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            selected_name = dialog.get_selected_team()
            if selected_name:
                # Find the team data
                selected_team = next((t for t in self.teams if t['name'] == selected_name), None)
                if selected_team:
                    self.current_team = selected_team
                    self.team_label.setText(selected_name)
                    # Reset player combo when changing teams
                    self.player_combo.clear()
                    self.player_combo.addItem("Todos los jugadores")
                    self.player_combo.setEnabled(False)
                    self.status_label.setText(f"Cargando datos para {selected_name}...")
                    QApplication.processEvents()
                    # Generate chart automatically
                    self.on_generate_chart()

    def on_team_changed(self, index: int):
        """Handle team selection change - deprecated, kept for compatibility."""
        pass

    def on_filter_changed(self):
        """Handle shot filter change and redraw chart if data exists."""
        # If Zones visualization is selected, force "All shots" filter and disable other filters
        if self.radio_zones.isChecked():
            self.radio_all.setChecked(True)
            self.radio_made.setEnabled(False)
            self.radio_missed.setEnabled(False)
        else:
            # Re-enable filters for other visualization types
            self.radio_made.setEnabled(True)
            self.radio_missed.setEnabled(True)

        if self.current_shots:
            # Redraw the chart with the current filter
            self._draw_chart()

    def on_update_data(self):
        """Update shot chart data from FEB."""
        try:
            self.progress_bar.setVisible(True)
            self.status_label.setText("Actualizando datos de gráficos de lanzamiento...")
            QApplication.processEvents()

            collection = self.db_handler.connection.get_collection(self.collection_name)
            if collection is None:
                QMessageBox.warning(self, "Error", "No se pudo acceder a la colección de datos.")
                self.progress_bar.setVisible(False)
                return

            documents = list(collection.find({}))

            if not documents:
                QMessageBox.information(self, "Sin datos",
                                      "No hay partidos en la base de datos. Por favor, actualice primero las estadísticas.")
                self.progress_bar.setVisible(False)
                return

            self.progress_bar.setMaximum(len(documents))
            self.progress_bar.setValue(0)

            updated = 0
            skipped = 0

            import requests
            session = requests.Session()

            for i, doc in enumerate(documents):
                match_code = str(doc.get('_id', ''))
                self.status_label.setText(f"Procesando partido {match_code}... ({i+1}/{len(documents)})")
                self.progress_bar.setValue(i + 1)
                QApplication.processEvents()

                if 'SHOTCHART' in doc and doc['SHOTCHART']:
                    skipped += 1
                    continue

                try:
                    token = self.scraper.token_manager.get_token()
                    shotchart_data = self.scraper.fetch_shotchart(match_code, session, token)

                    if shotchart_data:
                        collection.update_one(
                            {'_id': int(match_code)},
                            {'$set': {'SHOTCHART': shotchart_data}}
                        )
                        updated += 1

                except Exception:
                    pass  # Skip failed matches silently

            self.progress_bar.setVisible(False)
            self.status_label.setText(
                f"Actualización completa: {updated} partidos actualizados, {skipped} ya tenían datos"
            )

            self.refresh_teams()

            QMessageBox.information(self, "Actualización completa",
                                  f"Se actualizaron {updated} partidos.\n{skipped} partidos ya tenían datos de gráficos de lanzamiento.")

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.status_label.setText("Error en la actualización")
            QMessageBox.critical(self, "Error", f"Error al actualizar datos: {str(e)}")

    def on_generate_chart(self):
        """Generate shot chart for selected team."""
        if not self.current_team:
            return

        team = self.current_team
        try:
            self.status_label.setText(f"Generando gráfico de lanzamiento para {team['name']}...")
            QApplication.processEvents()

            collection = self.db_handler.connection.get_collection(self.collection_name)
            if collection is None:
                QMessageBox.warning(self, "Error", "No se pudo acceder a la colección de datos.")
                return

            all_shots = []
            documents = collection.find({})

            # Extract player information from SHOTCHART.TEAM.PLAYER for ID mapping
            players_info = {}  # {dorsal: name}
            player_id_map = {}  # {(team_idx, dorsal): {id, name}}

            for doc in documents:
                if 'SHOTCHART' not in doc or not doc['SHOTCHART']:
                    continue

                if 'SHOTS' not in doc['SHOTCHART']:
                    continue

                shots = doc['SHOTCHART']['SHOTS']
                team_index = get_team_index_in_document(doc, team['code'])

                if team_index is None:
                    continue

                # Extract player names and IDs from SHOTCHART.TEAM.PLAYER
                shotchart = doc['SHOTCHART']
                if 'TEAM' in shotchart and isinstance(shotchart['TEAM'], list):
                    if team_index < len(shotchart['TEAM']):
                        team_data = shotchart['TEAM'][team_index]
                        if 'PLAYER' in team_data and isinstance(team_data['PLAYER'], list):
                            for player in team_data['PLAYER']:
                                dorsal = str(player.get('no', '')).lstrip('0') or player.get('no', '')
                                player_id = player.get('id', '')
                                player_name = player.get('name', '')

                                if dorsal and player_id:
                                    # Map (team_index, dorsal) to player info
                                    key = (team_index, str(dorsal))
                                    player_id_map[key] = {
                                        'id': player_id,
                                        'name': player_name,
                                        'dorsal': str(dorsal)
                                    }
                                    # Also keep simple dorsal->name mapping for display
                                    if dorsal:
                                        players_info[str(dorsal)] = player_name

                # Add player_id to each shot for proper filtering
                team_shots = []
                for shot in shots:
                    if shot.get('team', '') == str(team_index):
                        shot_copy = shot.copy()
                        dorsal = str(shot.get('player', ''))
                        key = (team_index, dorsal)
                        if key in player_id_map:
                            shot_copy['player_id'] = player_id_map[key]['id']
                            shot_copy['player_name'] = player_id_map[key]['name']
                        team_shots.append(shot_copy)

                all_shots.extend(team_shots)

            if not all_shots:
                QMessageBox.information(self, "Sin datos",
                                      f"No se encontraron datos de lanzamientos para {team['name']}")
                self.status_label.setText("Sin datos de lanzamientos")
                return

            self.current_shots = all_shots
            self.current_team = team
            self.players_info = players_info
            self.player_id_map = player_id_map

            # Extract unique players from shots and populate combo
            self._populate_player_combo(all_shots, players_info)

            self._draw_chart()

            # Adjust window size to fit the chart properly
            # Account for controls, filters, viz type selector, status, progress bar, and margins
            self.resize(1050, 1100)

        except Exception as e:
            self.status_label.setText("Error al generar gráfico de lanzamiento")
            QMessageBox.critical(self, "Error", f"Error al generar gráfico de lanzamiento: {str(e)}")

    def _populate_player_combo(self, shots: List[Dict], players_info: Dict[str, str]):
        """Populate player combo box with unique players from shots.

        Args:
            shots: List of shot dictionaries
            players_info: Dictionary mapping dorsal number to player name
        """
        # Extract unique players by player_id (not just dorsal)
        players_dict = {}  # {player_id: {dorsal, name}}
        for shot in shots:
            player_id = shot.get('player_id', '')
            player_dorsal = shot.get('player', '')
            player_name = shot.get('player_name', '')

            if player_id:
                if player_id not in players_dict:
                    players_dict[player_id] = {
                        'dorsal': str(player_dorsal),
                        'name': player_name or players_info.get(str(player_dorsal), '')
                    }

        # Sort players by dorsal number
        sorted_players = sorted(
            players_dict.items(),
            key=lambda x: int(x[1]['dorsal']) if x[1]['dorsal'].isdigit() else 999
        )

        # Clear and repopulate combo
        self.player_combo.blockSignals(True)  # Prevent triggering filter during population
        self.player_combo.clear()
        self.player_combo.addItem("Todos los jugadores", None)

        for player_id, player_info in sorted_players:
            dorsal = player_info['dorsal']
            name = player_info['name']
            if name:
                display_text = f"#{dorsal} - {name}"
            else:
                display_text = f"#{dorsal}"
            # Store player_id as data, not dorsal
            self.player_combo.addItem(display_text, player_id)

        self.player_combo.setCurrentIndex(0)
        self.player_combo.setEnabled(True)
        self.player_combo.blockSignals(False)

    def on_player_filter_changed(self):
        """Handle player filter change and redraw chart."""
        if self.current_shots:
            self._draw_chart()

    def _draw_chart(self):
        """Draw or redraw the shot chart based on current filter."""
        if not self.current_shots or not self.current_team:
            return

        # Filter shots based on player selection (by player_id, not dorsal)
        selected_player_id = self.player_combo.currentData()
        if selected_player_id is not None:
            # Filter by player_id to avoid mixing shots from different players with same dorsal
            player_filtered_shots = [s for s in self.current_shots if s.get('player_id', '') == selected_player_id]
        else:
            player_filtered_shots = self.current_shots

        # Filter shots based on radio button selection (made/missed)
        if self.radio_made.isChecked():
            filtered_shots = [s for s in player_filtered_shots if int(s.get('m', 0)) == 1]
            filter_text = "Aciertos"
        elif self.radio_missed.isChecked():
            filtered_shots = [s for s in player_filtered_shots if int(s.get('m', 0)) == 0]
            filter_text = "Fallos"
        else:
            filtered_shots = player_filtered_shots
            filter_text = "Todos"

        # Calculate statistics
        made_count = sum(1 for s in filtered_shots if int(s.get('m', 0)) == 1)
        total_count = len(filtered_shots)
        accuracy = (made_count / total_count * 100) if total_count > 0 else 0
        total_all = len(self.current_shots)

        # Build title with player info if filtered
        if selected_player is not None:
            # Get player name from combo display text
            current_index = self.player_combo.currentIndex()
            if current_index > 0:  # Skip "Todos los jugadores"
                player_display = self.player_combo.itemText(current_index)
                title = f"{player_display}\n{made_count}/{total_count} ({accuracy:.1f}%)"
            else:
                title = f"{self.current_team['name']}\n{made_count}/{total_count} ({accuracy:.1f}%)"
        else:
            title = f"{self.current_team['name']}\n{made_count}/{total_count} ({accuracy:.1f}%)"

        self.figure.clear()

        # Choose visualization type
        if self.radio_zones.isChecked():
            # Plot performance zones using utility function for coordinate conversion
            processed_shots = convert_shots_for_zone_analysis(filtered_shots)

            # Analyze zone performance
            stats = self.zone_analyzer.analyze_zone_performance(processed_shots)

            # Create the zone performance visualization
            new_fig = self.zone_analyzer.plot_zone_analysis(
                stats=stats,
                title=f"{self.current_team['name']} - Análisis por Zonas\n{made_count}/{total_count} ({accuracy:.1f}%)",
                figsize=(10, 10)
            )
            viz_type = "Zonas de Rendimiento"

        elif self.radio_heatmap.isChecked():
            # Plot heatmap
            new_fig = self.visualizer.plot_heatmap(
                shots=filtered_shots,
                title=title,
                figsize=(10, 10),
                alpha=0.6
            )
            viz_type = "Mapa de Calor"
        else:
            # Plot scatter (default)
            new_fig = self.visualizer.plot_shots(
                shots=filtered_shots,
                title=title,
                figsize=(10, 10),
                show_legend=True,
                legend_loc='lower center'
            )
            viz_type = "Scatter Plot"

        self.figure = new_fig
        self.canvas.figure = new_fig
        self.canvas.draw()

        self.status_label.setText(
            f"{viz_type} - {filter_text}: {total_count} lanzamientos "
            f"({made_count} anotados, {total_count - made_count} fallados) | Total: {total_all}"
        )
