import sys
import os

# Ensure project root is in sys.path so both 'from src.X' and bare 'from X'
# imports work regardless of how the script is launched.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from scraper import FEBWebScraper
from database import MongoDBHandler
from ui import BasketballSeasonApp


def _fix_app_font(app: QApplication) -> None:
    """Ensure the application font has a valid point size.

    On Windows with certain DPI configurations the default system font is
    defined in pixels, making QFont.pointSize() return -1.  Qt's stylesheet
    engine later tries to propagate that -1 value and emits the warning:
        QFont::setPointSize: Point size <= 0 (-1), must be greater than 0
    Setting an explicit point size on the QApplication font at startup
    prevents the warning without changing the visual appearance.
    """
    font = app.font()
    if font.pointSize() <= 0:
        font.setPointSize(10)
        app.setFont(font)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    _fix_app_font(app)
    scraper = FEBWebScraper()
    db_handler = MongoDBHandler()
    window = BasketballSeasonApp(scraper, db_handler)
    window.show()
    sys.exit(app.exec())