"""The «two players together» analysis is gone (#200): nothing in the repository called it (the web uses ``getInOutAnalysis`` for each player) and the API it was served by
is only kept for development. The chain behind it (the individual stats with a teammate, the helper mixin and the repository helper only they used) went with it, so it
is not characterized and kept alive for nobody."""
import importlib.util

import pytest

from src.api.app import app
from src.database import MongoDBHandler
from src.database.repository_inout import InOutRepositoryMixin
from src.services.player_stats_service import PlayerStatsService
from tests.api_routes import api_operations

REMOVED_METHODS = ("get_two_players_together_stats", "get_player_individual_stats_with_teammate", "_process_game_with_teammate",
                   "get_players_together", "get_player_with_teammate")


@pytest.mark.parametrize("owner", [InOutRepositoryMixin, MongoDBHandler, PlayerStatsService])
def test_the_together_and_teammate_methods_are_gone(owner):
    assert not [name for name in REMOVED_METHODS if hasattr(owner, name)]


def test_the_together_endpoint_is_gone():
    assert not [path for _, path in api_operations(app) if "together" in path]      # from the OpenAPI schema: app.routes is nested in the FastAPI of the CI


@pytest.mark.parametrize("module", ["src.database._inout_helpers_mixin", "src.database.inout_repository_helper"])
def test_the_helpers_only_that_chain_used_are_gone(module):
    assert importlib.util.find_spec(module) is None


def test_the_player_in_out_stats_that_the_web_publishes_are_still_there():
    assert callable(InOutRepositoryMixin.get_player_in_out_stats)
