"""
AI Analysis Window - UI for generating team analysis reports.
"""

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                              QPushButton, QTextEdit, QLabel, QComboBox,
                              QMessageBox, QLineEdit, QDialog, QDialogButtonBox,
                              QCheckBox, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from typing import Dict, Optional
import matplotlib.pyplot as plt
from io import BytesIO
import re
import os

from ai import TeamAnalyzer, AnalysisConfig
from .pdf_generator import PDFGenerator
from .ui_utils import set_app_icon

class AnalysisWorker(QThread):
    """Worker thread for generating analysis without freezing UI."""

    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, analyzer: TeamAnalyzer, team_name: str, stats: Dict,
                 image: Optional[bytes] = None, include_recommendations: bool = True,
                 analysis_type: str = 'own'):
        super().__init__()
        self.analyzer = analyzer
        self.team_name = team_name
        self.stats = stats
        self.image = image
        self.include_recommendations = include_recommendations
        self.analysis_type = analysis_type

    def run(self):
        """Run analysis in background thread."""
        try:
            result = self.analyzer.analyze_team_performance(
                team_name=self.team_name,
                stats=self.stats,
                shot_chart_image=self.image,
                include_recommendations=self.include_recommendations,
                analysis_type=self.analysis_type
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class ApiKeyDialog(QDialog):
    """Dialog for configuring API keys."""

    def __init__(self, provider: str = 'groq', parent=None):
        super().__init__(parent)
        self.provider = provider
        self.setup_ui()

    def setup_ui(self):
        """Setup dialog UI."""
        self.setWindowTitle(f"MfA - Configurar API Key de {self.provider.capitalize()}")
        self.setModal(True)

        # Set application icon
        set_app_icon(self)

        layout = QVBoxLayout()

        # Instructions
        if self.provider == 'groq':
            instructions = (
                "Para obtener una API key gratuita de Groq:\n"
                "1. Visita: https://console.groq.com/keys\n"
                "2. Crea una cuenta o inicia sesión\n"
                "3. Haz clic en 'Create API Key'\n"
                "4. Copia y pega la clave abajo\n\n"
                "Tier gratuito: Muy generoso con límites altos"
            )
        elif self.provider == 'gemini':
            instructions = (
                "To get a free Google Gemini API key:\n"
                "1. Visit: https://makersuite.google.com/app/apikey\n"
                "2. Click 'Create API Key'\n"
                "3. Copy and paste the key below\n\n"
                "Free tier: 1,500 requests/day"
            )
        else:
            instructions = (
                "To get an OpenAI API key:\n"
                "1. Visit: https://platform.openai.com/api-keys\n"
                "2. Click 'Create new secret key'\n"
                "3. Copy and paste the key below\n\n"
                "New accounts get $5 free credit"
            )

        label = QLabel(instructions)
        label.setWordWrap(True)
        layout.addWidget(label)

        # API key input
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText(f"Paste your {self.provider.capitalize()} API key here")
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("API Key:"))
        layout.addWidget(self.api_key_input)

        # Show/hide key checkbox
        self.show_key_checkbox = QCheckBox("Show API key")
        self.show_key_checkbox.stateChanged.connect(self.toggle_key_visibility)
        layout.addWidget(self.show_key_checkbox)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def toggle_key_visibility(self, state):
        """Toggle API key visibility."""
        if state == Qt.CheckState.Checked.value:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)

    def get_api_key(self) -> str:
        """Get the entered API key."""
        return self.api_key_input.text().strip()


class AIAnalysisWindow(QMainWindow):
    """Window for AI-powered team analysis."""

    def __init__(self, team_name: str, stats: Dict, shot_chart_figure: Optional[plt.Figure] = None,
                 analysis_type: str = 'own', parent=None):
        """
        Initialize AI analysis window.

        Args:
            team_name: Name of the team to analyze
            stats: Team statistics dictionary
            shot_chart_figure: Optional matplotlib figure with shot chart
            analysis_type: Type of analysis - 'own' (own team) or 'opponent' (rival team)
            parent: Parent widget
        """
        super().__init__(parent)
        self.team_name = team_name
        self.stats = stats
        self.shot_chart_figure = shot_chart_figure
        self.analysis_type = analysis_type
        self.analyzer: Optional[TeamAnalyzer] = None
        self.worker: Optional[AnalysisWorker] = None
        self.original_html: str = ""  # Store original HTML from AI

        self.setup_ui()
        self.apply_styles()

    def setup_ui(self):
        """Setup the user interface."""
        # More appropriate icons for each analysis type
        if self.analysis_type == 'opponent':
            window_prefix = "MfA - Scouting Rival"
            header_emoji = "⚔️"  # Swords = battle/competition
            header_prefix = "Análisis Rival"
        else:
            window_prefix = "MfA - Análisis Propio"
            header_emoji = "🏀"  # Basketball = own team
            header_prefix = "Análisis de Equipo"

        self.setWindowTitle(f"{window_prefix} - {self.team_name}")
        self.setMinimumSize(800, 600)

        # Set application icon
        set_app_icon(self)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Header
        header_label = QLabel(f"{header_emoji} {header_prefix}: {self.team_name}")
        header_font = QFont()
        header_font.setPointSize(14)
        header_font.setBold(True)
        header_label.setFont(header_font)
        layout.addWidget(header_label)

        # API Key configuration
        api_layout = QHBoxLayout()
        api_label = QLabel("🤖 Groq Llama 3.3 70B (Free & Fast)")
        api_label.setStyleSheet("font-weight: bold; color: #9C27B0;")
        api_layout.addWidget(api_label)

        api_layout.addStretch()

        # Configure API key button
        self.config_btn = QPushButton("⚙️ Configure API Key")
        self.config_btn.clicked.connect(self.configure_api_key)
        api_layout.addWidget(self.config_btn)

        layout.addLayout(api_layout)

        # Options
        options_layout = QHBoxLayout()
        self.include_image_checkbox = QCheckBox("Incluir imagen de gráfico de lanzamiento")
        self.include_image_checkbox.setChecked(self.shot_chart_figure is not None)
        self.include_image_checkbox.setEnabled(self.shot_chart_figure is not None)
        options_layout.addWidget(self.include_image_checkbox)

        self.include_recommendations_checkbox = QCheckBox("Include tactical recommendations")
        self.include_recommendations_checkbox.setChecked(True)
        options_layout.addWidget(self.include_recommendations_checkbox)

        options_layout.addStretch()
        layout.addLayout(options_layout)

        # Generate button
        self.generate_btn = QPushButton("🤖 Generar Análisis")
        self.generate_btn.clicked.connect(self.generate_analysis)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        layout.addWidget(self.generate_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)  # Indeterminate
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        # Report display
        layout.addWidget(QLabel("Informe de Análisis:"))

        self.report_text = QTextEdit()
        self.report_text.setReadOnly(True)
        self.report_text.setPlaceholderText(
            "Haga clic en 'Generar Análisis' para crear un análisis impulsado por IA.\n\n"
            "El análisis incluirá:\n"
            "• Fortalezas y debilidades de tiro\n"
            "• Análisis de selección de tiro\n"
            "• Rendimiento por zonas\n"
            "• Recomendaciones tácticas\n"
            "• Áreas de enfoque para entrenamientos"
        )
        layout.addWidget(self.report_text)

        # Export button
        export_layout = QHBoxLayout()
        export_layout.addStretch()

        self.export_btn = QPushButton("Exportar a PDF")
        self.export_btn.clicked.connect(self.export_report)
        self.export_btn.setEnabled(False)
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        export_layout.addWidget(self.export_btn)

        layout.addLayout(export_layout)

        # Check if API key is configured
        self.check_api_key_status()

    def apply_styles(self):
        """Apply window styles."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f5f5f5;
            }
            QLabel {
                color: #333;
            }
            QTextEdit {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 8px;
                background-color: white;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11pt;
            }
        """)

    def check_api_key_status(self):
        """Check if API key is configured and update UI."""
        provider = 'groq'
        has_key = AnalysisConfig.has_api_key(provider)

        if has_key:
            self.generate_btn.setEnabled(True)
            self.config_btn.setText("✓ API Key Configured")
            self.config_btn.setStyleSheet("background-color: #e8f5e9;")
        else:
            self.generate_btn.setEnabled(False)
            self.config_btn.setText("⚠️ Configure API Key Required")
            self.config_btn.setStyleSheet("background-color: #fff3cd;")

    def configure_api_key(self):
        """Show dialog to configure API key."""
        provider = 'groq'
        dialog = ApiKeyDialog(provider, self)

        if dialog.exec():
            api_key = dialog.get_api_key()
            if api_key:
                try:
                    AnalysisConfig.save_api_key(provider, api_key)
                    QMessageBox.information(
                        self,
                        "Success",
                        f"{provider.capitalize()} API key saved successfully!"
                    )
                    self.check_api_key_status()
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to save API key: {str(e)}"
                    )
            else:
                QMessageBox.warning(self, "Warning", "Please enter an API key")

    def generate_analysis(self):
        """Generate AI analysis report."""
        try:
            # Initialize analyzer - use Groq (fast and free)
            provider = 'groq'
            model = 'fast'

            self.analyzer = TeamAnalyzer(provider=provider, model=model)

            # Get shot chart image if requested
            shot_chart_bytes = None
            if self.include_image_checkbox.isChecked() and self.shot_chart_figure:
                buf = BytesIO()
                self.shot_chart_figure.savefig(buf, format='png', dpi=150, bbox_inches='tight')
                shot_chart_bytes = buf.getvalue()
                buf.close()

            # Disable button and show progress
            self.generate_btn.setEnabled(False)
            self.export_btn.setEnabled(False)  # Disable export while generating
            self.progress_bar.show()
            self.report_text.setText("Generating analysis... This may take 10-30 seconds.")

            # Run analysis in background thread
            self.worker = AnalysisWorker(
                analyzer=self.analyzer,
                team_name=self.team_name,
                stats=self.stats,
                image=shot_chart_bytes,
                include_recommendations=self.include_recommendations_checkbox.isChecked(),
                analysis_type=self.analysis_type
            )
            self.worker.finished.connect(self.on_analysis_finished)
            self.worker.error.connect(self.on_analysis_error)
            self.worker.start()

        except ValueError as e:
            QMessageBox.critical(self, "Configuration Error", str(e))
            self.generate_btn.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to initialize analyzer: {str(e)}")
            self.generate_btn.setEnabled(True)

    def on_analysis_finished(self, result: str):
        """Handle analysis completion."""
        self.progress_bar.hide()
        self.generate_btn.setEnabled(True)

        # Store the original HTML/content from AI
        self.original_html = result

        # Check if result is HTML (starts with < or contains HTML tags)
        if result.strip().startswith('<') or '<html>' in result.lower() or '<h1>' in result.lower():
            # It's HTML, set it as HTML
            self.report_text.setHtml(result)
        else:
            # It's markdown or plain text
            self.report_text.setMarkdown(result)

        self.export_btn.setEnabled(True)

    def on_analysis_error(self, error: str):
        """Handle analysis error."""
        self.progress_bar.hide()
        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(False)  # Disable export on error
        self.report_text.setText(f"Error generating analysis:\n\n{error}")
        QMessageBox.critical(self, "Analysis Error", error)

    def export_report(self):
        """Export report to PDF file."""
        from PyQt6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Informe de Análisis",
            f"{self.team_name}_analisis.pdf",
            "PDF Files (*.pdf);;All Files (*)"
        )

        if file_path:
            try:
                # Ensure file has .pdf extension
                if not file_path.lower().endswith('.pdf'):
                    file_path += '.pdf'

                self._generate_pdf(file_path)

                QMessageBox.information(
                    self,
                    "Éxito",
                    f"Informe exportado correctamente a:\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error de Exportación",
                    f"No se pudo exportar el informe: {str(e)}"
                )

    def _generate_pdf(self, file_path: str):
        """Generate PDF from HTML report."""
        try:
            # Use the original HTML from AI if available
            if self.original_html:
                report_html = self.original_html
            else:
                # Fallback: get from QTextEdit
                report_html = self.report_text.toHtml()

            # Clean up HTML if AI wrapped it in markdown code blocks
            if '```html' in report_html:
                report_html = report_html.replace('```html', '').replace('```', '').strip()
            elif report_html.startswith('```'):
                # Remove first and last ``` markers
                lines = report_html.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].startswith('```'):
                    lines = lines[:-1]
                report_html = '\n'.join(lines).strip()

            # Add team name to HTML if not present
            if '<h1>' not in report_html or 'Analisis de Equipo' in report_html[:200]:
                report_html = report_html.replace(
                    '<h1>Analisis de Equipo</h1>',
                    f'<h1>Análisis de Equipo: {self.team_name}</h1>'
                )

            # Use fpdf2 with HTML parsing (most reliable on Windows)
            self._generate_pdf_from_html_fallback(file_path, report_html)

        except Exception as e:
            raise

    def _generate_pdf_from_html_fallback(self, file_path: str, html_content: str):
        """Generate PDF from AI-generated HTML using PDFGenerator.

        This method converts HTML analysis reports to PDF format using the
        PDFGenerator module that extracts and formats text content while preserving
        document structure. It handles Spanish text, special characters, and
        includes optional shot chart visualization.

        The generated PDF includes:
        - Title page with team name and season
        - Formatted analysis sections (headings, paragraphs, lists)
        - Optional shot chart visualization on a separate page

        Args:
            file_path: Absolute path where PDF should be saved
            html_content: HTML string containing the analysis report

        Raises:
            Exception: If PDF generation fails (file access, parsing errors, etc.)

        Note:
            Uses PDFGenerator module for consistent PDF generation across the application.
        """
        # Generate PDF using the centralized PDFGenerator
        PDFGenerator.generate_from_html(
            file_path=file_path,
            html_content=html_content,
            shot_chart_figure=self.shot_chart_figure
        )
