"""Repository for basketball data operations."""

from typing import Dict, List, Optional, FrozenSet
from pymongo.errors import PyMongoError

from .connection import MongoDBConnection
from .aggregation import AggregationPipelineBuilder
from .aggregation.fbcyl_pipeline import FBCYLPipelineBuilder

from src.utils.collection_utils import is_fbcyl as _is_fbcyl


class BasketballRepository:
    """Repository for basketball data CRUD operations."""

    def __init__(self, connection: MongoDBConnection):
        """
        Initialize repository with a MongoDB connection.

        Args:
            connection: MongoDBConnection instance
        """
        self.connection = connection

    def document_exists(self, collection_name: str, match_code) -> bool:
        """
        Check if a document with the given match_code exists in the collection.

        Args:
            collection_name: Name of the collection
            match_code: Match identifier (int for FEB, str UUID for FBCYL)

        Returns:
            True if document exists, False otherwise
        """
        if not self.connection.is_connected():
            return False

        try:
            collection = self.connection.get_collection(collection_name)
            # Convert to int if it's a numeric string, otherwise use as-is (UUID)
            doc_id = int(match_code) if isinstance(match_code, str) and match_code.isdigit() else match_code
            return collection.find_one({"_id": doc_id}) is not None
        except PyMongoError as e:
            return False

    def insert_boxscore(self, collection_name: str, match_code: str, boxscore: Dict) -> bool:
        """
        Insert a boxscore document if it doesn't already exist in the collection.

        Args:
            collection_name: Name of the collection
            match_code: Match identifier
            boxscore: Boxscore data dictionary

        Returns:
            True if successful, False otherwise
        """
        if not self.connection.is_connected():
            return False

        # Check if document already exists
        if self.document_exists(collection_name, int(match_code)):
            # Document exists, silently skip it
            return True

        try:
            collection = self.connection.get_collection(collection_name)
            boxscore["_id"] = int(match_code)
            collection.insert_one(boxscore)
            return True
        except PyMongoError as e:
            return False

    def insert_fbcyl_match(self, collection_name: str, match_uuid: str, match_data: Dict) -> bool:
        """
        Insert a FBCYL match document with complete data (moves + stats).

        Args:
            collection_name: Name of the collection
            match_uuid: Match UUID (24-character hex string)
            match_data: Dictionary with 'uuid', 'moves', and 'stats' keys

        Returns:
            True if successful, False otherwise
        """
        if not self.connection.is_connected():
            return False

        # Check if document already exists
        if self.document_exists(collection_name, match_uuid):
            return True

        try:
            collection = self.connection.get_collection(collection_name)
            # Use UUID as the document _id
            match_data["_id"] = match_uuid
            collection.insert_one(match_data)
            return True
        except PyMongoError as e:
            return False

    def get_team_stats(self, collection_name: str, date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Get aggregated team statistics from all matches in the collection.

        Returns a list of dictionaries containing each team's season statistics including:
        - Total games played (home and away)
        - Total points scored and received
        - Field goal statistics (2PT, 3PT, FT)
        - Rebounds, assists, steals, etc.
        - Advanced metrics (Four Factors, efficiency ratings, etc.)

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter (e.g., {"$gte": datetime(2024, 1, 1)})
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)

        Returns:
            List of team statistics dictionaries
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection by checking collection name or document structure
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                pipeline = FBCYLPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)
            else:
                pipeline = AggregationPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)

            result = list(collection.aggregate(pipeline))

            if not result and is_fbcyl:
                # Debug: Check if collection has data
                doc_count = collection.count_documents({})
                print(f"[Repository] FBCYL collection {collection_name} has {doc_count} documents")
                if doc_count > 0:
                    sample = collection.find_one()
                    print(f"[Repository] Sample document keys: {list(sample.keys()) if sample else 'None'}")
                    if sample and 'stats' in sample:
                        print(f"[Repository] Sample stats keys: {list(sample['stats'].keys())}")
                        if 'teams' in sample['stats']:
                            print(f"[Repository] Number of teams in sample: {len(sample['stats']['teams'])}")
                            if sample['stats']['teams']:
                                print(f"[Repository] First team keys: {list(sample['stats']['teams'][0].keys())}")

                    # Try a simple aggregation to see what's happening
                    print(f"[Repository] Testing simple aggregation...")
                    simple_result = list(collection.aggregate([
                        {"$limit": 1},
                        {"$project": {"teams": "$stats.teams"}}
                    ]))
                    print(f"[Repository] Simple aggregation result: {len(simple_result)} docs")

            return result
        except PyMongoError as e:
            print(f"[Repository] Error in get_team_stats: {e}")
            import traceback
            traceback.print_exc()
            return []
        except Exception as e:
            print(f"[Repository] Unexpected error in get_team_stats: {e}")
            import traceback
            traceback.print_exc()
            return []

    def get_opponent_stats(self, collection_name: str, date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Get aggregated opponent statistics grouped by team.

        This shows what each team's opponents have done against them across all matches.
        Useful for defensive analysis and understanding the strength of opposition faced.

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter (e.g., {"$gte": datetime(2024, 1, 1)})
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)

        Returns:
            List of opponent statistics dictionaries grouped by team
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                pipeline = FBCYLPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)
            else:
                pipeline = AggregationPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)

            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            return []

    def get_last_match(self, collection_name: str, team_name: str) -> Dict:
        """
        Get the last match document for a specific team.

        Args:
            collection_name: Name of the collection
            team_name: Name of the team to find

        Returns:
            Last match document or empty dict if not found
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL format: stats.teams[].name and stats.startDate
                pipeline = [
                    {
                        "$addFields": {
                            "parsedDate": {
                                "$dateFromString": {
                                    "dateString": "$stats.startDate",
                                    "format": "%Y-%m-%dT%H:%M:%S.%LZ",
                                    "onError": None,
                                    "onNull": None
                                }
                            }
                        }
                    },
                    {
                        "$match": {
                            "stats.teams.name": team_name
                        }
                    },
                    {"$sort": {"parsedDate": -1}},
                    {"$limit": 1}
                ]
            else:
                # FEB format: HEADER.TEAM.name and HEADER.starttime
                pipeline = [
                    {
                        "$addFields": {
                            "parsedDate": {
                                "$dateFromString": {
                                    "dateString": "$HEADER.starttime",
                                    "format": "%d-%m-%Y - %H:%M",
                                    "onError": None,
                                    "onNull": None
                                }
                            }
                        }
                    },
                    {
                        "$match": {
                            "HEADER.TEAM.name": team_name
                        }
                    },
                    {"$sort": {"parsedDate": -1}},
                    {"$limit": 1}
                ]

            result = list(collection.aggregate(pipeline))
            return result[0] if result else {}
        except PyMongoError as e:
            return {}

    def get_all_teams(self, collection_name: str) -> List[str]:
        """
        Get list of all unique team names in the collection.
        Supports both FEB and FBCYL data formats.

        Args:
            collection_name: Name of the collection

        Returns:
            Sorted list of team names
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL format: teams.name
                teams = collection.distinct("teams.name")
            else:
                # FEB format: HEADER.TEAM.name
                teams = collection.distinct("HEADER.TEAM.name")

            return sorted(teams)
        except PyMongoError as e:
            return []

    def get_player_stats(self, collection_name: str, date_filter: Dict = None, venue_filter: bool = None, result_filter: str = None) -> List[Dict]:
        """
        Get aggregated player statistics from all matches in the collection.

        Returns a list of dictionaries containing each player's season statistics including:
        - Total games played
        - Total minutes played
        - Total points, assists, rebounds, etc.
        - Shooting percentages
        - Per-game averages

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter dict with datetime object
            venue_filter: Optional boolean to filter by venue (True=home, False=away, None=all)
            result_filter: Optional string to filter by result ('won', 'lost', None=all)

        Returns:
            List of player statistics dictionaries
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                pipeline = FBCYLPipelineBuilder.build_player_stats_pipeline(date_filter, venue_filter, result_filter)
            else:
                pipeline = AggregationPipelineBuilder.build_player_stats_pipeline(date_filter, venue_filter, result_filter)

            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            return []

    def get_aggregated_team_stats(self, collection_name: str, team_name: str) -> Dict:
        """
        Get aggregated statistics for a specific team across all their games.

        Args:
            collection_name: Name of the collection
            team_name: Name of the team

        Returns:
            Dictionary with aggregated team statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            team_stats = self.get_team_stats(collection_name)

            for team in team_stats:
                if team.get('team_name') == team_name:
                    return team

            return {}
        except PyMongoError as e:
            return {}

    def get_aggregated_opponent_stats(self, collection_name: str, team_name: str) -> Dict:
        """
        Get aggregated opponent statistics for a specific team.

        Args:
            collection_name: Name of the collection
            team_name: Name of the team

        Returns:
            Dictionary with aggregated opponent statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            opp_stats = self.get_opponent_stats(collection_name)

            for opp in opp_stats:
                if opp.get('team_name') == team_name:
                    return opp

            return {}
        except PyMongoError as e:
            return {}

    def get_league_stats(self, collection_name: str) -> Dict:
        """
        Get league-wide aggregated statistics.

        Args:
            collection_name: Name of the collection

        Returns:
            Dictionary with league-wide statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            collection = self.connection.get_collection(collection_name)

            # Aggregate all team statistics to get league totals
            pipeline = [
                {
                    "$addFields": {
                        "teams": [
                            {
                                "pts": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 0]}},
                                "fga": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 0]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2a", 0]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 0]}}
                                ]},
                                "fgm": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2m", 0]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3m", 0]}}
                                ]},
                                "ftm": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1m", 0]}},
                                "fta": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 0]}},
                                "orb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 0]}},
                                "drb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 0]}},
                                "trb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rt", 0]}},
                                "ast": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.assist", 0]}},
                                "tov": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.to", 0]}},
                                "pf": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pf", 0]}},
                                "3pa": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 0]}}
                            },
                            {
                                "pts": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pts", 1]}},
                                "fga": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 1]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2a", 1]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 1]}}
                                ]},
                                "fgm": {"$add": [
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p2m", 1]}},
                                    {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3m", 1]}}
                                ]},
                                "ftm": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1m", 1]}},
                                "fta": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p1a", 1]}},
                                "orb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.ro", 1]}},
                                "drb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rd", 1]}},
                                "trb": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.rt", 1]}},
                                "ast": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.assist", 1]}},
                                "tov": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.to", 1]}},
                                "pf": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.pf", 1]}},
                                "3pa": {"$toInt": {"$arrayElemAt": ["$BOXSCORE.TEAM.TOTAL.p3a", 1]}}
                            }
                        ]
                    }
                },
                {
                    "$unwind": "$teams"
                },
                {
                    "$group": {
                        "_id": None,
                        "total_games": {"$sum": 1},  # Count number of games (team-games, not actual games)
                        "total_pts": {"$sum": "$teams.pts"},
                        "total_fga": {"$sum": "$teams.fga"},
                        "total_fgm": {"$sum": "$teams.fgm"},
                        "total_ftm": {"$sum": "$teams.ftm"},
                        "total_fta": {"$sum": "$teams.fta"},
                        "total_orb": {"$sum": "$teams.orb"},
                        "total_drb": {"$sum": "$teams.drb"},
                        "total_trb": {"$sum": "$teams.trb"},
                        "total_ast": {"$sum": "$teams.ast"},
                        "total_tov": {"$sum": "$teams.tov"},
                        "total_pf": {"$sum": "$teams.pf"},
                        "total_3pa": {"$sum": "$teams.3pa"}
                    }
                },
                {
                    "$addFields": {
                        # Calculate total possessions using the formula:
                        # Poss = FGA + 0.4*FTA - 1.07*ORB_pct*(FGA-FGM) + TOV
                        # Simplified here as: FGA + 0.4*FTA - 0.4*ORB + TOV
                        "total_possessions": {
                            "$add": [
                                "$total_fga",
                                {"$multiply": [0.4, "$total_fta"]},
                                {"$multiply": [-0.4, "$total_orb"]},
                                "$total_tov"
                            ]
                        }
                    }
                }
            ]

            result = list(collection.aggregate(pipeline))
            return result[0] if result else {}
        except PyMongoError as e:
            return {}

    def get_games_with_playbyplay(self, collection_name: str, date_filter: Dict = None) -> List[Dict]:
        """
        Get all game documents that contain PLAYBYPLAY data.

        Args:
            collection_name: Name of the collection
            date_filter: Optional MongoDB date filter dict with datetime object

        Returns:
            List of game documents with PLAYBYPLAY data
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            
            # Ensure indexes exist for optimal performance
            self.connection.ensure_indexes(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL: Check for 'moves' field
                match_filter = {"moves": {"$exists": True, "$ne": None}}

                if date_filter:
                    # FBCYL uses stats.time field
                    pipeline = [
                        {
                            "$addFields": {
                                "parsedDate": {
                                    "$dateFromString": {
                                        "dateString": "$stats.time",
                                        "format": "%b %d, %Y %I:%M:%S %p",
                                        "onError": None,
                                        "onNull": None
                                    }
                                }
                            }
                        },
                        {
                            "$match": {
                                "parsedDate": date_filter,
                                "moves": {"$exists": True, "$ne": None}
                            }
                        }
                    ]
                    return list(collection.aggregate(pipeline))
                else:
                    return list(collection.find(match_filter))
            else:
                # FEB: Check for PLAYBYPLAY.LINES
                match_filter = {"PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}}

                if date_filter:
                    # Add date parsing to the pipeline
                    pipeline = [
                        {
                            "$addFields": {
                                "parsedDate": {
                                    "$dateFromString": {
                                        "dateString": "$HEADER.starttime",
                                        "format": "%d-%m-%Y - %H:%M",
                                        "onError": None,
                                        "onNull": None
                                    }
                                }
                            }
                        },
                        {
                            "$match": {
                                "parsedDate": date_filter,
                                "PLAYBYPLAY.LINES": {"$exists": True, "$ne": None}
                            }
                        }
                    ]
                    return list(collection.aggregate(pipeline))
                else:
                    return list(collection.find(match_filter))

        except PyMongoError as e:
            return []

    def get_games_for_team(self, collection_name: str, team_id: str, 
                           only_with_playbyplay: bool = False) -> List[Dict]:
        """
        Get all games for a specific team.

        Args:
            collection_name: Name of the collection
            team_id: Team ID
            only_with_playbyplay: If True, only return games with play-by-play data

        Returns:
            List of game documents where the team participated
        """
        if not self.connection.is_connected():
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            
            # Ensure indexes exist for optimal performance
            self.connection.ensure_indexes(collection_name)
            
            is_fbcyl = _is_fbcyl(collection_name)

            if is_fbcyl:
                # FBCYL: Check in stats.teams array
                match_filter = {
                    "$or": [
                        {"stats.teams.teamIdIntern": team_id},
                        {"stats.teams.teamIdIntern": int(team_id) if team_id.isdigit() else team_id},
                        {"stats.teams.teamIdExtern": team_id},
                        {"stats.teams.teamIdExtern": int(team_id) if team_id.isdigit() else team_id}
                    ]
                }
                
                # Add play-by-play filter if requested
                if only_with_playbyplay:
                    match_filter["moves"] = {"$exists": True, "$ne": None}
            else:
                # FEB: Check in HEADER.TEAM array
                match_filter = {
                    "HEADER.TEAM.id": team_id
                }
                
                # Add play-by-play filter if requested
                if only_with_playbyplay:
                    match_filter["PLAYBYPLAY.LINES"] = {"$exists": True, "$ne": None}

            return list(collection.find(match_filter))

        except PyMongoError as e:
            return []

    def get_player_in_out_stats(self, collection_name: str, player_id: str,
                                 date_filter: Dict = None, debug: bool = False,
                                 progress_callback=None) -> Dict:
        """
        Get IN/OUT statistics for a specific player using play-by-play data.

        Args:
            collection_name: Name of the collection
            player_id: Player's ID (idPlayer from JSON)
            date_filter: Optional MongoDB date filter dict with datetime object
            progress_callback: Optional callback function(current, total) for progress reporting

        Returns:
            Dictionary with 'in' and 'out' statistics and metadata
        """
        if not self.connection.is_connected():
            return {}

        try:
            from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator

            # Report initial progress - fetching games
            if progress_callback:
                progress_callback(0, 100)  # Use percentage-based for this phase

            # Get all games with play-by-play data (this can be slow)
            games = self.get_games_with_playbyplay(collection_name, date_filter)

            # Report that loading is complete
            if progress_callback and len(games) > 0:
                progress_callback(1, len(games))  # Signal that we have the data and starting analysis

            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            # Convert player_id to appropriate type for comparison
            if is_fbcyl:
                # FBCYL: player_id is UUID (stats.teams[].players[].uuid)
                # UUID is stable across games, but actorId changes per game
                # We extract actorId per game to identify actions in moves[]
                # We don't need to find player_team_id upfront since both actorId and teamIdIntern
                # change per game. We'll extract them in the per-game loop below.
                player_id_compare = player_id  # Keep as string (UUID format)
                player_team_id = None  # Not used for FBCYL (per-game extraction instead)
            else:
                # FEB: player_id is consistent across games, find team ID from first appearance
                player_id_compare = player_id
                player_team_id = None

                # Find player's team ID from first appearance
                for game in games:
                    # FEB structure: BOXSCORE.TEAM[].PLAYER[]
                    boxscore = game.get('BOXSCORE', {})
                    teams = boxscore.get('TEAM', [])

                    for team in teams:
                        players = team.get('PLAYER', [])
                        for player in players:
                            if player.get('id') == player_id_compare:
                                player_team_id = team.get('id')
                                break
                        if player_team_id:
                            break

                    if player_team_id:
                        break

                if not player_team_id:
                    return {}

            # Aggregate stats across all games
            total_stats_in = {
                'points_for': 0, 'points_against': 0,
                'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
                'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
                'minutes': 0, 'games': 0,
                # opponent aggregated keys (if provided by analyzer)
                'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
                'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
                'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
            }

            total_stats_out = {
                'points_for': 0, 'points_against': 0,
                'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
                'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
                'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
                'minutes': 0, 'games': 0,
                # opponent aggregated keys (if provided by analyzer)
                'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
                'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
                'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
            }

            games_analyzed = 0
            debug_outputs = []
            games_participated = 0
            total_games = len(games)

            # Report initial progress
            if progress_callback:
                progress_callback(0, total_games)

            for game_index, game in enumerate(games):
                # Report progress at the start of each game
                if progress_callback:
                    progress_callback(game_index + 1, total_games)
                # Default per-game container (to avoid UnboundLocalError in finally)
                game_stats = {}
                game_was_skipped = False

                # For FBCYL: Get actorId AND teamIdIntern for THIS specific game (both change per game)
                current_game_actor_id = None
                current_game_team_id = None

                if is_fbcyl:
                    # Helper function to normalize player names: first initial + surnames
                    def normalize_name(name):
                        if not name:
                            return ""
                        words = name.split()
                        if len(words) >= 3:
                            # First initial + two surnames
                            return f"{words[0][0]} {words[-2]} {words[-1]}"
                        elif len(words) >= 2:
                            # First initial + one surname
                            return f"{words[0][0]} {words[-1]}"
                        return name

                    # Try to get normalized name from player_id if it's a name-based identifier
                    # (in case UUID wasn't available and we're using surnames as fallback)
                    target_normalized = normalize_name(player_id_compare) if not player_id_compare.count('-') == 4 else None

                    stats = game.get('stats', {})
                    for team in stats.get('teams', []):
                        for player in team.get('players', []):
                            # FBCYL: Match by UUID (stable identifier) OR by normalized name
                            player_uuid = player.get('uuid')
                            player_name = player.get('name', '')
                            player_normalized = normalize_name(player_name)

                            if player_uuid == player_id_compare or \
                               (target_normalized and player_normalized == target_normalized):
                                # Extract actorId for THIS game (used in moves[])
                                current_game_actor_id = player.get('actorId')
                                current_game_team_id = team.get('teamIdIntern') or team.get('teamIdExtern')
                                break
                        if current_game_actor_id:
                            break

                    # Skip this game if player not found
                    if not current_game_actor_id or not current_game_team_id:
                        continue

                # Determine if player actually played in this game using BOXSCORE/stats minutes
                def _player_minutes_played(g, pid) -> float:
                    if is_fbcyl:
                        # For FBCYL, pid is the actorId for this specific game
                        # FBCYL structure: stats.teams[].players[]
                        stats = g.get('stats', {})
                        for team in stats.get('teams', []):
                            for p in team.get('players', []):
                                p_id = p.get('actorId')
                                if p_id == pid:
                                    m = p.get('timePlayed')  # FBCYL uses 'timePlayed' field
                                    if m is None:
                                        return 0.0
                                    if isinstance(m, (int, float)):
                                        return float(m)
                                    try:
                                        return float(m)
                                    except Exception:
                                        return 0.0
                        return 0.0
                    else:
                        # FEB structure: BOXSCORE.TEAM[].PLAYER[]
                        box = g.get('BOXSCORE', {})
                        for team in box.get('TEAM', []):
                            for p in team.get('PLAYER', []):
                                if p.get('id') == pid:
                                    m = p.get('min')
                                    if m is None:
                                        return 0.0
                                    if isinstance(m, (int, float)):
                                        return float(m)
                                    s = str(m).strip()
                                    if s in ('0', '0:00', ''):
                                        return 0.0
                                    if ':' in s:
                                        try:
                                            parts = s.split(':')
                                            mm = int(parts[0])
                                            ss = int(parts[1]) if len(parts) > 1 else 0
                                            return mm + ss / 60.0
                                        except Exception:
                                            return 0.0
                                    try:
                                        return float(s)
                                    except Exception:
                                        return 0.0
                        return 0.0

                # For FBCYL, use current game's actorId; for FEB use player_id_compare
                pid_for_game = current_game_actor_id if is_fbcyl else player_id_compare
                minutes_played = _player_minutes_played(game, pid_for_game)

                # Determine if the player's team participated in this game
                def _team_participated(g, team_id) -> bool:
                    if is_fbcyl:
                        # FBCYL: Use teamIdIntern (matches moves[].idTeam for play-by-play)
                        stats = g.get('stats', {})
                        for team in stats.get('teams', []):
                            t_id = team.get('teamIdIntern') or team.get('teamIdExtern')
                            if t_id == team_id:
                                # If there are players listed, consider the team participated
                                players = team.get('players', [])
                                if not players:
                                    return False
                                # If any player has minutes > 0, the team participated
                                for p in players:
                                    m = p.get('timePlayed')
                                    if m is None:
                                        continue
                                    if isinstance(m, (int, float)) and m > 0:
                                        return True
                                # If no player has minutes but players exist, assume team participated
                                return True
                        return False
                    else:
                        # FEB structure: BOXSCORE.TEAM[]
                        box = g.get('BOXSCORE', {})
                        for team in box.get('TEAM', []):
                            if team.get('id') == team_id:
                                # If there are players listed, consider the team participated
                                players = team.get('PLAYER', [])
                                if not players:
                                    return False
                                # If any player has minutes > 0, the team participated
                                for p in players:
                                    m = p.get('min')
                                    if m is None:
                                        continue
                                    if isinstance(m, (int, float)) and m > 0:
                                        return True
                                    s = str(m).strip()
                                    if s and s not in ('0', '0:00'):
                                        # treat presence of a non-zero string minute as participation
                                        return True
                                # If no player has minutes but players exist, assume team participated
                                return True
                        return False

                # Use current game's team_id for FBCYL, or player_team_id for FEB
                team_id_for_game = current_game_team_id if is_fbcyl else player_team_id
                team_played = _team_participated(game, team_id_for_game)

                # Count games where the player actually participated (min > 0)
                if minutes_played > 0.0:
                    games_participated += 1

                try:
                    # Skip games where the player's team did not participate
                    if not team_played:
                        game_was_skipped = True
                        if debug:
                            debug_outputs.append({
                                'game_id': game.get('_id'),
                                'skipped': True,
                                'reason': 'team_not_participating',
                                'in': None,
                                'out': None,
                                'minutes_played': minutes_played,
                                'player_id': player_id
                            })
                        continue
                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)
                    calculator = InOutStatsCalculator(analyzer)

                    # For FBCYL: use actorId and teamIdIntern for this specific game
                    game_stats = calculator.calculate_in_out_stats(pid_for_game, team_id_for_game)

                    # Accumulate IN stats
                    for key in list(total_stats_in.keys()):
                        if key in game_stats.get('in', {}):
                            total_stats_in[key] += game_stats['in'][key]

                    # Accumulate OUT stats
                    for key in list(total_stats_out.keys()):
                        if key in game_stats.get('out', {}):
                            total_stats_out[key] += game_stats['out'][key]

                    games_analyzed += 1

                except Exception as e:
                    if debug:
                        import traceback
                        traceback.print_exc()
                    continue

                finally:
                    if debug and not game_was_skipped:
                        debug_outputs.append({
                            'game_id': game.get('_id'),
                            'skipped': False,
                            'in': game_stats.get('in') if isinstance(game_stats, dict) else None,
                            'out': game_stats.get('out') if isinstance(game_stats, dict) else None,
                            'minutes_played': minutes_played,
                            'player_id': player_id
                        })

            # Use games_participated as the denominator for per-game minutes (Min/J)
            total_stats_in['games'] = games_participated
            total_stats_out['games'] = games_participated

            if debug:
                # Save debug outputs to a JSON file in repository root
                try:
                    import json, os
                    debug_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), f"debug_inout_{player_id}.json")
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        json.dump(debug_outputs, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    pass

            return {
                'in': total_stats_in,
                'out': total_stats_out,
                'player_id': player_id,
                'player_team_id': player_team_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}

    def get_two_players_together_stats(self, collection_name: str, player1_id: str, 
                                        player2_id: str, date_filter: Dict = None, 
                                        debug: bool = False, progress_callback=None) -> Dict:
        """
        Get statistics when two specific players are on court together.

        Args:
            collection_name: Name of the collection
            player1_id: First player's ID (idPlayer from JSON)
            player2_id: Second player's ID (idPlayer from JSON)
            date_filter: Optional MongoDB date filter dict with datetime object
            progress_callback: Optional callback function(current, total) for progress reporting

        Returns:
            Dictionary with statistics when both players are together on court
        """
        if not self.connection.is_connected():
            return {}

        try:
            from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator
            from .inout_repository_helper import InOutRepositoryHelper

            games = self._fetch_games_with_progress(collection_name, date_filter, progress_callback)
            is_fbcyl = _is_fbcyl(collection_name)
            
            total_stats = self._initialize_together_stats()
            games_analyzed = 0
            games_participated = 0

            for game_index, game in enumerate(games):
                self._report_progress(progress_callback, game_index + 1, len(games))
                
                player_info = InOutRepositoryHelper.find_players_in_game(
                    game, player1_id, player2_id, is_fbcyl
                )
                
                if not player_info.all_found:
                    continue

                try:
                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)
                    
                    segments1 = analyzer.get_player_court_segments(player_info.player1_actor_id)
                    segments2 = analyzer.get_player_court_segments(player_info.player2_actor_id)
                    
                    together_segments = InOutRepositoryHelper.calculate_overlap_segments(
                        segments1, segments2
                    )
                    
                    if not together_segments:
                        continue
                    
                    time_together = InOutRepositoryHelper.calculate_total_time(together_segments)
                    
                    actions = InOutRepositoryHelper.filter_actions_by_segments(
                        analyzer, together_segments, is_fbcyl
                    )
                    
                    opponent_id = InOutRepositoryHelper.find_opponent_team_id(
                        game, player_info.team_id, is_fbcyl
                    )
                    
                    calculator = InOutStatsCalculator(analyzer)
                    game_stats = calculator._calculate_stats_from_actions(
                        actions, player_info.team_id, opponent_id or ""
                    )
                    
                    self._accumulate_stats(total_stats, game_stats)
                    total_stats['minutes'] += time_together
                    
                    games_analyzed += 1
                    if time_together > 0:
                        games_participated += 1

                except Exception as e:
                    if debug:
                        import traceback
                        traceback.print_exc()
                    continue

            total_stats['games'] = games_participated

            return {
                'together': total_stats,
                'player1_id': player1_id,
                'player2_id': player2_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}

    def _process_game_with_teammate(self, game: Dict, main_player_id: str, teammate_id: str,
                                   is_fbcyl: bool, debug: bool = False) -> Optional[Dict]:
        """
        Process a single game to extract player and team stats when main player plays with teammate.
        
        Args:
            game: Game document
            main_player_id: Main player's ID
            teammate_id: Teammate's ID
            is_fbcyl: Whether this is FBCYL format
            debug: Whether to print debug info
            
        Returns:
            Dict with 'player_stats', 'team_stats', 'time_together' or None if players not found together
        """
        from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator
        from .inout_repository_helper import InOutRepositoryHelper
        
        player_info = InOutRepositoryHelper.find_players_in_game(
            game, main_player_id, teammate_id, is_fbcyl
        )
        
        if not player_info.all_found:
            return None
        
        try:
            analyzer = PlayByPlayAnalyzer(game, is_fbcyl=is_fbcyl)
            
            segments_main = analyzer.get_player_court_segments(player_info.player1_actor_id)
            segments_teammate = analyzer.get_player_court_segments(player_info.player2_actor_id)
            
            together_segments = InOutRepositoryHelper.calculate_overlap_segments(
                segments_main, segments_teammate
            )
            
            if not together_segments:
                return None
            
            time_together = InOutRepositoryHelper.calculate_total_time(together_segments)
            
            actions = InOutRepositoryHelper.filter_actions_by_segments(
                analyzer, together_segments, is_fbcyl
            )
            
            # Extract individual stats for main player
            player_game_stats = self._calculate_player_individual_stats_from_actions(
                actions, player_info.player1_actor_id, is_fbcyl
            )
            
            # Calculate team stats for possessions
            opponent_id = InOutRepositoryHelper.find_opponent_team_id(
                game, player_info.team_id, is_fbcyl
            )
            
            calculator = InOutStatsCalculator(analyzer)
            team_game_stats = calculator._calculate_stats_from_actions(
                actions, player_info.team_id, opponent_id or ""
            )
            
            return {
                'player_stats': player_game_stats,
                'team_stats': team_game_stats,
                'time_together': time_together
            }
            
        except Exception as e:
            if debug:
                import traceback
                traceback.print_exc()
            return None
    
    def get_player_individual_stats_with_teammate(self, collection_name: str, 
                                                   main_player_id: str, teammate_id: str,
                                                   date_filter: Dict = None, debug: bool = False,
                                                   progress_callback=None) -> Dict:
        """
        Get individual statistics of main_player when playing with teammate, normalized per 100 possessions.

        Args:
            collection_name: Name of the collection
            main_player_id: Main player's ID (idPlayer from JSON)
            teammate_id: Teammate's ID (idPlayer from JSON)
            date_filter: Optional MongoDB date filter dict with datetime object
            progress_callback: Optional callback function(current, total) for progress reporting

        Returns:
            Dictionary with main player's individual and normalized (per 100 poss) statistics
        """
        if not self.connection.is_connected():
            return {}

        try:
            games = self._fetch_games_with_progress(collection_name, date_filter, progress_callback)
            is_fbcyl = _is_fbcyl(collection_name)
            
            total_stats = self._initialize_player_individual_stats()
            team_stats = self._initialize_together_stats()
            games_analyzed = 0
            games_participated = 0

            for game_index, game in enumerate(games):
                self._report_progress(progress_callback, game_index + 1, len(games))
                
                game_result = self._process_game_with_teammate(
                    game, main_player_id, teammate_id, is_fbcyl, debug
                )
                
                if game_result is None:
                    continue
                
                # Accumulate stats
                self._accumulate_player_individual_stats(total_stats, game_result['player_stats'])
                self._accumulate_stats(team_stats, game_result['team_stats'])
                total_stats['minutes'] += game_result['time_together']
                team_stats['minutes'] += game_result['time_together']
                
                games_analyzed += 1
                if game_result['time_together'] > 0:
                    games_participated += 1

            total_stats['games'] = games_participated
            team_stats['games'] = games_participated

            # Calculate team possessions and normalize player stats
            possessions = self._calculate_possessions_from_stats(team_stats)
            normalized_stats = self._normalize_player_stats_per_100poss(
                total_stats, possessions
            )

            return {
                'raw_stats': total_stats,
                'team_stats': team_stats,
                'possessions': possessions,
                'per_100_poss': normalized_stats,
                'main_player_id': main_player_id,
                'teammate_id': teammate_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}
    
    def _initialize_player_individual_stats(self) -> Dict:
        """Initialize empty player individual statistics dictionary."""
        return {
            'points': 0,
            'fgm_2': 0, 'fga_2': 0,
            'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0,
            'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 0, 'games': 0
        }
    
    def _process_fbcyl_player_action(self, action: Dict, player_actor_id: str, stats: Dict) -> None:
        """
        Process a single FBCYL action for individual player stats.
        
        Args:
            action: FBCYL action dictionary
            player_actor_id: Player's actor ID
            stats: Statistics dictionary to update (modified in place)
        """
        actor_id = str(action.get('actorId', ''))
        if actor_id != player_actor_id:
            return
        
        move_text = action.get('move', '')
        
        # Points scored and shots (based on Spanish FBCYL patterns)
        if 'Canasta de 1' in move_text:
            stats['points'] += 1
            stats['ftm'] += 1
            stats['fta'] += 1
        elif 'Intento fallado de 1' in move_text:
            stats['fta'] += 1
        elif 'Canasta de 2' in move_text:
            stats['points'] += 2
            stats['fgm_2'] += 1
            stats['fga_2'] += 1
        elif 'Intento fallado de 2' in move_text:
            stats['fga_2'] += 1
        elif 'Canasta de 3' in move_text:
            stats['points'] += 3
            stats['fgm_3'] += 1
            stats['fga_3'] += 1
        elif 'Intento fallado de 3' in move_text:
            stats['fga_3'] += 1
        
        # Other stats (check if these patterns exist in FBCYL)
        move_lower = move_text.lower()
        if 'asistencia' in move_lower:
            stats['ast'] += 1
        if 'robo' in move_lower or 'recuperación' in move_lower:
            stats['stl'] += 1
        if 'tapón' in move_lower or 'bloqueo' in move_lower:
            stats['blk'] += 1
        if 'pérdida' in move_lower:
            stats['tov'] += 1
        if 'personal' in move_lower or 'falta' in move_lower:
            stats['pf'] += 1
        if 'rebote' in move_lower:
            if 'ofensivo' in move_lower:
                stats['orb'] += 1
            elif 'defensivo' in move_lower:
                stats['drb'] += 1
            else:
                # Generic rebound, count as defensive by default
                stats['drb'] += 1
    
    def _process_feb_player_action(self, action: Dict, player_actor_id: str, stats: Dict,
                                   context: Dict) -> None:
        """
        Process a single FEB action for individual player stats.
        
        Args:
            action: FEB action dictionary
            player_actor_id: Player's actor ID
            stats: Statistics dictionary to update (modified in place)
            context: Shared context dict with 'last_shot_team' and 'player_team' keys
        """
        actor_id = str(action.get('idPlayer', ''))
        action_type = action.get('action', '')
        text = action.get('text', '').upper()
        current_team = str(action.get('idTeam', ''))
        
        # Track player's team for rebound context
        if actor_id == player_actor_id and context['player_team'] is None:
            context['player_team'] = current_team
        
        # Track last shot team for rebound classification
        if action_type in ['shoot', 'fthrow']:
            if 'FALLADO' in text or 'MISS' in text:
                context['last_shot_team'] = current_team
            else:
                context['last_shot_team'] = None  # Made shots don't lead to rebounds
        
        if actor_id != player_actor_id:
            return
        
        # Process player's action based on type
        if action_type == 'shoot':
            self._process_feb_shot(text, stats)
        elif action_type == 'fthrow':
            self._process_feb_free_throw(text, stats)
        elif action_type == 'assist':
            stats['ast'] += 1
        elif action_type == 'recovery':
            stats['stl'] += 1
        elif action_type == 'blockshot':
            stats['blk'] += 1
        elif action_type == 'lose':
            stats['tov'] += 1
        elif action_type == 'foul':
            stats['pf'] += 1
        elif action_type == 'rebound':
            self._process_feb_rebound(stats, context)
    
    def _process_feb_shot(self, text: str, stats: Dict) -> None:
        """Process FEB shoot action."""
        if 'TIRO DE 2' in text or 'TIRO DE CAMPO' in text:
            if 'ANOTADO' in text or 'CONVERTIDO' in text:
                stats['points'] += 2
                stats['fgm_2'] += 1
                stats['fga_2'] += 1
            else:
                stats['fga_2'] += 1
        elif 'TIRO DE 3' in text or '3 PUNTOS' in text:
            if 'ANOTADO' in text or 'CONVERTIDO' in text:
                stats['points'] += 3
                stats['fgm_3'] += 1
                stats['fga_3'] += 1
            else:
                stats['fga_3'] += 1
    
    def _process_feb_free_throw(self, text: str, stats: Dict) -> None:
        """Process FEB free throw action."""
        stats['fta'] += 1
        if 'ANOTADO' in text:
            stats['points'] += 1
            stats['ftm'] += 1
    
    def _process_feb_rebound(self, stats: Dict, context: Dict) -> None:
        """Process FEB rebound with context."""
        last_shot_team = context.get('last_shot_team')
        player_team = context.get('player_team')
        
        if last_shot_team and player_team:
            if last_shot_team == player_team:
                stats['orb'] += 1
            else:
                stats['drb'] += 1
        else:
            stats['drb'] += 1
        context['last_shot_team'] = None
    
    def _calculate_player_individual_stats_from_actions(self, actions: List[Dict], 
                                                        player_actor_id: str,
                                                        is_fbcyl: bool) -> Dict:
        """
        Calculate individual player statistics from filtered actions.

        Args:
            actions: List of play-by-play actions
            player_actor_id: Actor ID of the main player
            is_fbcyl: Whether this is FBCYL format

        Returns:
            Dictionary with player's individual statistics
        """
        stats = self._initialize_player_individual_stats()
        
        if is_fbcyl:
            # FBCYL: Simple iteration
            for action in actions:
                self._process_fbcyl_player_action(action, player_actor_id, stats)
        else:
            # FEB: Track context for rebound classification
            context = {'last_shot_team': None, 'player_team': None}
            for action in actions:
                self._process_feb_player_action(action, player_actor_id, stats, context)
        
        return stats
    
    def _accumulate_player_individual_stats(self, total_stats: Dict, game_stats: Dict) -> None:
        """Accumulate player individual statistics."""
        for key in ['points', 'fgm_2', 'fga_2', 'fgm_3', 'fga_3', 'ftm', 'fta',
                   'orb', 'drb', 'ast', 'stl', 'blk', 'tov', 'pf']:
            if key in game_stats:
                total_stats[key] += game_stats[key]

    def _calculate_possessions_from_stats(self, stats: Dict) -> float:
        """
        Calculate team possessions from statistics.
        Formula: FGA + (0.45 * FTA) + TOV - ORB
        """
        fga = stats.get('fga_2', 0) + stats.get('fga_3', 0)
        fta = stats.get('fta', 0)
        tov = stats.get('tov', 0)
        orb = stats.get('orb', 0)
        
        possessions = fga + (0.45 * fta) + tov - orb
        return max(possessions, 1)  # Avoid division by zero

    def _normalize_player_stats_per_100poss(self, stats: Dict, possessions: float) -> Dict:
        """
        Normalize player individual statistics per 100 possessions.
        
        Args:
            stats: Raw player statistics
            possessions: Team possessions when player was on court
            
        Returns:
            Dictionary with normalized statistics per 100 possessions
        """
        if possessions <= 0:
            return {key: 0.0 for key in ['points', 'fgm_2', 'fga_2', 'fgm_3', 'fga_3', 
                                         'ftm', 'fta', 'orb', 'drb', 'ast', 'stl', 
                                         'blk', 'tov', 'pf']}
        
        factor = 100.0 / possessions
        
        return {
            'points': stats.get('points', 0) * factor,
            'fgm_2': stats.get('fgm_2', 0) * factor,
            'fga_2': stats.get('fga_2', 0) * factor,
            'fgm_3': stats.get('fgm_3', 0) * factor,
            'fga_3': stats.get('fga_3', 0) * factor,
            'ftm': stats.get('ftm', 0) * factor,
            'fta': stats.get('fta', 0) * factor,
            'orb': stats.get('orb', 0) * factor,
            'drb': stats.get('drb', 0) * factor,
            'ast': stats.get('ast', 0) * factor,
            'stl': stats.get('stl', 0) * factor,
            'blk': stats.get('blk', 0) * factor,
            'tov': stats.get('tov', 0) * factor,
            'pf': stats.get('pf', 0) * factor,
            # Calculate percentages (not normalized)
            'fg2_pct': (stats.get('fgm_2', 0) / stats.get('fga_2', 1) * 100) if stats.get('fga_2', 0) > 0 else 0,
            'fg3_pct': (stats.get('fgm_3', 0) / stats.get('fga_3', 1) * 100) if stats.get('fga_3', 0) > 0 else 0,
            'ft_pct': (stats.get('ftm', 0) / stats.get('fta', 1) * 100) if stats.get('fta', 0) > 0 else 0,
            'efg_pct': ((stats.get('fgm_2', 0) + 1.5 * stats.get('fgm_3', 0)) / 
                       (stats.get('fga_2', 0) + stats.get('fga_3', 0)) * 100) 
                       if (stats.get('fga_2', 0) + stats.get('fga_3', 0)) > 0 else 0,
            'ts_pct': (stats.get('points', 0) / 
                      (2 * (stats.get('fga_2', 0) + stats.get('fga_3', 0) + 0.44 * stats.get('fta', 0))) * 100)
                      if (stats.get('fga_2', 0) + stats.get('fga_3', 0) + stats.get('fta', 0)) > 0 else 0
        }

    def _fetch_games_with_progress(self, collection_name: str, date_filter: Dict,
                                   progress_callback) -> List[Dict]:
        """Fetch games and report initial progress."""
        if progress_callback:
            progress_callback(0, 100)
        
        games = self.get_games_with_playbyplay(collection_name, date_filter)
        
        if progress_callback and len(games) > 0:
            progress_callback(1, len(games))
        
        return games

    def _initialize_together_stats(self) -> Dict:
        """Initialize empty statistics dictionary."""
        return {
            'points_for': 0, 'points_against': 0,
            'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'minutes': 0, 'games': 0,
            'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
            'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
            'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
        }

    def _report_progress(self, progress_callback, current: int, total: int) -> None:
        """Report progress if callback provided."""
        if progress_callback:
            progress_callback(current, total)

    def _accumulate_stats(self, total_stats: Dict, game_stats: Dict) -> None:
        """Accumulate game statistics into total."""
        for key in list(total_stats.keys()):
            if key in game_stats:
                total_stats[key] += game_stats[key]

    def _old_calculate_stats_from_actions_helper(self, actions: List[Dict], team_id: str, 
                                             is_fbcyl: bool, game: Dict) -> Dict:
        """
        Helper method to calculate statistics from a list of actions.
        
        Args:
            actions: List of action dictionaries
            team_id: Team ID to calculate stats for
            is_fbcyl: Whether this is FBCYL format
            game: Full game data for context
            
        Returns:
            Dictionary with calculated statistics
        """
        # Find opponent team ID
        opponent_team_id = None
        
        if is_fbcyl:
            stats = game.get('stats', {})
            for team in stats.get('teams', []):
                tid = team.get('teamIdIntern') or team.get('teamIdExtern')
                if tid != team_id:
                    opponent_team_id = tid
                    break
        else:
            teams = game.get('HEADER', {}).get('TEAM', [])
            for team in teams:
                tid = team.get('id')
                if tid != team_id:
                    opponent_team_id = tid
                    break
        
        stats = {
            'points_for': 0, 'points_against': 0,
            'fgm_2': 0, 'fga_2': 0, 'fgm_3': 0, 'fga_3': 0,
            'ftm': 0, 'fta': 0, 'orb': 0, 'drb': 0,
            'ast': 0, 'stl': 0, 'blk': 0, 'tov': 0, 'pf': 0,
            'opp_fgm_2': 0, 'opp_fga_2': 0, 'opp_fgm_3': 0, 'opp_fga_3': 0,
            'opp_ftm': 0, 'opp_fta': 0, 'opp_orb': 0, 'opp_drb': 0,
            'opp_ast': 0, 'opp_stl': 0, 'opp_blk': 0, 'opp_tov': 0, 'opp_pf': 0
        }
        
        for action in actions:
            if is_fbcyl:
                # FBCYL processing
                move_text = action.get('move', '').upper()
                action_team = str(action.get('idTeam', ''))
                points = action.get('points', 0)
                
                # Points
                if points > 0:
                    if action_team == str(team_id):
                        stats['points_for'] += points
                    elif opponent_team_id and action_team == str(opponent_team_id):
                        stats['points_against'] += points
                
                # Determine target (team or opponent)
                is_team_action = (action_team == str(team_id))
                prefix = '' if is_team_action else 'opp_'
                
                # Process stats based on move text
                if points == 2 and '2PT' in move_text:
                    stats[f'{prefix}fga_2'] += 1
                    if 'SUCCESS' in move_text or points > 0:
                        stats[f'{prefix}fgm_2'] += 1
                elif points == 3 and '3PT' in move_text:
                    stats[f'{prefix}fga_3'] += 1
                    if 'SUCCESS' in move_text or points > 0:
                        stats[f'{prefix}fgm_3'] += 1
                elif 'FREE_THROW' in move_text:
                    stats[f'{prefix}fta'] += 1
                    if 'SUCCESS' in move_text or points > 0:
                        stats[f'{prefix}ftm'] += 1
                
                if 'REBOUND_OFF' in move_text:
                    stats[f'{prefix}orb'] += 1
                elif 'REBOUND_DEF' in move_text:
                    stats[f'{prefix}drb'] += 1
                elif 'ASSIST' in move_text:
                    stats[f'{prefix}ast'] += 1
                elif 'STEAL' in move_text or 'TURNOVER_STEAL' in move_text:
                    stats[f'{prefix}stl'] += 1
                elif 'BLOCK' in move_text:
                    stats[f'{prefix}blk'] += 1
                elif 'TURNOVER' in move_text and 'STEAL' not in move_text:
                    stats[f'{prefix}tov'] += 1
                elif 'FOUL' in move_text:
                    stats[f'{prefix}pf'] += 1
                    
            else:
                # FEB processing
                text = action.get('text', '').upper()
                action_type = action.get('action', '')
                action_team = str(action.get('idTeam', ''))
                
                is_team_action = (action_team == str(team_id))
                prefix = '' if is_team_action else 'opp_'
                
                # Points
                if 'CANASTA DE 2' in text or 'TIRO DE 2' in text:
                    stats[f'{prefix}fga_2'] += 1
                    if 'FALLADO' not in text:
                        stats[f'{prefix}fgm_2'] += 1
                        stats['points_for' if is_team_action else 'points_against'] += 2
                elif 'CANASTA DE 3' in text or 'TIRO DE 3' in text or 'TRIPLE' in text:
                    stats[f'{prefix}fga_3'] += 1
                    if 'FALLADO' not in text:
                        stats[f'{prefix}fgm_3'] += 1
                        stats['points_for' if is_team_action else 'points_against'] += 3
                elif 'TIRO LIBRE' in text:
                    stats[f'{prefix}fta'] += 1
                    if 'ANOTADO' in text:
                        stats[f'{prefix}ftm'] += 1
                        stats['points_for' if is_team_action else 'points_against'] += 1
                
                # Other stats
                if action_type == 'rebound' or 'REBOTE' in text:
                    # Simplified: assume offensive if rebote ofensivo mentioned
                    if 'OFENSIVO' in text:
                        stats[f'{prefix}orb'] += 1
                    else:
                        stats[f'{prefix}drb'] += 1
                elif 'ASISTENCIA' in text:
                    stats[f'{prefix}ast'] += 1
                elif 'ROBO' in text or 'RECUPERA' in text:
                    stats[f'{prefix}stl'] += 1
                elif 'TAPÓN' in text or 'TAPON' in text:
                    stats[f'{prefix}blk'] += 1
                elif 'PÉRDIDA' in text or 'PERDIDA' in text:
                    stats[f'{prefix}tov'] += 1
                elif 'FALTA' in text:
                    stats[f'{prefix}pf'] += 1
        
        return stats

    def get_team_possession_stats(self, collection_name: str, team_id: str,
                                   date_filter: Dict = None) -> Dict:
        """
        Get possession statistics for a team using play-by-play data.

        Args:
            collection_name: Name of the collection
            team_id: Team's ID
            date_filter: Optional MongoDB date filter dict with datetime object

        Returns:
            Dictionary with possession statistics:
            - total_possessions: Total number of possessions across all games
            - avg_duration: Average possession duration in seconds
            - possessions_by_duration: Stats for <=8s, 8-16s, >16s with count, points, and OER
            - games_analyzed: Number of games included in analysis
        """
        if not self.connection.is_connected():
            return {}

        try:
            from .playbyplay_analyzer import PossessionAnalyzer

            # Get games for this specific team WITH play-by-play data only (optimized)
            games = self.get_games_for_team(collection_name, team_id, only_with_playbyplay=True)
            
            if not games:
                return {
                    'total_possessions': 0,
                    'avg_duration': 0.0,
                    'possessions_by_duration': {
                        '<=8s': {'count': 0, 'total_points': 0, 'oer': 0.0},
                        '8-16s': {'count': 0, 'total_points': 0, 'oer': 0.0},
                        '>16s': {'count': 0, 'total_points': 0, 'oer': 0.0}
                    },
                    'games_analyzed': 0
                }
            
            # Detect if this is a FBCYL collection
            is_fbcyl = _is_fbcyl(collection_name)

            # Aggregate stats across all games
            all_possessions = []
            short_poss = {'count': 0, 'total_points': 0}  # <=8s
            medium_poss = {'count': 0, 'total_points': 0}  # 8-16s
            long_poss = {'count': 0, 'total_points': 0}  # >16s
            games_analyzed = 0

            for game in games:
                try:
                    analyzer = PossessionAnalyzer(game, is_fbcyl=is_fbcyl)
                    game_stats = analyzer.calculate_possessions(team_id)

                    # Aggregate totals
                    all_possessions.extend([game_stats['avg_duration']] * game_stats['total_possessions'])
                    
                    # Aggregate by duration
                    for duration_key in ['<=8s', '8-16s', '>16s']:
                        duration_stats = game_stats['possessions_by_duration'][duration_key]
                        if duration_key == '<=8s':
                            short_poss['count'] += duration_stats['count']
                            short_poss['total_points'] += duration_stats['total_points']
                        elif duration_key == '8-16s':
                            medium_poss['count'] += duration_stats['count']
                            medium_poss['total_points'] += duration_stats['total_points']
                        else:  # '>16s'
                            long_poss['count'] += duration_stats['count']
                            long_poss['total_points'] += duration_stats['total_points']

                    games_analyzed += 1

                except Exception as e:
                    continue

            # Calculate overall statistics
            total_possessions = short_poss['count'] + medium_poss['count'] + long_poss['count']
            avg_duration = sum(all_possessions) / len(all_possessions) if all_possessions else 0.0

            # Calculate OER for each duration range
            def calculate_oer(poss_count: int, total_points: int) -> float:
                if poss_count == 0:
                    return 0.0
                return (total_points / poss_count) * 100

            return {
                'total_possessions': total_possessions,
                'avg_duration': round(avg_duration, 2),
                'possessions_by_duration': {
                    '<=8s': {
                        'count': short_poss['count'],
                        'total_points': short_poss['total_points'],
                        'oer': round(calculate_oer(short_poss['count'], short_poss['total_points']), 2)
                    },
                    '8-16s': {
                        'count': medium_poss['count'],
                        'total_points': medium_poss['total_points'],
                        'oer': round(calculate_oer(medium_poss['count'], medium_poss['total_points']), 2)
                    },
                    '>16s': {
                        'count': long_poss['count'],
                        'total_points': long_poss['total_points'],
                        'oer': round(calculate_oer(long_poss['count'], long_poss['total_points']), 2)
                    }
                },
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            return {}

    def get_lineup_analysis(
        self,
        collection_name: str,
        team_id: str,
        team_name: str,
        combination_size: int = 5,
        date_filter: Dict = None,
        is_fbcyl: bool = False,
        progress_callback=None
    ) -> List[Dict]:
        """
        Get lineup analysis for a team showing best and worst lineups by statistics.

        Args:
            collection_name: MongoDB collection name
            team_id: Team identifier
            team_name: Team name for filtering
            combination_size: Size of player combination (3, 4, or 5)
            date_filter: Optional date filter dictionary
            is_fbcyl: Whether data is FBCYL format
            progress_callback: Optional callback function(current, total) for progress

        Returns:
            List of lineup dictionaries with statistics, sorted by net rating
        """
        from .playbyplay_analyzer import PlayByPlayAnalyzer
        from .lineup_extractor import LineupExtractor
        from .lineup_stats_calculator import LineupStatsCalculator

        try:
            # Get all games with play-by-play for this team
            games = self.get_games_for_team(
                collection_name,
                team_id,
                only_with_playbyplay=True
            )

            if not games:
                return []

            # Apply date filter if provided
            if date_filter:
                filtered_games = []
                for game in games:
                    # Extract date from game
                    if is_fbcyl:
                        game_date = game.get('date', '')
                    else:
                        game_date = game.get('HEADER', {}).get('starttime', '').split(' - ')[0]
                    
                    # Compare with filter (assuming filter is like {"$gte": "2024-01-01"})
                    if '$gte' in date_filter:
                        if game_date >= date_filter['$gte']:
                            filtered_games.append(game)
                    else:
                        filtered_games.append(game)
                
                games = filtered_games

            if not games:
                return []

            # Track lineup statistics across all games
            lineup_stats_map = {}  # frozenset -> stats dict
            total_games = len(games)

            for game_idx, game in enumerate(games):
                try:
                    # Report progress
                    if progress_callback:
                        progress_callback(game_idx + 1, total_games)

                    # Initialize analyzers
                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl)
                    extractor = LineupExtractor(analyzer)
                    calculator = LineupStatsCalculator(analyzer)

                    # Get all lineup combinations for this game (NO minimum threshold per game)
                    lineup_times = extractor.get_lineup_combinations(
                        team_id,
                        combination_size,
                        min_seconds=0  # Detect ALL lineups, filter later by total time
                    )

                    # Calculate stats for each lineup in this game
                    for lineup_key, time_seconds in lineup_times.items():
                        lineup_stats = calculator.calculate_lineup_stats_single_game(
                            analyzer,
                            extractor,
                            team_id,
                            lineup_key
                        )

                        # Aggregate with existing stats
                        if lineup_key not in lineup_stats_map:
                            # First time seeing this lineup
                            lineup_stats['avg_minutes_per_game'] = lineup_stats.get('minutes', 0)
                            lineup_stats_map[lineup_key] = lineup_stats
                        else:
                            # Merge stats from this game
                            existing = lineup_stats_map[lineup_key]
                            self._merge_lineup_stats(existing, lineup_stats)

                except Exception as e:
                    # Skip games with errors (e.g., incomplete play-by-play)
                    print(f"Error processing game for lineup analysis: {e}")
                    continue

            # Convert to list and add player names
            # Filter by total accumulated time and games played for representative lineups
            lineup_list = []
            min_total_minutes = 15  # 15 minutes minimum total
            min_games_played = 5    # At least 5 games
            
            for lineup_key, stats in lineup_stats_map.items():
                total_minutes = stats.get('minutes', 0)
                games_played = stats.get('games_played', 0)
                
                # Skip lineups that don't meet minimum thresholds
                if total_minutes < min_total_minutes or games_played < min_games_played:
                    continue
                
                # Get player names
                player_names = self._get_player_names_for_lineup(
                    collection_name,
                    lineup_key,
                    is_fbcyl
                )
                
                stats['player_names'] = player_names
                stats['player_ids'] = list(lineup_key)
                lineup_list.append(stats)

            # Sort by net rating (descending)
            lineup_list.sort(key=lambda x: x.get('net_rating', 0), reverse=True)

            return lineup_list

        except PyMongoError as e:
            print(f"MongoDB error in get_lineup_analysis: {e}")
            return []

    def _merge_lineup_stats(self, existing: Dict, new_stats: Dict) -> None:
        """
        Merge new lineup stats into existing stats.

        Args:
            existing: Existing stats dictionary (modified in place)
            new_stats: New stats to add
        """
        # Aggregate counting stats
        counting_stats = [
            'points_for', 'points_against', 'fgm', 'fga', 'fg3m', 'fg3a',
            'ftm', 'fta', 'orb', 'drb', 'trb', 'ast', 'stl', 'blk', 'tov', 'pf'
        ]
        
        for stat in counting_stats:
            existing[stat] = existing.get(stat, 0) + new_stats.get(stat, 0)
        
        # Aggregate minutes, possessions, games, and segments
        old_minutes = existing.get('minutes', 0)
        new_minutes = new_stats.get('minutes', 0)
        existing['minutes'] = old_minutes + new_minutes
        existing['possessions'] = existing.get('possessions', 0) + new_stats.get('possessions', 0)
        existing['games_played'] = existing.get('games_played', 0) + new_stats.get('games_played', 0)
        existing['segments_count'] = existing.get('segments_count', 0) + new_stats.get('segments_count', 0)
        
        # Calculate average minutes per game
        if existing['games_played'] > 0:
            existing['avg_minutes_per_game'] = round(existing['minutes'] / existing['games_played'], 1)
        else:
            existing['avg_minutes_per_game'] = 0.0
        
        # Recalculate derived stats
        existing['plus_minus'] = existing['points_for'] - existing['points_against']
        
        possessions = existing['possessions']
        if possessions > 0:
            existing['ortg'] = round((existing['points_for'] / possessions) * 100, 1)
            existing['drtg'] = round((existing['points_against'] / possessions) * 100, 1)
            existing['net_rating'] = round(existing['ortg'] - existing['drtg'], 1)
        
        # Recalculate percentages
        fga = existing.get('fga', 0)
        if fga > 0:
            fgm = existing.get('fgm', 0)
            fg3m = existing.get('fg3m', 0)
            existing['efg_pct'] = round(((fgm + 0.5 * fg3m) / fga) * 100, 1)
            
            fta = existing.get('fta', 0)
            existing['ftr'] = round(fta / fga, 2)
        
        tov = existing.get('tov', 0)
        fta = existing.get('fta', 0)
        denominator = fga + 0.44 * fta + tov
        if denominator > 0:
            existing['tov_pct'] = round((tov / denominator) * 100, 1)

    def _get_player_names_for_lineup(
        self,
        collection_name: str,
        lineup_keys: FrozenSet[str],
        is_fbcyl: bool
    ) -> List[str]:
        """
        Get player names from their IDs.

        Args:
            collection_name: MongoDB collection name
            lineup_keys: Frozenset of player IDs
            is_fbcyl: Whether data is FBCYL format

        Returns:
            List of player names
        """
        names = []
        player_ids_list = list(lineup_keys)
        
        # Try to find all players in a single query
        try:
            collection = self.connection.get_collection(collection_name)
            
            if is_fbcyl:
                # FBCYL: actorId in stats.teams.players
                # Convert to ints for matching
                player_ids_int = []
                for pid in player_ids_list:
                    try:
                        player_ids_int.append(int(pid))
                    except:
                        player_ids_int.append(pid)
                
                game = collection.find_one(
                    {"stats.teams.players.actorId": {"$in": player_ids_int}},
                    {"stats.teams.players": 1}
                )
                
                if game:
                    player_map = {}
                    for team in game.get('stats', {}).get('teams', []):
                        for player in team.get('players', []):
                            actor_id = str(player.get('actorId'))
                            if actor_id in player_ids_list:
                                player_map[actor_id] = player.get('name', 'Unknown')
                    
                    # Preserve order and handle missing players
                    for pid in player_ids_list:
                        names.append(player_map.get(pid, f"Player {pid}"))
                else:
                    names = [f"Player {pid}" for pid in player_ids_list]
            else:
                # FEB: id in BOXSCORE.TEAM.PLAYER
                # Convert to mixed types for matching
                player_ids_mixed = []
                for pid in player_ids_list:
                    player_ids_mixed.append(pid)
                    try:
                        player_ids_mixed.append(int(pid))
                    except:
                        pass
                
                game = collection.find_one(
                    {"BOXSCORE.TEAM.PLAYER.id": {"$in": player_ids_mixed}},
                    {"BOXSCORE.TEAM.PLAYER": 1}
                )
                
                if game:
                    player_map = {}
                    for team in game.get('BOXSCORE', {}).get('TEAM', []):
                        for player in team.get('PLAYER', []):
                            player_id = str(player.get('id', ''))
                            if player_id in player_ids_list:
                                player_map[player_id] = player.get('name', 'Unknown')
                    
                    # Preserve order and handle missing players
                    for pid in player_ids_list:
                        names.append(player_map.get(pid, f"Player {pid}"))
                else:
                    names = [f"Player {pid}" for pid in player_ids_list]
                    
        except Exception as e:
            print(f"Error getting player names: {e}")
            names = [f"Player {pid}" for pid in player_ids_list]
        
        return names
