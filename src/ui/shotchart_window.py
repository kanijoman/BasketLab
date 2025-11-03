"""Shot chart visualization window."""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QComboBox, QLabel, QPushButton, QMessageBox,
                              QProgressBar, QApplication, QRadioButton, QButtonGroup)
from PyQt6.QtCore import Qt
from typing import List, Dict
import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from shotcharts import ShotChartVisualizer


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
        self.current_shots = []
        self.current_team = None

        self.setWindowTitle("Shot Charts - Gráficos de Lanzamiento")
        self.setMinimumSize(900, 700)

        # Get available teams
        self.teams = self._get_available_teams()

        self.setup_ui()

        # Show initial message (after setup_ui creates status_label)
        if not self.teams:
            self.status_label.setText("No se encontraron equipos. Los datos se actualizarán automáticamente.")
        else:
            self.status_label.setText(f"{len(self.teams)} equipos disponibles. Seleccione uno para comenzar.")

    def _get_available_teams(self) -> List[Dict]:
        """Get list of available teams from the collection."""
        try:
            collection = self.db_handler.connection.get_collection(self.collection_name)
            if collection is None:
                return []

            documents = list(collection.find({}))
            teams_dict = {}

            for doc in documents:
                # Try BOXSCORE.TEAM first (primary source)
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

                # Fallback: Try HEADER.TEAM
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

        except Exception as e:
            return []

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
        self.team_combo = QComboBox()
        self.team_combo.addItem("-- Seleccionar equipo --", None)
        for team in self.teams:
            self.team_combo.addItem(team['name'], team)
        self.team_combo.currentIndexChanged.connect(self.on_team_changed)
        control_layout.addWidget(self.team_combo)

        # Generate button
        self.generate_button = QPushButton("Generar Gráfico de Tiro")
        self.generate_button.setEnabled(False)
        self.generate_button.clicked.connect(self.on_generate_chart)
        control_layout.addWidget(self.generate_button)

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
            self.teams = self._get_available_teams()

            # Update combo box
            current_selection = self.team_combo.currentData()
            self.team_combo.clear()
            self.team_combo.addItem("-- Seleccionar equipo --", None)

            for team in self.teams:
                self.team_combo.addItem(team['name'], team)

            # Try to restore previous selection
            if current_selection:
                for i in range(self.team_combo.count()):
                    if self.team_combo.itemData(i) == current_selection:
                        self.team_combo.setCurrentIndex(i)
                        break

            self.status_label.setText(f"Lista actualizada: {len(self.teams)} equipos encontrados")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error al actualizar lista de equipos: {str(e)}")

    def on_team_changed(self, index: int):
        """Handle team selection change."""
        team = self.team_combo.currentData()
        if team:
            self.generate_button.setEnabled(True)
            self.status_label.setText(f"Equipo seleccionado: {team['name']}")
        else:
            self.generate_button.setEnabled(False)
            self.status_label.setText("Seleccione un equipo para comenzar")

    def on_filter_changed(self):
        """Handle shot filter change and redraw chart if data exists."""
        if self.current_shots:
            # Redraw the chart with the current filter
            self._draw_chart()

    def on_update_data(self):
        """Update shot chart data from FEB."""
        try:
            self.progress_bar.setVisible(True)
            self.status_label.setText("Actualizando datos de shot charts...")
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
                                  f"Se actualizaron {updated} partidos.\n{skipped} partidos ya tenían datos de shot chart.")

        except Exception as e:
            self.progress_bar.setVisible(False)
            self.status_label.setText("Error en la actualización")
            QMessageBox.critical(self, "Error", f"Error al actualizar datos: {str(e)}")

    def on_generate_chart(self):
        """Generate shot chart for selected team."""
        team = self.team_combo.currentData()
        if not team:
            return

        try:
            self.status_label.setText(f"Generando shot chart para {team['name']}...")
            QApplication.processEvents()

            collection = self.db_handler.connection.get_collection(self.collection_name)
            if collection is None:
                QMessageBox.warning(self, "Error", "No se pudo acceder a la colección de datos.")
                return

            all_shots = []
            documents = collection.find({})

            for doc in documents:
                if 'SHOTCHART' not in doc or not doc['SHOTCHART']:
                    continue

                if 'SHOTS' not in doc['SHOTCHART']:
                    continue

                shots = doc['SHOTCHART']['SHOTS']
                team_index = self._get_team_index(doc, team['code'])

                if team_index is None:
                    continue

                team_shots = [s for s in shots if s.get('team', '') == str(team_index)]
                all_shots.extend(team_shots)

            if not all_shots:
                QMessageBox.information(self, "Sin datos",
                                      f"No se encontraron datos de lanzamientos para {team['name']}")
                self.status_label.setText("Sin datos de lanzamientos")
                return

            self.current_shots = all_shots
            self.current_team = team

            self._draw_chart()

            # Adjust window size to fit the chart properly
            self.resize(1050, 1050)

        except Exception as e:
            self.status_label.setText("Error al generar shot chart")
            QMessageBox.critical(self, "Error", f"Error al generar shot chart: {str(e)}")

    def _get_team_index(self, doc: Dict, team_code: str) -> int:
        """
        Determine team index (0 or 1) in a match document.

        Args:
            doc: Match document
            team_code: Team code to search for

        Returns:
            Team index (0 or 1) or None if not found
        """
        # Check BOXSCORE.TEAM array
        if 'BOXSCORE' in doc and 'TEAM' in doc['BOXSCORE']:
            teams = doc['BOXSCORE']['TEAM']
            if isinstance(teams, list):
                for idx, team_data in enumerate(teams):
                    if isinstance(team_data, dict) and 'TOTAL' in team_data:
                        if team_data['TOTAL'].get('teamCode', '') == team_code:
                            return idx

        # Fallback: check HEADER.TEAM
        if 'HEADER' in doc and 'TEAM' in doc['HEADER']:
            teams = doc['HEADER']['TEAM']
            if isinstance(teams, list):
                for idx, team_data in enumerate(teams):
                    if isinstance(team_data, dict):
                        if team_data.get('teamCode', '') == team_code:
                            return idx

        return None

    def _draw_chart(self):
        """Draw or redraw the shot chart based on current filter."""
        if not self.current_shots or not self.current_team:
            return

        # Filter shots based on radio button selection
        if self.radio_made.isChecked():
            filtered_shots = [s for s in self.current_shots if int(s.get('m', 0)) == 1]
            filter_text = "Aciertos"
        elif self.radio_missed.isChecked():
            filtered_shots = [s for s in self.current_shots if int(s.get('m', 0)) == 0]
            filter_text = "Fallos"
        else:
            filtered_shots = self.current_shots
            filter_text = "Todos"

        # Calculate statistics
        made_count = sum(1 for s in filtered_shots if int(s.get('m', 0)) == 1)
        total_count = len(filtered_shots)
        accuracy = (made_count / total_count * 100) if total_count > 0 else 0
        total_all = len(self.current_shots)

        title = f"{self.current_team['name']}\n{made_count}/{total_count} ({accuracy:.1f}%)"

        self.figure.clear()

        new_fig = self.visualizer.plot_shots(
            shots=filtered_shots,
            title=title,
            figsize=(10, 10),
            show_legend=True,
            legend_loc='lower center'
        )

        self.figure = new_fig
        self.canvas.figure = new_fig
        self.canvas.draw()

        self.status_label.setText(
            f"Mostrando {filter_text}: {total_count} lanzamientos "
            f"({made_count} anotados, {total_count - made_count} fallados) | Total: {total_all}"
        )
