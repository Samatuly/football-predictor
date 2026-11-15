"""Elo -> Poisson model (ported from scripts/m.py) with calibratable parameters.

1. dr = elo_scale * (Elo_home - Elo_away) + home_adv (home_adv = 0 on a neutral venue).
2. We = 1 / (1 + 10^(-dr/400)) is the Elo expected result.
3. Total T = base_total + total_slope * |dr|.
4. T is split into λ_home and λ_away so that P(home) + P(draw)/2 = We (bisection),
   with the low-score correction draw_delta (0-0 and 1-1 up, 1-0 and 0-1 down).

Default parameters are the original ones from the 13 Nov report (scripts/m.py).
Calibrated parameters are in CALIBRATED (fitted on 1990–2009, tested on 2010–2026).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ..scoregrid import ScoreGrid

NAME = "elo_poisson"
VALIDATED = True  # walk-forward backtest 2010–2026 on international matches; not compared with the market

ASSUMPTIONS = (
    "The Elo rating of a national team reflects its strength on the match date",
    "Team goals are Poisson with a low-score correction",
    "Parameters were fitted on international matches 1990–2009; they do not transfer to clubs",
)


@dataclass(frozen=True)
class EloPoissonParams:
    home_adv: float = 100.0
    base_total: float = 2.5
    total_slope: float = 0.0012
    elo_scale: float = 1.0
    draw_delta: float = 0.0

    def as_dict(self) -> dict:
        return asdict(self)


ORIGINAL = EloPoissonParams()
# Filled in from the results of core/calibrate_cli.py
# base_total/total_slope come from the goal-market calibration (core/calibrate_totals_cli.py)
CALIBRATED = EloPoissonParams(home_adv=100.0, base_total=2.3, total_slope=0.0021,
                              elo_scale=0.8, draw_delta=0.2)


def elo_expectation(dr: float) -> float:
    return 1 / (1 + 10 ** (-dr / 400))


def _grid(total: float, s: float, delta: float, max_goals: int) -> ScoreGrid:
    return ScoreGrid.poisson((total + s) / 2, (total - s) / 2, max_goals).with_low_score_boost(delta)


def predict(elo_home: float, elo_away: float, neutral: bool = False,
            params: EloPoissonParams = ORIGINAL, iters: int = 60, max_goals: int = 10) -> dict:
    dr = params.elo_scale * (elo_home - elo_away) + (0 if neutral else params.home_adv)
    we = elo_expectation(dr)
    total = params.base_total + params.total_slope * abs(dr)

    lo, hi = -total, total
    s = 0.0
    for _ in range(iters):
        s = (lo + hi) / 2
        w, d, _ = _grid(total, s, params.draw_delta, max_goals).outcome()
        if w + d / 2 < we:
            lo = s
        else:
            hi = s
    grid = _grid(total, s, params.draw_delta, max_goals)
    return {"model": NAME, "validated": VALIDATED, "params": params.as_dict(),
            "dr": dr, "we": we, "total": total, "grid": grid}
