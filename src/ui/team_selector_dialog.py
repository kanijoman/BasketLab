"""Dialog for selecting a team from the competition."""

from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                              QPushButton, QLabel, QLineEdit, QListWidgetItem)
from PyQt6.QtCore import Qt
from typing import List, Optional


class TeamSelectorDialog(QDialog):
    """Dialog to select a team from a list."""

    def __init__(self, teams: List[str], parent=None):
        """
        Initialize team selector dialog.

        Args:
            teams: List of team names
            parent: Parent widget
        """
        super().__init__(parent)
        self.selected_team: Optional[str] = None
        self.teams = teams

        self.setWindowTitle("Seleccionar Equipo")
        self.setMinimumSize(400, 500)
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Seleccione un equipo para ver su último partido:")
        title_label.setStyleSheet("font-size: 12pt; font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Search box
        search_layout = QHBoxLayout()
        search_label = QLabel("Buscar:")
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Escriba para filtrar equipos...")
        self.search_box.textChanged.connect(self._filter_teams)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)

        # Team list
        self.team_list = QListWidget()
        self.team_list.itemDoubleClicked.connect(self._on_team_double_clicked)
        layout.addWidget(self.team_list)

        # Populate team list
        for team in self.teams:
            item = QListWidgetItem(team)
            self.team_list.addItem(item)

        # Buttons
        button_layout = QHBoxLayout()

        self.select_button = QPushButton("Seleccionar")
        self.select_button.clicked.connect(self.accept)
        self.select_button.setDefault(True)

        cancel_button = QPushButton("Cancelar")
        cancel_button.clicked.connect(self.reject)

        button_layout.addStretch()
        button_layout.addWidget(self.select_button)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # Info label
        info_label = QLabel(f"Total de equipos: {len(self.teams)}")
        info_label.setStyleSheet("color: gray; font-size: 9pt; margin-top: 5px;")
        layout.addWidget(info_label)

    def _filter_teams(self, text: str):
        """Filter team list based on search text."""
        search_text = text.lower()
        for i in range(self.team_list.count()):
            item = self.team_list.item(i)
            team_name = item.text().lower()
            item.setHidden(search_text not in team_name)

    def _on_team_double_clicked(self, item: QListWidgetItem):
        """Handle double click on team item."""
        self.accept()

    def accept(self):
        """Accept dialog and store selected team."""
        selected_items = self.team_list.selectedItems()
        if selected_items:
            self.selected_team = selected_items[0].text()
            super().accept()

    def get_selected_team(self) -> Optional[str]:
        """
        Get the selected team name.

        Returns:
            Selected team name or None if canceled
        """
        return self.selected_team
