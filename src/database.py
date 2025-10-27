import pymongo
from pymongo.errors import ConnectionFailure, PyMongoError
from typing import Optional, Dict, List
import re

class MongoDBHandler:
    """A class to handle MongoDB operations for basketball data."""

    def __init__(self, connection_string: str = "mongodb+srv://kanijoman:S0p0rt3s@mycluster.g3slkjv.mongodb.net/"):
        """Initialize MongoDB client."""
        try:
            self.client = pymongo.MongoClient(connection_string)
            self.client.server_info()  # Test connection
            self.db = self.client["FEB"]
        except ConnectionFailure as e:
            print(f"[MongoDBHandler] Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None

    def is_connected(self) -> bool:
        """Check if MongoDB client is connected."""
        return self.client is not None and self.db is not None

    def document_exists(self, collection_name: str, match_code: int) -> bool:
        """Check if a document with the given match_code exists in the collection."""
        if not self.is_connected():
            print(f"[MongoDBHandler] No connection to MongoDB")
            return False
        try:
            collection = self.db[collection_name]
            return collection.find_one({"_id": match_code}) is not None
        except PyMongoError as e:
            print(f"[MongoDBHandler] Error checking document existence for match {match_code}: {e}")
            return False

    def insert_boxscore(self, collection_name: str, match_code: str, boxscore: Dict) -> bool:
        """Insert a boxscore document into the specified collection."""
        if not self.is_connected():
            print(f"[MongoDBHandler] No connection to MongoDB")
            return False
        try:
            collection = self.db[collection_name]
            boxscore["_id"] = int(match_code)
            collection.insert_one(boxscore)
            return True
        except PyMongoError as e:
            print(f"[MongoDBHandler] Failed to save match {match_code} to MongoDB: {e}")
            return False

    def get_team_stats(self, collection_name: str) -> List[Dict]:
        """Get aggregated team statistics from all matches in the collection.

        Returns a list of dictionaries containing each team's season statistics including:
        - Total games played (home and away)
        - Total points scored and received
        - Field goal statistics (2PT, 3PT, FT)
        - Rebounds, assists, steals, etc.
        - Win/Loss record
        """
        if not self.is_connected():
            print("[MongoDBHandler] No connection to MongoDB")
            return []

        try:
            collection = self.db[collection_name]

            pipeline = [
                # Phase 1: Prepare data before unwind
                {"$addFields": {
                    "localPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
                    "awayPoints": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}}
                }},

                # Phase 2: Get one document per team with its index
                {"$unwind": {
                    "path": "$BOXSCORE.TEAM",
                    "includeArrayIndex": "teamIndex"
                }},

                # Phase 3: Project required fields
                {"$project": {
                    "team_id": "$BOXSCORE.TEAM.id",
                    "team_name": "$BOXSCORE.TEAM.name",
                    "points": {"$toInt": "$BOXSCORE.TEAM.TOTAL.pts"},
                    "opponent_points": {
                        "$cond": {
                            "if": {"$eq": ["$teamIndex", 0]},
                            "then": "$awayPoints",
                            "else": "$localPoints"
                        }
                    },
                    "fg2_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2m"},
                    "fg2_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p2a"},
                    "fg3_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3m"},
                    "fg3_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p3a"},
                    "ft_made": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1m"},
                    "ft_attempts": {"$toInt": "$BOXSCORE.TEAM.TOTAL.p1a"},
                    "def_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.rd"},
                    "off_rebounds": {"$toInt": "$BOXSCORE.TEAM.TOTAL.ro"},
                    "assists": {"$toInt": "$BOXSCORE.TEAM.TOTAL.assist"},
                    "steals": {"$toInt": "$BOXSCORE.TEAM.TOTAL.st"},
                    "turnovers": {"$toInt": "$BOXSCORE.TEAM.TOTAL.to"},
                    "blocks": {"$toInt": "$BOXSCORE.TEAM.TOTAL.bs"},
                    "match_id": "$_id",
                    "is_local": {"$eq": ["$teamIndex", 0]}
                }},

                # Phase 3: Group by team
                {"$group": {
                    "_id": "$team_id",
                    "team_name": {"$first": "$team_name"},
                    "total_games": {"$sum": 1},
                    "games_home": {"$sum": {"$cond": ["$is_local", 1, 0]}},
                    "games_away": {"$sum": {"$cond": ["$is_local", 0, 1]}},
                    "points_scored": {"$sum": "$points"},
                    "points_received": {"$sum": "$opponent_points"},
                    "fg2_made": {"$sum": "$fg2_made"},
                    "fg2_attempted": {"$sum": "$fg2_attempts"},
                    "fg3_made": {"$sum": "$fg3_made"},
                    "fg3_attempted": {"$sum": "$fg3_attempts"},
                    "ft_made": {"$sum": "$ft_made"},
                    "ft_attempted": {"$sum": "$ft_attempts"},
                    "rebounds_def": {"$sum": "$def_rebounds"},
                    "rebounds_off": {"$sum": "$off_rebounds"},
                    "assists": {"$sum": "$assists"},
                    "steals": {"$sum": "$steals"},
                    "turnovers": {"$sum": "$turnovers"},
                    "blocks": {"$sum": "$blocks"},
                    "match_list": {"$push": "$match_id"}
                }},

                # Phase 4: Calculate additional statistics
                {"$addFields": {
                    "total_rebounds": {"$add": ["$rebounds_def", "$rebounds_off"]},
                    "points_per_game": {"$divide": ["$points_scored", "$total_games"]},
                    "points_against_per_game": {"$divide": ["$points_received", "$total_games"]},
                    "fg2_percentage": {
                        "$multiply": [
                            {"$cond": [
                                {"$eq": ["$fg2_attempted", 0]},
                                0,
                                {"$divide": ["$fg2_made", "$fg2_attempted"]}
                            ]},
                            100
                        ]
                    },
                    "fg3_percentage": {
                        "$multiply": [
                            {"$cond": [
                                {"$eq": ["$fg3_attempted", 0]},
                                0,
                                {"$divide": ["$fg3_made", "$fg3_attempted"]}
                            ]},
                            100
                        ]
                    },
                    "ft_percentage": {
                        "$multiply": [
                            {"$cond": [
                                {"$eq": ["$ft_attempted", 0]},
                                0,
                                {"$divide": ["$ft_made", "$ft_attempted"]}
                            ]},
                            100
                        ]
                    }
                }},

                # Phase 5: Sort by points per game
                {"$sort": {"points_per_game": -1}}
            ]

            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[MongoDBHandler] Error getting team stats: {e}")
            return []

    @staticmethod
    def get_collection_name(competition: str, season: str, group: str) -> str:
        """Generate collection name in the format {competicion}_{temporada}_{Grupo}.

        Removes or replaces invalid MongoDB characters and whitespace:
        - Replaces spaces, tabs, newlines with underscores
        - Removes $ and other special MongoDB characters
        - Ensures name doesn't start with 'system.' or contain null character
        """
        # First, replace all whitespace characters with underscore
        safe_competition = re.sub(r'\s+', '_', competition.strip())
        safe_season = re.sub(r'\s+', '_', season.strip())
        safe_group = re.sub(r'\s+', '_', group.strip())

        # Replace invalid MongoDB characters and common problematic characters
        pattern = r'[\\/:*?"<>|.$\x00-\x1F\x7F]'
        safe_competition = re.sub(pattern, '_', safe_competition)
        safe_season = re.sub(pattern, '_', safe_season)
        safe_group = re.sub(pattern, '_', safe_group)

        # Collapse multiple underscores into one
        safe_competition = re.sub(r'_+', '_', safe_competition)
        safe_season = re.sub(r'_+', '_', safe_season)
        safe_group = re.sub(r'_+', '_', safe_group)

        # Remove leading/trailing underscores
        safe_competition = safe_competition.strip('_')
        safe_season = safe_season.strip('_')
        safe_group = safe_group.strip('_')

        collection_name = f"{safe_competition}_{safe_season}_{safe_group}"

        # Ensure the name doesn't start with 'system.'
        if collection_name.lower().startswith('system.'):
            collection_name = 'col_' + collection_name

        return collection_name