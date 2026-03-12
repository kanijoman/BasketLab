import sys
import os

# Ensure project root is in sys.path so both 'from src.X' and bare 'from X'
# imports work regardless of how the script is launched.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Tell Qt to use 96 DPI as the reference before it initialises its font
# subsystem.  On Windows with certain display scaling configurations Qt reads
# the system font as a *pixel-based* font (pointSize == -1).  Fixing the DPI
# hint here prevents the warning that would otherwise fire inside the
# QApplication constructor itself, before any Python-level fix can run:
#   QFont::setPointSize: Point size <= 0 (-1), must be greater than 0
os.environ.setdefault("QT_FONT_DPI", "96")

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from scraper import FEBWebScraper
from database import MongoDBHandler
from ui import BasketballSeasonApp


def _fix_app_font(app: QApplication) -> None:
    """Ensure the application font has a valid point size.

    Secondary safety net after the env-var fix above.  Calling
    setPointSize() on a QFont that was built with pixelSize does NOT clear
    the internal pixel flag – Qt keeps treating it as pixel-based.  We
    therefore create a *new* QFont using the family name + an explicit point
    size instead of mutating the existing object.
    """
    font = app.font()
    if font.pointSize() <= 0:
        family = font.family() or "Segoe UI"
        app.setFont(QFont(family, 10))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    _fix_app_font(app)
    scraper = FEBWebScraper()
    db_handler = MongoDBHandler()
    window = BasketballSeasonApp(scraper, db_handler)
    window.show()
    sys.exit(app.exec())