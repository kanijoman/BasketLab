"""Lineup analysis repository mixin."""

from typing import Dict, List, Optional, FrozenSet
from pymongo.errors import PyMongoError

from utils.collection_utils import is_fbcyl as _is_fbcyl


class LineupRepositoryMixin:
    """Mixin providing lineup analysis query methods."""

    def get_lineup_analysis(
        self,
        collection_name: str,
        team_id: str,
        team_name: str,
        combination_size: int = 5,
        date_filter: Dict = None,
        is_fbcyl: bool = False,
        include_game_log: bool = False,
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
            # Define a projection to avoid loading large BOXSCORE/stats.players fields —
            # the lineup extractor only needs play-by-play data + team/date metadata.
            if is_fbcyl:
                projection = {"moves": 1, "stats.teams": 1, "stats.time": 1}
            else:
                projection = {"PLAYBYPLAY": 1, "HEADER": 1}

            # Get all games with play-by-play for this team; apply date filter and
            # projection inside MongoDB to avoid Python-side filtering and memory waste.
            games = self.get_games_for_team(
                collection_name,
                team_id,
                only_with_playbyplay=True,
                projection=projection,
                date_filter=date_filter if date_filter else None,
            )

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

                    # Extract game date once per game (used for game_log)
                    if is_fbcyl:
                        # Date is in stats.time: 'Mar 1, 2026 1:00:00 PM'
                        # Convert to ISO YYYY-MM-DD for consistent sorting in the chart.
                        raw_time = game.get('stats', {}).get('time', '')
                        game_date = self._parse_fbcyl_date(raw_time)
                    else:
                        game_date = game.get('HEADER', {}).get('starttime', '').split(' - ')[0]

                    # Initialize analyzers
                    analyzer = PlayByPlayAnalyzer(game, is_fbcyl)
                    extractor = LineupExtractor(analyzer)
                    calculator = LineupStatsCalculator(analyzer)

                    # FBCYL: moves use teamIdIntern, but team_id is teamIdExtern — resolve
                    effective_team_id = (
                        self._resolve_fbcyl_team_id(game, team_id) if is_fbcyl else team_id
                    )

                    # Get all lineup combinations for this game (NO minimum threshold per game)
                    lineup_times = extractor.get_lineup_combinations(
                        effective_team_id,
                        combination_size,
                        min_seconds=0  # Detect ALL lineups, filter later by total time
                    )

                    # Calculate stats for each lineup in this game
                    for lineup_key, time_seconds in lineup_times.items():
                        lineup_stats = calculator.calculate_lineup_stats_single_game(
                            analyzer,
                            extractor,
                            effective_team_id,
                            lineup_key
                        )

                        # Build per-game log entry before merging (data would be lost after)
                        if include_game_log:
                            game_entry = {
                                'date':          game_date,
                                'net_rating':    lineup_stats.get('net_rating', 0),
                                'ortg':          lineup_stats.get('ortg', 0),
                                'drtg':          lineup_stats.get('drtg', 0),
                                'plus_minus':    lineup_stats.get('plus_minus', 0),
                                'points_for':    lineup_stats.get('points_for', 0),
                                'points_against': lineup_stats.get('points_against', 0),
                                'efg_pct':       lineup_stats.get('efg_pct', 0),
                                'tov_pct':       lineup_stats.get('tov_pct', 0),
                                'orb_pct':       lineup_stats.get('orb_pct', 0),
                                'ftr':           lineup_stats.get('ftr', 0),
                                'ast':           lineup_stats.get('ast', 0),
                                'trb':           lineup_stats.get('trb', 0),
                                'minutes':       lineup_stats.get('minutes', 0),
                            }

                        # Aggregate with existing stats
                        if lineup_key not in lineup_stats_map:
                            # First time seeing this lineup
                            lineup_stats['avg_minutes_per_game'] = lineup_stats.get('minutes', 0)
                            if include_game_log:
                                lineup_stats['game_log'] = [game_entry]
                            lineup_stats_map[lineup_key] = lineup_stats
                        else:
                            # Merge stats from this game
                            existing = lineup_stats_map[lineup_key]
                            self._merge_lineup_stats(existing, lineup_stats)
                            if include_game_log:
                                existing.setdefault('game_log', []).append(game_entry)

                except Exception as e:
                    # Skip games with errors (e.g., incomplete play-by-play)
                    print(f"Error processing game for lineup analysis: {e}")
                    continue

            # Convert to list and add player names
            # Filter by total accumulated time and games played for representative lineups
            qualifying = []
            all_player_ids: set = set()
            min_total_minutes = 15  # 15 minutes minimum total
            min_games_played = 5    # At least 5 games
            
            for lineup_key, stats in lineup_stats_map.items():
                total_minutes = stats.get('minutes', 0)
                games_played = stats.get('games_played', 0)
                
                # Skip lineups that don't meet minimum thresholds
                if total_minutes < min_total_minutes or games_played < min_games_played:
                    continue

                qualifying.append((lineup_key, stats))
                all_player_ids.update(lineup_key)

            # Bulk-load ALL player names in a single DB query
            player_name_map = self._bulk_load_player_names(
                collection_name, list(all_player_ids), is_fbcyl
            )

            lineup_list = []
            for lineup_key, stats in qualifying:
                player_names = []
                player_photo_urls = []
                for pid in lineup_key:
                    name, photo = player_name_map.get(str(pid), (f"Player {pid}", None))
                    player_names.append(name)
                    player_photo_urls.append(photo)

                stats['player_names'] = player_names
                stats['players'] = player_names  # overwrite frozenset set by calculator
                stats['player_ids'] = list(lineup_key)
                stats['player_photo_urls'] = player_photo_urls
                lineup_list.append(stats)

            # Sort by net rating (descending)
            lineup_list.sort(key=lambda x: x.get('net_rating', 0), reverse=True)

            return lineup_list

        except PyMongoError as e:
            print(f"MongoDB error in get_lineup_analysis: {e}")
            return []

    def _parse_fbcyl_date(self, raw_time: str) -> str:
        """Parse FBCYL stats.time field to ISO YYYY-MM-DD string.

        FBCYL stores the game datetime as e.g. ``'Mar 1, 2026 1:00:00 PM'``.
        Returns ``''`` if parsing fails.
        """
        if not raw_time:
            return ''
        try:
            from datetime import datetime
            dt = datetime.strptime(raw_time.strip(), "%b %d, %Y %I:%M:%S %p")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            # Try without leading-zero padding for single-digit days
            try:
                from datetime import datetime
                dt = datetime.strptime(raw_time.strip(), "%B %d, %Y %I:%M:%S %p")
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                return raw_time[:10]  # best-effort: return first 10 chars

    def _resolve_fbcyl_team_id(self, game: Dict, team_id_extern: str) -> str:
        """Resolve FBCYL teamIdExtern to teamIdIntern for PBP analysis.

        moves[].idTeam stores teamIdIntern (game-scoped internal ID), not the
        persistent teamIdExtern that the rest of the API uses.  We look up the
        mapping in the current game document.
        """
        try:
            target = int(team_id_extern)
        except (ValueError, TypeError):
            target = team_id_extern

        for team in game.get('stats', {}).get('teams', []):
            extern = team.get('teamIdExtern')
            if extern == target or str(extern) == str(team_id_extern):
                intern = team.get('teamIdIntern')
                if intern is not None:
                    return str(intern)
        return team_id_extern  # fallback: no conversion found

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
    ) -> tuple:
        """Return (names, photo_urls) lists aligned with lineup_keys iteration order.

        For FEB collections the photo URL is taken directly from the ``logo``
        field stored in ``BOXSCORE.TEAM.PLAYER`` (e.g.
        ``https://imagenes.feb.es/foto.aspx?c={player_id}``).

        For FBCYL collections there is no CDN URL that reliably works, so
        ``photo_urls`` will be a list of ``None`` values — the frontend falls
        back to coloured-initials avatars.
        """
        names: List[str] = []
        photo_urls: List[Optional[str]] = []
        player_ids_list = list(lineup_keys)

        try:
            collection = self.connection.get_collection(collection_name)

            # Normalise IDs to str for consistent map key lookups
            player_ids_str = [str(pid) for pid in player_ids_list]

            if is_fbcyl:
                # ---------------------------------------------------------
                # FBCYL: lineup keys are licenseId strings (persistent IDs).
                # Name is in moves[].actorName.  No reliable photo CDN.
                # ---------------------------------------------------------
                player_ids_int = [
                    int(pid) if str(pid).isdigit() else pid
                    for pid in player_ids_list
                ]

                player_map: Dict[str, str] = {}
                for game in collection.find(
                    {"moves.licenseId": {"$in": player_ids_int}},
                    {"moves": 1},
                    limit=10
                ):
                    for move in game.get('moves', []):
                        lid = str(move.get('licenseId', ''))
                        if lid in player_ids_str and lid not in player_map:
                            player_map[lid] = move.get('actorName', 'Unknown')
                    if len(player_map) == len(player_ids_str):
                        break

                for pid in player_ids_str:
                    names.append(player_map.get(pid, f"Player {pid}"))
                    photo_urls.append(None)  # No CDN for FBCYL

            else:
                # ---------------------------------------------------------
                # FEB: lineup keys are player id strings.
                # Name and logo URL both live in BOXSCORE.TEAM.PLAYER[].
                # ---------------------------------------------------------
                player_ids_mixed = []
                for pid in player_ids_list:
                    player_ids_mixed.append(pid)
                    try:
                        player_ids_mixed.append(int(pid))
                    except (ValueError, TypeError):
                        pass

                game = collection.find_one(
                    {"BOXSCORE.TEAM.PLAYER.id": {"$in": player_ids_mixed}},
                    {"BOXSCORE.TEAM.PLAYER": 1}
                )

                if game:
                    name_map: Dict[str, str] = {}
                    logo_map: Dict[str, Optional[str]] = {}
                    for team in game.get('BOXSCORE', {}).get('TEAM', []):
                        for player in team.get('PLAYER', []):
                            pid_str = str(player.get('id', ''))
                            if pid_str in player_ids_str:
                                name_map[pid_str] = player.get('name', 'Unknown')
                                logo = player.get('logo', '')
                                logo_map[pid_str] = logo if logo and logo.startswith('http') else None

                    for pid in player_ids_str:
                        names.append(name_map.get(pid, f"Player {pid}"))
                        photo_urls.append(logo_map.get(pid))
                else:
                    names = [f"Player {pid}" for pid in player_ids_str]
                    photo_urls = [None] * len(player_ids_str)

        except Exception as e:
            print(f"Error getting player names: {e}")
            names = [f"Player {pid}" for pid in player_ids_list]
            photo_urls = [None] * len(player_ids_list)

        return names, photo_urls

    def _bulk_load_player_names(
        self,
        collection_name: str,
        player_ids: List[str],
        is_fbcyl: bool,
    ) -> Dict[str, tuple]:
        """Return a mapping ``{player_id_str: (name, photo_url)}`` for all *player_ids*.

        Resolves ALL requested IDs in a single MongoDB query, replacing the
        previous N+1 pattern where ``_get_player_names_for_lineup`` was called
        once per qualifying lineup.

        Args:
            collection_name: MongoDB collection name.
            player_ids: List of player ID strings to look up.
            is_fbcyl: True for FBCYL format, False for FEB.

        Returns:
            Dict mapping each player ID string to a ``(name, photo_url)`` tuple.
            Unknown IDs get a fallback ``("Player {id}", None)`` entry.
        """
        result: Dict[str, tuple] = {}
        if not player_ids:
            return result

        try:
            collection = self.connection.get_collection(collection_name)
            ids_str = [str(pid) for pid in player_ids]

            if is_fbcyl:
                ids_int = [int(pid) for pid in ids_str if pid.isdigit()]
                ids_to_search = ids_int if ids_int else ids_str
                for doc in collection.find(
                    {"moves.licenseId": {"$in": ids_to_search}},
                    {"moves": 1},
                ):
                    for move in doc.get("moves", []):
                        lid = str(move.get("licenseId", ""))
                        if lid in ids_str and lid not in result:
                            result[lid] = (move.get("actorName", f"Player {lid}"), None)
                    if len(result) == len(ids_str):
                        break
            else:
                ids_mixed = []
                for pid in player_ids:
                    ids_mixed.append(pid)
                    try:
                        ids_mixed.append(int(pid))
                    except (ValueError, TypeError):
                        pass
                for doc in collection.find(
                    {"BOXSCORE.TEAM.PLAYER.id": {"$in": ids_mixed}},
                    {"BOXSCORE.TEAM.PLAYER": 1},
                ):
                    for team in doc.get("BOXSCORE", {}).get("TEAM", []):
                        for player in team.get("PLAYER", []):
                            pid_str = str(player.get("id", ""))
                            if pid_str in ids_str and pid_str not in result:
                                logo = player.get("logo", "")
                                photo = logo if logo and logo.startswith("http") else None
                                result[pid_str] = (player.get("name", f"Player {pid_str}"), photo)
                    if len(result) == len(ids_str):
                        break

        except Exception as e:
            print(f"Error in _bulk_load_player_names: {e}")

        # Fill in fallbacks for any IDs not found
        for pid in ids_str:
            if pid not in result:
                result[pid] = (f"Player {pid}", None)

        return result
