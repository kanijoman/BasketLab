"""Bayesian (Kalman) rating of the teams of a competition: the prior of the matchup that the win probability lives on (issue #567).

Every team has a rating in points per game and a variance (how sure we are of it). A result moves the two teams by the part of the surprise (the margin
minus the expected one: rating gap plus home court) that matches how unsure each one was, so a team with few games moves a lot and a well-known one little;
after each game every variance grows a little, so the rating follows a team that changes during the season. The home court is learnt from the margins.
The study of 26/10/2026 (docs/evaluaciones/2026-10-26_modelos-de-probabilidad-y-palancas.md) measured it against the season average of the net rating:
log loss 0.4105 -> 0.4070 with the model calibrated per family of competitions. Standard library only, O(1) per game.
"""

from __future__ import annotations

from typing import Dict

P0 = 60.0             # variance (points per game squared) of a team never seen: about +-8 points
Q_GAME = 0.3          # variance added to a team after each of its games: the season moves
NOISE = 144.0         # variance of the margin of one game around its expectation (12 points)
HOME_PRIOR = 3.0      # home court (points) before any result is known
HOME_WEIGHT = 20      # the home court prior counts as this many games
DEFAULT_PACE = 70.0   # possessions per 40 minutes when the pace of the matchup is not known


class TeamRatings:
    def __init__(self) -> None:
        self._mean: Dict[str, float] = {}
        self._var: Dict[str, float] = {}
        self._home_sum, self._home_n = HOME_PRIOR * HOME_WEIGHT, HOME_WEIGHT

    def rating(self, team: str) -> float:
        """Points per game above the average team of the competition (0 for a team never seen)."""
        return self._mean.get(str(team), 0.0)

    def home_advantage(self) -> float:
        return self._home_sum / self._home_n

    def update(self, home: str, away: str, margin: float) -> None:
        """One result: ``margin`` = points of the home team minus points of the away team."""
        home, away = str(home), str(away)
        for team in (home, away):
            self._mean.setdefault(team, 0.0)
            self._var.setdefault(team, P0)
        surprise = margin - (self._mean[home] - self._mean[away] + self.home_advantage())
        spread = self._var[home] + self._var[away] + NOISE
        gain_home, gain_away = self._var[home] / spread, self._var[away] / spread
        self._mean[home] += gain_home * surprise
        self._mean[away] -= gain_away * surprise
        self._var[home] = self._var[home] * (1 - gain_home) + Q_GAME
        self._var[away] = self._var[away] * (1 - gain_away) + Q_GAME
        self._home_sum, self._home_n = self._home_sum + margin, self._home_n + 1

    def gap_per_100(self, own: str, rival: str, pace: float) -> float:
        """Expected margin of ``own`` against ``rival`` on a neutral court, per 100 possessions (the unit of ``net_rtg_prior``)."""
        per_game = self.rating(own) - self.rating(rival)
        return per_game * 100.0 / (pace if pace and pace > 0 else DEFAULT_PACE)
