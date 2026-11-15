"""Scoreline probability matrix from two independent Poissons."""
from __future__ import annotations

import math
from dataclasses import dataclass

MAX_GOALS = 10  # P(k > 10) is negligible for λ <= 4


def poisson_pmf(lam: float, k: int) -> float:
    return math.exp(-lam) * lam**k / math.factorial(k)


@dataclass(frozen=True)
class ScoreGrid:
    """grid[i][j] = P(home scored i, away scored j)."""

    lam_home: float
    lam_away: float
    grid: tuple[tuple[float, ...], ...]

    @classmethod
    def poisson(cls, lam_home: float, lam_away: float, max_goals: int = MAX_GOALS) -> "ScoreGrid":
        ph = [poisson_pmf(lam_home, i) for i in range(max_goals + 1)]
        pa = [poisson_pmf(lam_away, j) for j in range(max_goals + 1)]
        g = tuple(tuple(ph[i] * pa[j] for j in range(max_goals + 1)) for i in range(max_goals + 1))
        return cls(lam_home, lam_away, g)

    def with_low_score_boost(self, delta: float) -> "ScoreGrid":
        """Dixon–Coles-style correction: 0-0 and 1-1 × (1+δ), 1-0 and 0-1 × (1-δ), then renormalise.

        δ > 0 raises the share of draws, which independent Poissons underestimate.
        """
        if delta == 0:
            return self
        g = [list(r) for r in self.grid]
        g[0][0] *= 1 + delta
        g[1][1] *= 1 + delta
        g[1][0] *= 1 - delta
        g[0][1] *= 1 - delta
        s = sum(map(sum, g))
        return ScoreGrid(self.lam_home, self.lam_away, tuple(tuple(x / s for x in r) for r in g))

    def prob(self, cond) -> float:
        n = len(self.grid)
        return sum(self.grid[i][j] for i in range(n) for j in range(n) if cond(i, j))

    def outcome(self) -> tuple[float, float, float]:
        """(home win, draw, away win)."""
        return (self.prob(lambda i, j: i > j), self.prob(lambda i, j: i == j), self.prob(lambda i, j: i < j))

    def top_scores(self, k: int = 3) -> list[tuple[str, float]]:
        n = len(self.grid)
        cells = sorted(((self.grid[i][j], f"{i}-{j}") for i in range(n) for j in range(n)), reverse=True)
        return [(s, p) for p, s in cells[:k]]
