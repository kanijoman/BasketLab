"""Repository for basketball data operations."""

from typing import Dict, List
from pymongo.errors import PyMongoError

from .connection import MongoDBConnection
from .aggregation import AggregationPipelineBuilder
from .aggregation.fbcyl_pipeline import FBCYLPipelineBuilder


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
            print(f"[BasketballRepository] No connection to MongoDB")
            return False

        try:
            collection = self.connection.get_collection(collection_name)
            # Convert to int if it's a numeric string, otherwise use as-is (UUID)
            doc_id = int(match_code) if isinstance(match_code, str) and match_code.isdigit() else match_code
            return collection.find_one({"_id": doc_id}) is not None
        except PyMongoError as e:
            print(f"[BasketballRepository] Error checking document existence for match {match_code}: {e}")
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
            print(f"[BasketballRepository] No connection to MongoDB")
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
            print(f"[BasketballRepository] Failed to save match {match_code} to MongoDB: {e}")
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
            print(f"[BasketballRepository] No connection to MongoDB")
            return False

        # Check if document already exists
        if self.document_exists(collection_name, match_uuid):
            print(f"[BasketballRepository] FBCYL match {match_uuid} already exists, skipping")
            return True

        try:
            collection = self.connection.get_collection(collection_name)
            # Use UUID as the document _id
            match_data["_id"] = match_uuid
            collection.insert_one(match_data)
            print(f"[BasketballRepository] Successfully inserted FBCYL match {match_uuid}")
            return True
        except PyMongoError as e:
            print(f"[BasketballRepository] Failed to save FBCYL match {match_uuid} to MongoDB: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection by checking collection name or document structure
            is_fbcyl = collection_name.startswith('FBCYL_')

            if is_fbcyl:
                print(f"[BasketballRepository] Using FBCYL pipeline for collection: {collection_name}")
                pipeline = FBCYLPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)
            else:
                print(f"[BasketballRepository] Using FEB pipeline for collection: {collection_name}")
                pipeline = AggregationPipelineBuilder.build_team_stats_pipeline(date_filter, venue_filter, result_filter)

            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting team stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Detect if this is a FBCYL collection
            is_fbcyl = collection_name.startswith('FBCYL_')

            if is_fbcyl:
                print(f"[BasketballRepository] Using FBCYL pipeline for opponent stats: {collection_name}")
                pipeline = FBCYLPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)
            else:
                print(f"[BasketballRepository] Using FEB pipeline for opponent stats: {collection_name}")
                pipeline = AggregationPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)

            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting opponent stats: {e}")
            return []

    def get_last_match(self, collection_name: str, team_name: str) -> Dict:
        if not self.connection.is_connected():
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_opponent_stats_pipeline(date_filter, venue_filter, result_filter)
            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting opponent stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return {}

        try:
            collection = self.connection.get_collection(collection_name)

            # First, add parsed date field and filter by team
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
            print(f"[BasketballRepository] Error getting last match: {e}")
            return {}

    def get_all_teams(self, collection_name: str) -> List[str]:
        """
        Get list of all unique team names in the collection.

        Args:
            collection_name: Name of the collection

        Returns:
            Sorted list of team names
        """
        if not self.connection.is_connected():
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            teams = collection.distinct("HEADER.TEAM.name")
            return sorted(teams)
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting teams: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)
            pipeline = AggregationPipelineBuilder.build_player_stats_pipeline(date_filter, venue_filter, result_filter)
            return list(collection.aggregate(pipeline))
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting player stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            team_stats = self.get_team_stats(collection_name)

            for team in team_stats:
                if team.get('team_name') == team_name:
                    return team

            return {}
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting aggregated team stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return {}

        try:
            collection = self.connection.get_collection(collection_name)
            opp_stats = self.get_opponent_stats(collection_name)

            for opp in opp_stats:
                if opp.get('team_name') == team_name:
                    return opp

            return {}
        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting aggregated opponent stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
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
            print(f"[BasketballRepository] Error getting league stats: {e}")
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
            print("[BasketballRepository] No connection to MongoDB")
            return []

        try:
            collection = self.connection.get_collection(collection_name)

            # Build match filter
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
            print(f"[BasketballRepository] Error getting games with playbyplay: {e}")
            return []

    def get_player_in_out_stats(self, collection_name: str, player_id: str,
                                 date_filter: Dict = None, debug: bool = False) -> Dict:
        """
        Get IN/OUT statistics for a specific player using play-by-play data.

        Args:
            collection_name: Name of the collection
            player_id: Player's ID (idPlayer from JSON)
            date_filter: Optional MongoDB date filter dict with datetime object

        Returns:
            Dictionary with 'in' and 'out' statistics and metadata
        """
        if not self.connection.is_connected():
            print("[BasketballRepository] No connection to MongoDB")
            return {}

        try:
            from .playbyplay_analyzer import PlayByPlayAnalyzer, InOutStatsCalculator

            # Get all games with play-by-play data
            games = self.get_games_with_playbyplay(collection_name, date_filter)

            # Find player's team ID from first appearance
            player_team_id = None
            for game in games:
                boxscore = game.get('BOXSCORE', {})
                teams = boxscore.get('TEAM', [])

                for team in teams:
                    players = team.get('PLAYER', [])
                    for player in players:
                        if player.get('id') == player_id:
                            player_team_id = team.get('id')
                            break
                    if player_team_id:
                        break
                if player_team_id:
                    break

            if not player_team_id:
                print(f"[BasketballRepository] Could not find team for player {player_id}")
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

            for game in games:
                # Default per-game container (to avoid UnboundLocalError in finally)
                game_stats = {}
                game_was_skipped = False

                # Determine if player actually played in this game using BOXSCORE minutes
                def _player_minutes_played(g, pid) -> float:
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

                minutes_played = _player_minutes_played(game, player_id)

                # Determine if the player's team participated in this game
                def _team_participated(g, team_id) -> bool:
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

                team_played = _team_participated(game, player_team_id)

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
                    analyzer = PlayByPlayAnalyzer(game)
                    calculator = InOutStatsCalculator(analyzer)

                    game_stats = calculator.calculate_in_out_stats(player_id, player_team_id)

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
                    print(f"[BasketballRepository] Error analyzing game {game.get('_id')}: {e}")
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
                    print(f"[BasketballRepository] Debug IN/OUT written to {debug_file}")
                except Exception as e:
                    print(f"[BasketballRepository] Error saving debug file: {e}")

            return {
                'in': total_stats_in,
                'out': total_stats_out,
                'player_id': player_id,
                'player_team_id': player_team_id,
                'games_analyzed': games_analyzed
            }

        except PyMongoError as e:
            print(f"[BasketballRepository] Error getting player IN/OUT stats: {e}")
            return {}
