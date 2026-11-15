"""Пошаговый (walk-forward) Elo для сборных.

Рейтинги на дату матча считаются только по матчам, сыгранным раньше: сначала прогноз,
потом обновление. Поэтому утечки будущего нет по построению.

Формула в стиле World Football Elo (eloratings.net): K зависит от турнира, множитель
за разницу мячей, +100 хозяевам. Коэффициенты K и множитель — по памяти, не сверены
с первоисточником (метка: unverified). Это НЕ точная копия рейтингов eloratings.net.
"""
from __future__ import annotations

from collections import defaultdict

from .data.results import Match

START = 1500.0
HOME_ADV = 100.0


def k_factor(tournament: str) -> float:
    t = tournament.lower()
    if t == "fifa world cup":
        return 60.0
    if "qualification" in t:
        return 40.0
    if t in {"uefa euro", "copa américa", "african cup of nations", "afc asian cup",
             "gold cup", "confederations cup", "uefa nations league", "concacaf nations league"}:
        return 50.0
    if t == "friendly":
        return 20.0
    return 30.0


def goal_multiplier(diff: int) -> float:
    d = abs(diff)
    if d <= 1:
        return 1.0
    if d == 2:
        return 1.5
    return 1.75 + (d - 3) / 8


class EloBook:
    def __init__(self) -> None:
        self.rating: dict[str, float] = defaultdict(lambda: START)
        self.games: dict[str, int] = defaultdict(int)

    def pre_match(self, m: Match) -> tuple[float, float]:
        """Рейтинги ДО матча."""
        return self.rating[m.home], self.rating[m.away]

    def update(self, m: Match) -> None:
        rh, ra = self.rating[m.home], self.rating[m.away]
        dr = rh + (0 if m.neutral else HOME_ADV) - ra
        we = 1 / (1 + 10 ** (-dr / 400))
        w = (1.0, 0.5, 0.0)[m.outcome]
        delta = k_factor(m.tournament) * goal_multiplier(m.home_goals - m.away_goals) * (w - we)
        self.rating[m.home] = rh + delta
        self.rating[m.away] = ra - delta
        self.games[m.home] += 1
        self.games[m.away] += 1
