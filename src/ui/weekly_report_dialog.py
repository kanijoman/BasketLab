"""Dialog for configuring weekly report generation."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QPushButton, QComboBox, QFileDialog, QLineEdit,
                              QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt
from typing import List, Optional, Dict


class WeeklyReportDialog(QDialog):
    """Dialog to configure weekly report generation."""

    def __init__(self, teams: List[str], parent=None):
        """
        Initialize weekly report dialog.

        Args:
            teams: List of available team names
            parent: Parent widget
        """
        super().__init__(parent)
        self.teams = sorted(teams)
        self.selected_team_a: Optional[str] = None
        self.selected_team_b: Optional[str] = None
        self.output_folder: Optional[str] = None

        self.setWindowTitle("Generar Informe Semanal")
        self.setMinimumSize(500, 400)
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Configuración del Informe Semanal")
        title_label.setStyleSheet("font-size: 14pt; font-weight: bold; margin-bottom: 10px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel(
            "Este informe generará estadísticas completas y gráficos de lanzamiento\n"
            "para dos equipos (propio y rival) en formato PNG."
        )
        desc_label.setStyleSheet("color: gray; font-size: 10pt; margin-bottom: 15px;")
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Team selection group
        team_group = QGroupBox("Selección de Equipos")
        team_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        team_layout = QVBoxLayout(team_group)

        # Team A (own team) selection
        team_a_layout = QHBoxLayout()
        team_a_label = QLabel("Equipo Propio (A):")
        team_a_label.setMinimumWidth(150)
        self.team_a_combo = QComboBox()
        self.team_a_combo.addItem("-- Seleccionar --", None)
        for team in self.teams:
            self.team_a_combo.addItem(team, team)
        self.team_a_combo.currentIndexChanged.connect(self._validate_selection)
        team_a_layout.addWidget(team_a_label)
        team_a_layout.addWidget(self.team_a_combo, 1)
        team_layout.addLayout(team_a_layout)

        # Team B (opponent) selection
        team_b_layout = QHBoxLayout()
        team_b_label = QLabel("Equipo Rival (B):")
        team_b_label.setMinimumWidth(150)
        self.team_b_combo = QComboBox()
        self.team_b_combo.addItem("-- Seleccionar --", None)
        for team in self.teams:
            self.team_b_combo.addItem(team, team)
        self.team_b_combo.currentIndexChanged.connect(self._validate_selection)
        team_b_layout.addWidget(team_b_label)
        team_b_layout.addWidget(self.team_b_combo, 1)
        team_layout.addLayout(team_b_layout)

        layout.addWidget(team_group)

        # Output folder selection group
        folder_group = QGroupBox("Carpeta de Destino")
        folder_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        folder_layout = QVBoxLayout(folder_group)

        folder_select_layout = QHBoxLayout()
        folder_label = QLabel("Carpeta:")
        folder_label.setMinimumWidth(150)
        self.folder_line = QLineEdit()
        self.folder_line.setPlaceholderText("Seleccione una carpeta...")
        self.folder_line.setReadOnly(True)
        self.browse_button = QPushButton("📁 Examinar...")
        self.browse_button.clicked.connect(self._browse_folder)
        folder_select_layout.addWidget(folder_label)
        folder_select_layout.addWidget(self.folder_line, 1)
        folder_select_layout.addWidget(self.browse_button)
        folder_layout.addLayout(folder_select_layout)

        # Info label
        info_label = QLabel(
            "Los informes se guardarán en subcarpetas organizadas por equipo y tipo."
        )
        info_label.setStyleSheet("color: gray; font-size: 9pt; font-style: italic;")
        info_label.setWordWrap(True)
        folder_layout.addWidget(info_label)

        layout.addWidget(folder_group)

        # Spacer
        layout.addStretch()

        # Report content info
        content_group = QGroupBox("Contenido del Informe")
        content_group.setStyleSheet("QGroupBox { font-weight: bold; }")
        content_layout = QVBoxLayout(content_group)

        content_text = QLabel(
            "El informe incluirá:\n\n"
            "📊 Estadísticas Básicas:\n"
            "  • Toda la competición\n"
            "  • Partidos ganados vs perdidos\n"
            "  • Local vs Visitante\n"
            "  • Último mes\n"
            "  • Último partido de cada equipo\n\n"
            "👥 Estadísticas Individuales:\n"
            "  • Por jugadora para ambos equipos\n\n"
            "🎯 Gráficos de Lanzamiento:\n"
            "  • Mapas de calor de equipo\n"
            "  • Zonas de tiro de equipo\n"
            "  • Mapas de calor por jugadora\n"
            "  • Zonas de tiro por jugadora"
        )
        content_text.setStyleSheet("font-size: 9pt;")
        content_text.setWordWrap(True)
        content_layout.addWidget(content_text)

        layout.addWidget(content_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.generate_button = QPushButton("✅ Generar Informe")
        self.generate_button.clicked.connect(self._on_generate)
        self.generate_button.setEnabled(False)
        self.generate_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border-radius: 5px;
                padding: 10px 20px;
                font-weight: bold;
                font-size: 11pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
                color: #757575;
            }
        """)

        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)
        cancel_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                font-size: 11pt;
            }
        """)

        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(self.generate_button)

        layout.addLayout(button_layout)

    def _browse_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta de Destino",
            "",
            QFileDialog.Option.ShowDirsOnly | QFileDialog.Option.DontResolveSymlinks
        )

        if folder:
            self.folder_line.setText(folder)
            self.output_folder = folder
            self._validate_selection()

    def _validate_selection(self):
        """Validate all selections and enable/disable generate button."""
        team_a = self.team_a_combo.currentData()
        team_b = self.team_b_combo.currentData()
        folder = self.output_folder

        # Check if all fields are filled (convert explicitly to bool)
        all_filled = bool(team_a and team_b and folder)

        # Check if teams are different (convert explicitly to bool)
        teams_different = bool(team_a != team_b if (team_a and team_b) else True)

        # Enable button only if all conditions met
        self.generate_button.setEnabled(all_filled and teams_different)

        # Show warning if same team selected
        if team_a and team_b and team_a == team_b:
            self.generate_button.setToolTip("⚠️ Los equipos A y B deben ser diferentes")
        else:
            self.generate_button.setToolTip("")

    def _on_generate(self):
        """Handle generate button click."""
        self.selected_team_a = self.team_a_combo.currentData()
        self.selected_team_b = self.team_b_combo.currentData()

        # Final validation
        if not self.selected_team_a or not self.selected_team_b:
            QMessageBox.warning(
                self,
                "Selección incompleta",
                "Por favor, seleccione ambos equipos."
            )
            return

        if self.selected_team_a == self.selected_team_b:
            QMessageBox.warning(
                self,
                "Equipos idénticos",
                "Los equipos A y B deben ser diferentes."
            )
            return

        if not self.output_folder:
            QMessageBox.warning(
                self,
                "Carpeta no seleccionada",
                "Por favor, seleccione una carpeta de destino."
            )
            return

        # Accept dialog
        super().accept()

    def get_configuration(self) -> Optional[Dict[str, str]]:
        """
        Get the report configuration.

        Returns:
            Dictionary with team_a, team_b, and output_folder keys, or None if canceled
        """
        if self.selected_team_a and self.selected_team_b and self.output_folder:
            return {
                'team_a': self.selected_team_a,
                'team_b': self.selected_team_b,
                'output_folder': self.output_folder
            }
        return None
