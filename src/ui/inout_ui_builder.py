"""UI Builder for IN/OUT Analysis Window - Extracts UI construction logic."""

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox,
                              QLabel, QPushButton, QTableWidget, QHeaderView)


class InOutUIBuilder:
    """Helper class for building IN/OUT analysis UI components."""
    
    # UI Style constants
    BUTTON_STYLE_GREEN = """
        QPushButton {
            background-color: #4CAF50;
            color: white;
            border-radius: 5px;
            padding: 8px 15px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
    """
    
    BUTTON_STYLE_BLUE = """
        QPushButton {
            background-color: #2196F3;
            color: white;
            border-radius: 5px;
            padding: 8px 15px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #1976D2;
        }
    """
    
    INFO_BOX_STYLE = "background-color: #e3f2fd; padding: 10px; border-radius: 5px;"
    
    @staticmethod
    def create_combo_with_label(label_text: str, tooltip: str = "") -> tuple:
        """
        Create a label and combobox pair.
        
        Args:
            label_text: Text for the label
            tooltip: Optional tooltip for the combobox
            
        Returns:
            Tuple of (QLabel, QComboBox)
        """
        label = QLabel(label_text)
        label.setStyleSheet("font-weight: bold;")
        
        combo = QComboBox()
        combo.setMaxVisibleItems(20)
        if tooltip:
            combo.setToolTip(tooltip)
            
        return label, combo
    
    @staticmethod
    def create_result_table(column_count: int, headers: list) -> QTableWidget:
        """
        Create a standard result table with resize-to-contents behavior.
        
        Args:
            column_count: Number of columns
            headers: List of header labels
            
        Returns:
            Configured QTableWidget
        """
        table = QTableWidget()
        table.setColumnCount(column_count)
        table.setHorizontalHeaderLabels(headers)
        table.setSortingEnabled(False)
        
        header = table.horizontalHeader()
        for i in range(column_count):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            
        return table
    
    @staticmethod
    def create_inout_tab_ui(parent) -> tuple:
        """
        Create UI elements for traditional IN/OUT analysis tab.
        
        Args:
            parent: Parent window (must have _on_inout_calculate method)
            
        Returns:
            Tuple of (tab_widget, player_combo, calc_button, table, info_label)
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)
        
        # Player selector
        selector_layout = QHBoxLayout()
        player_label, player_combo = InOutUIBuilder.create_combo_with_label(
            "Jugador:", "Seleccione jugador para análisis IN/OUT"
        )
        selector_layout.addWidget(player_label)
        selector_layout.addWidget(player_combo)
        
        calc_button = QPushButton("Calcular IN/OUT")
        calc_button.setStyleSheet(InOutUIBuilder.BUTTON_STYLE_GREEN)
        calc_button.clicked.connect(parent._on_inout_calculate)
        selector_layout.addWidget(calc_button)
        
        export_button = QPushButton("📤 Exportar")
        export_button.setStyleSheet(InOutUIBuilder.BUTTON_STYLE_BLUE)
        export_button.setToolTip("Exportar tabla en CSV/PNG/PDF")
        selector_layout.addWidget(export_button)
        
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
        # Result table
        table = InOutUIBuilder.create_result_table(
            4, ["Estadística", "IN (Equipo)", "OUT (Equipo)", "Δ %"]
        )
        layout.addWidget(table)
        
        # Info label
        info_label = QLabel("")
        layout.addWidget(info_label)
        
        return tab, player_combo, calc_button, table, info_label, export_button
    
    @staticmethod
    def create_invin_tab_ui(parent) -> tuple:
        """
        Create UI elements for IN vs IN comparison tab.
        
        Args:
            parent: Parent window (must have _on_invin_calculate method)
            
        Returns:
            Tuple of (tab_widget, player1_combo, player2_combo, calc_button, 
                     table, info_label, export_button)
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)
        
        # Instructions
        instructions = QLabel(
            "Compara el rendimiento del equipo cuando cada uno de los dos jugadores está en cancha."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(InOutUIBuilder.INFO_BOX_STYLE)
        layout.addWidget(instructions)
        
        # Player selectors
        selector_layout = QHBoxLayout()
        
        player1_label, player1_combo = InOutUIBuilder.create_combo_with_label(
            "Jugador 1:", "Primer jugador para comparar"
        )
        selector_layout.addWidget(player1_label)
        selector_layout.addWidget(player1_combo)
        
        player2_label, player2_combo = InOutUIBuilder.create_combo_with_label(
            "Jugador 2:", "Segundo jugador para comparar"
        )
        selector_layout.addWidget(player2_label)
        selector_layout.addWidget(player2_combo)
        
        calc_button = QPushButton("Comparar")
        calc_button.setStyleSheet(InOutUIBuilder.BUTTON_STYLE_GREEN)
        calc_button.clicked.connect(parent._on_invin_calculate)
        selector_layout.addWidget(calc_button)
        
        export_button = QPushButton("📤 Exportar")
        export_button.setStyleSheet(InOutUIBuilder.BUTTON_STYLE_BLUE)
        export_button.setToolTip("Exportar tabla en CSV/PNG/PDF")
        selector_layout.addWidget(export_button)
        
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
        # Result table
        table = InOutUIBuilder.create_result_table(
            4, ["Estadística", "Jugador 1 IN", "Jugador 2 IN", "Δ %"]
        )
        layout.addWidget(table)
        
        # Info label
        info_label = QLabel("")
        layout.addWidget(info_label)
        
        return tab, player1_combo, player2_combo, calc_button, table, info_label, export_button
    
    @staticmethod
    def create_comparison_tab_ui(parent) -> tuple:
        """
        Create UI elements for teammate comparison tab.
        
        Args:
            parent: Parent window (must have _on_comparison_calculate method)
            
        Returns:
            Tuple of (tab_widget, main_combo, teammate_a_combo, teammate_b_combo,
                     calc_button, table, info_label, export_button)
        """
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(8)
        layout.setContentsMargins(6, 6, 6, 6)
        
        # Instructions
        instructions = QLabel(
            "Seleccione un jugador principal y dos compañeros para comparar "
            "el rendimiento del equipo cuando el jugador principal juega con cada uno de ellos."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(InOutUIBuilder.INFO_BOX_STYLE)
        layout.addWidget(instructions)
        
        # Player selectors
        selector_layout = QHBoxLayout()
        
        # Main player
        main_label, main_combo = InOutUIBuilder.create_combo_with_label(
            "Jugador Principal:", "Seleccione el jugador principal"
        )
        selector_layout.addWidget(main_label)
        selector_layout.addWidget(main_combo)
        
        # Teammate A
        a_label, a_combo = InOutUIBuilder.create_combo_with_label(
            "Compañero A:", "Seleccione el primer compañero"
        )
        selector_layout.addWidget(a_label)
        selector_layout.addWidget(a_combo)
        
        # Teammate B
        b_label, b_combo = InOutUIBuilder.create_combo_with_label(
            "Compañero B:", "Seleccione el segundo compañero"
        )
        selector_layout.addWidget(b_label)
        selector_layout.addWidget(b_combo)
        
        # Calculate button
        calc_button = QPushButton("Comparar")
        calc_button.setStyleSheet(InOutUIBuilder.BUTTON_STYLE_GREEN)
        calc_button.clicked.connect(parent._on_comparison_calculate)
        selector_layout.addWidget(calc_button)
        
        export_button = QPushButton("📤 Exportar")
        export_button.setStyleSheet(InOutUIBuilder.BUTTON_STYLE_BLUE)
        export_button.setToolTip("Exportar tabla en CSV/PNG/PDF")
        selector_layout.addWidget(export_button)
        
        selector_layout.addStretch()
        layout.addLayout(selector_layout)
        
        # Result table
        table = InOutUIBuilder.create_result_table(
            4, ["Estadística", "Con Compañero A", "Con Compañero B", "Δ %"]
        )
        layout.addWidget(table)
        
        # Info label
        info_label = QLabel("")
        layout.addWidget(info_label)
        
        return (tab, main_combo, a_combo, b_combo,
                calc_button, table, info_label, export_button)
