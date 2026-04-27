"""Player Data Fetcher — fetch player info from database and external sources.

Moved from src/ui/player_data_fetcher.py (Qt UI layer removed).
Used by individual_scouting_service.py for photo/bio data.
"""

import os
import re
import tempfile
import requests
from typing import Optional, Any
from bs4 import BeautifulSoup
from datetime import datetime
from PIL import Image


class PlayerDataFetcher:
    """Fetch and manage player data from various sources."""

    def __init__(
        self,
        db_handler: Optional[Any] = None,
        collection_name: Optional[str] = None,
    ):
        self.db_handler = db_handler
        self.collection_name = collection_name
        self.photo_cache: dict = {}

    def get_player_dorsal_and_photo(
        self, player_id: str
    ) -> "tuple[str, Optional[str], Optional[str]]":
        """Get player's dorsal, photo URL and team_id from their last match.

        Returns:
            Tuple (dorsal, photo_url, team_id). photo_url and team_id can be None.
        """
        if not self.db_handler or not player_id or not self.collection_name:
            return "", None, None

        try:
            collection = None
            try:
                if hasattr(self.db_handler, "connection"):
                    collection = self.db_handler.connection.get_collection(
                        self.collection_name
                    )
                elif hasattr(self.db_handler, "db"):
                    collection = self.db_handler.db[self.collection_name]
            except Exception:
                return "", None, None

            if collection is None:
                return "", None, None

            matches = (
                collection.find({"BOXSCORE.TEAM.PLAYER.id": player_id})
                .sort("_id", -1)
                .limit(1)
            )
            match = next(iter(matches), None)
            if not match:
                return "", None, None

            for team in match.get("BOXSCORE", {}).get("TEAM", []):
                for player in team.get("PLAYER", []):
                    if player.get("id") == player_id:
                        dorsal = player.get("no", "")
                        photo_url = player.get("logo", "")
                        team_id = team.get("id", "")
                        if photo_url and photo_url.startswith("http"):
                            return dorsal, photo_url, team_id
                        return dorsal, None, team_id

            return "", None, None

        except Exception:
            return "", None, None

    def get_player_birth_info(
        self, player_id: str, team_id: Optional[str]
    ) -> "tuple[Optional[str], Optional[int], Optional[str]]":
        """Get player's birth date, age and height from FEB website.

        Returns:
            Tuple (birth_date, age, height). All values can be None.
        """
        if not player_id or not team_id:
            return None, None, None

        try:
            url = f"https://baloncestoenvivo.feb.es/jugador/{team_id}/{player_id}"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                )
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            birth_date = None
            age = None
            height = None

            info_sections = soup.find_all(
                ["div", "span", "p"],
                class_=lambda x: x
                and (
                    "dato" in x.lower()
                    or "info" in x.lower()
                    or "fecha" in x.lower()
                ),
            )

            for section in info_sections:
                text = section.get_text(strip=True)
                date_match = re.search(
                    r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", text
                )
                if date_match and not birth_date:
                    day, month, year = date_match.groups()
                    birth_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
                    try:
                        bd = datetime.strptime(birth_date, "%d/%m/%Y")
                        today = datetime.now()
                        age = today.year - bd.year - (
                            (today.month, today.day) < (bd.month, bd.day)
                        )
                    except Exception:
                        pass

                height_match = re.search(r"(\d{2,3})\s*cm", text, re.IGNORECASE)
                if height_match and not height:
                    height = f"{height_match.group(1)} cm"

            if not birth_date or not height:
                page_text = soup.get_text()
                if not birth_date:
                    date_pattern = re.search(
                        r"(?:nacimiento|fecha)[:\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})",
                        page_text,
                        re.IGNORECASE,
                    )
                    if date_pattern:
                        day, month, year = date_pattern.groups()
                        birth_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"
                        try:
                            bd = datetime.strptime(birth_date, "%d/%m/%Y")
                            today = datetime.now()
                            age = today.year - bd.year - (
                                (today.month, today.day) < (bd.month, bd.day)
                            )
                        except Exception:
                            pass

                if not height:
                    height_pattern = re.search(
                        r"(?:altura|height)[:\s]*(\d{2,3})\s*cm",
                        page_text,
                        re.IGNORECASE,
                    )
                    if height_pattern:
                        height = f"{height_pattern.group(1)} cm"

            return birth_date, age, height

        except requests.exceptions.RequestException:
            return None, None, None
        except Exception:
            return None, None, None

    def download_photo_from_url(
        self, photo_url: str, player_id: str
    ) -> Optional[str]:
        """Download a player photo and return path to a temp file, or None."""
        if player_id in self.photo_cache:
            cached = self.photo_cache[player_id]
            if os.path.exists(cached):
                return cached

        try:
            response = requests.get(photo_url, timeout=10)
            if response.status_code != 200:
                return None

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
            tmp.write(response.content)
            tmp.close()

            try:
                with Image.open(tmp.name) as img:
                    if img.mode in ("RGBA", "LA", "P"):
                        img = img.convert("RGB")
                    img.thumbnail((400, 400), Image.Resampling.LANCZOS)
                    img.save(tmp.name, "JPEG", quality=85)
            except Exception:
                pass

            self.photo_cache[player_id] = tmp.name
            return tmp.name

        except requests.RequestException:
            return None
        except Exception:
            return None

    def cleanup_photo_cache(self) -> None:
        """Delete all temporary downloaded photos from the cache."""
        for photo_path in self.photo_cache.values():
            try:
                if photo_path and os.path.exists(photo_path):
                    os.unlink(photo_path)
            except Exception:
                pass
        self.photo_cache.clear()
