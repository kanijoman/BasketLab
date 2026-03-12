import sys
import os

# Ensure project root is in sys.path so both 'from src.X' and bare 'from X'
# imports work regardless of how the script is launched.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QtMsgType, qInstallMessageHandler
from scraper import FEBWebScraper
from database import MongoDBHandler
from ui import BasketballSeasonApp


def _qt_message_handler(msg_type, context, message):
    """Redirect Qt messages to Python; print traceback on font warnings."""
    import traceback
    if "setPointSize" in message or "Point size" in message:
        print(f"\n[Qt WARNING] {message}", flush=True)
        print("  Qt source:", context.file, "line", context.line, flush=True)
        traceback.print_stack()
    elif msg_type >= QtMsgType.QtWarningMsg:
        print(f"[Qt] {message}", flush=True)


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
    # AA_Use96Dpi must be set BEFORE QApplication is constructed.
    # In Qt 6 this ensures every pixel→point conversion during stylesheet
    # processing uses 96 DPI as the reference density, preventing the warning:
    #   QFont::setPointSize: Point size <= 0 (-1), must be greater than 0
    # which fires when the stylesheet engine tries to inherit/convert a
    # pixel-based system font whose point size is unresolved (-1).
    # Note: QT_FONT_DPI (Qt 5 env-var) has no effect in Qt 6.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_Use96Dpi)
    qInstallMessageHandler(_qt_message_handler)
    app = QApplication(sys.argv)
    _fix_app_font(app)
    scraper = FEBWebScraper()
    db_handler = MongoDBHandler()
    window = BasketballSeasonApp(scraper, db_handler)
    window.show()
    sys.exit(app.exec())