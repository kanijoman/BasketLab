"""Constants for FEB web scraping."""

# Base URLs
BASE_URL = "https://baloncestoenvivo.feb.es/calendario/lf2/9/{year}"
MATCH_PAGE_URL = "https://baloncestoenvivo.feb.es/partido/{match_code}"

# API URLs
BOXSCORE_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/BoxScore/{match_code}"
SHOTCHART_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/ShotChart/{match_code}"
KEYFACTS_API_URL = "https://intrafeb.feb.es/LiveStats.API/api/v1/KeyFacts/{match_code}"

# Form field IDs
SEASON_DROPDOWN_ID = "_ctl0_MainContentPlaceHolderMaster_temporadasDropDownList"
GROUP_DROPDOWN_ID = "_ctl0_MainContentPlaceHolderMaster_gruposDropDownList"

# Hidden form fields
HIDDEN_FIELDS = ["__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION", "__PREVIOUSPAGE"]

# HTTP Headers
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/140.0.0.0",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://baloncestoenvivo.feb.es/"
}

HTML_HEADERS = DEFAULT_HEADERS | {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

# Timeout settings
DEFAULT_TIMEOUT = 10
EXTENDED_TIMEOUT = 15

# Token cache settings
TOKEN_CACHE_HOURS = 24
