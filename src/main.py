import sys
import os

# Ensure project root is in sys.path so both 'from src.X' and bare 'from X'
# imports work regardless of how the script is launched.
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from PyQt6.QtWidgets import QApplication
from scraper import FEBWebScraper
from database import MongoDBHandler
from ui import BasketballSeasonApp

if __name__ == "__main__":
    app = QApplication(sys.argv)
    scraper = FEBWebScraper()
    db_handler = MongoDBHandler()
    window = BasketballSeasonApp(scraper, db_handler)
    window.show()
    sys.exit(app.exec())