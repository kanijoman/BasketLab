import sys
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