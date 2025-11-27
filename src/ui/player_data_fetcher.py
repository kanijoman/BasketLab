"""
Player Data Fetcher - Fetch player information from external sources.

This module handles fetching player data such as photos, birth information,
and dorsals from the database and external websites.
"""

import os
import tempfile
import requests
from typing import Optional, Any
from bs4 import BeautifulSoup
from datetime import datetime
from PIL import Image


class PlayerDataFetcher:
    """Fetch and manage player data from various sources."""

    def __init__(self, db_handler: Optional[Any] = None, collection_name: Optional[str] = None):
        """
        Initialize player data fetcher.

        Args:
            db_handler: Database handler for fetching data
            collection_name: MongoDB collection name
        """
        self.db_handler = db_handler
        self.collection_name = collection_name
        self.photo_cache = {}  # Cache of downloaded photos

    def get_player_dorsal_and_photo(self, player_id: str) -> tuple[str, Optional[str], Optional[str]]:
        """
        Get player's dorsal, photo URL and team_id from their last match.

        Args:
            player_id: Player ID

        Returns:
            Tuple (dorsal, photo_url, team_id). Dorsal as string, photo_url and team_id can be None
        """
        if not self.db_handler or not player_id:
            return "", None, None

        try:
            # Get collection
            collection = None
            if not self.collection_name:
                return "", None, None

            try:
                if hasattr(self.db_handler, 'connection'):
                    collection = self.db_handler.connection.get_collection(self.collection_name)
                elif hasattr(self.db_handler, 'db'):
                    collection = self.db_handler.db[self.collection_name]
            except Exception as e:
                return "", None, None

            if collection is None:
                return "", None, None

            # Find last match with this player (sorted by date descending)
            matches = collection.find(
                {"BOXSCORE.TEAM.PLAYER.id": player_id}
            ).sort("_id", -1).limit(1)

            match = None
            for m in matches:
                match = m
                break

            if not match:
                return "", None, None

            # Search for player data in the match
            for team in match.get('BOXSCORE', {}).get('TEAM', []):
                for player in team.get('PLAYER', []):
                    if player.get('id') == player_id:
                        dorsal = player.get('no', '')
                        photo_url = player.get('logo', '')
                        team_id = team.get('id', '')

                        if photo_url and photo_url.startswith('http'):
                            return dorsal, photo_url, team_id
                        else:
                            return dorsal, None, team_id

            return "", None, None

        except Exception as e:
            import traceback
            traceback.print_exc()
            return "", None, None

    def get_player_birth_info(self, player_id: str, team_id: Optional[str]) -> tuple[Optional[str], Optional[int], Optional[str]]:
        """
        Get player's birth date, age and height from FEB website.

        Args:
            player_id: Player ID
            team_id: Team ID

        Returns:
            Tuple (birth_date, age, height). birth_date as string (format DD/MM/YYYY),
            age as int (years), height as string (format "XXX cm")
        """
        if not player_id or not team_id:
            return None, None, None

        try:
            url = f"https://baloncestoenvivo.feb.es/jugador/{team_id}/{player_id}"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Search for birth date and height on the page
            birth_date = None
            age = None
            height = None

            # Search in divs or spans with player data related classes
            info_sections = soup.find_all(['div', 'span', 'p'], class_=lambda x: x and ('dato' in x.lower() or 'info' in x.lower() or 'fecha' in x.lower()))

            for section in info_sections:
                text = section.get_text(strip=True)

                # Search for date pattern DD/MM/YYYY or DD-MM-YYYY
                import re
                date_match = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', text)
                if date_match and not birth_date:
                    day, month, year = date_match.groups()
                    birth_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"

                    # Calculate age
                    try:
                        birth_datetime = datetime.strptime(birth_date, "%d/%m/%Y")
                        today = datetime.now()
                        age = today.year - birth_datetime.year - ((today.month, today.day) < (birth_datetime.month, birth_datetime.day))
                    except:
                        pass

                # Search for height pattern XXX cm
                height_match = re.search(r'(\d{2,3})\s*cm', text, re.IGNORECASE)
                if height_match and not height:
                    height = f"{height_match.group(1)} cm"

            # If not found in specific sections, search in all text
            if not birth_date or not height:
                page_text = soup.get_text()
                import re

                if not birth_date:
                    # Search for pattern with "nacimiento" or "fecha" near a date
                    date_pattern = re.search(r'(?:nacimiento|fecha)[:\s]*(\d{1,2})[/-](\d{1,2})[/-](\d{4})', page_text, re.IGNORECASE)
                    if date_pattern:
                        day, month, year = date_pattern.groups()
                        birth_date = f"{day.zfill(2)}/{month.zfill(2)}/{year}"

                        try:
                            birth_datetime = datetime.strptime(birth_date, "%d/%m/%Y")
                            today = datetime.now()
                            age = today.year - birth_datetime.year - ((today.month, today.day) < (birth_datetime.month, birth_datetime.day))
                        except:
                            pass

                if not height:
                    # Search for height pattern in full text
                    height_pattern = re.search(r'(?:altura|height)[:\s]*(\d{2,3})\s*cm', page_text, re.IGNORECASE)
                    if height_pattern:
                        height = f"{height_pattern.group(1)} cm"

            return birth_date, age, height

        except requests.exceptions.RequestException as e:
            return None, None, None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None, None, None

    def download_photo_from_url(self, photo_url: str, player_id: str) -> Optional[str]:
        """
        Download photo from URL.

        Args:
            photo_url: Photo URL
            player_id: Player ID (for caching)

        Returns:
            Path to temporary file with photo, or None if download failed
        """
        # Check if already cached
        if player_id in self.photo_cache:
            cached_path = self.photo_cache[player_id]
            if os.path.exists(cached_path):
                return cached_path

        try:
            # Download image
            response = requests.get(photo_url, timeout=10)
            if response.status_code != 200:
                return None

            # Save to temporary file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.jpg')
            temp_file.write(response.content)
            temp_file.close()

            # Process image to optimize size
            try:
                with Image.open(temp_file.name) as img:
                    # Convert to RGB if necessary
                    if img.mode in ('RGBA', 'LA', 'P'):
                        img = img.convert('RGB')

                    # Resize if too large
                    max_size = (400, 400)
                    img.thumbnail(max_size, Image.Resampling.LANCZOS)

                    # Save optimized
                    img.save(temp_file.name, 'JPEG', quality=85)

            except Exception as e:
                # Continue anyway, original image might work
                pass

            # Save to cache
            self.photo_cache[player_id] = temp_file.name

            return temp_file.name

        except requests.RequestException as e:
            return None
        except Exception as e:
            import traceback
            traceback.print_exc()
            return None

    def cleanup_photo_cache(self):
        """Clean up temporary downloaded photos."""
        for player_id, photo_path in self.photo_cache.items():
            try:
                if photo_path and os.path.exists(photo_path):
                    os.unlink(photo_path)
            except Exception as e:
                pass

        self.photo_cache.clear()
