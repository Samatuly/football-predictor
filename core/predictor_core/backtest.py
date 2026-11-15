"""Walk-forward backtest of 1X2 models on international matches.

For each match in date order:
  1. every model forecasts, seeing only the past;
  2. the forecast is recorded if the match is inside the evaluation window and both teams have >= min_games matches;
  3. only then are ratings and base rates updated with the result.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date

from .data.results import Match
from .metrics import calibration, summarize
from .models import elo_poisson
from .ratings_elo import EloBook

Probs = tuple[float, float, float]


@dataclass
class BaseRates:
    """H/D/A frequencies from past matches, separately for neutral venues and for matches with a home side."""
    counts: dict[bool, list[int]] = field(default_factory=lambda: {True: [1, 1, 1], False: [1, 1, 1]})

    def predict(self, neutral: bool) -> Probs:
        c = self.counts[neutral]
        s = sum(c)
        return (c[0] / s, c[1] / s, c[2] / s)

    def update(self, m: Match) -> None:
        self.counts[m.neutral][m.outcome] += 1


def _elo_poisson(params: elo_poisson.EloPoissonParams) -> Callable[[float, float, bool], tuple[Probs, float]]:
    def f(rh: float, ra: float, neutral: bool) -> tuple[Probs, float]:
        p = elo_poisson.predict(rh, ra, neutral=neutral, params=params)
        return p["grid"].outcome(), p["total"]
    return f


def run(matches: list[Match], start: date, end: date | None = None, min_games: int = 30,
        exclude_friendlies: bool = False, variants: dict | None = None) -> dict:
    variants = variants or {
        "elo_poisson (current: T=2.5+0.0012|dr|)": elo_poisson.EloPoissonParams(),
        "elo_poisson (T=2.6 constant)": elo_poisson.EloPoissonParams(base_total=2.6, total_slope=0.0),
    }
    models = {name: _elo_poisson(p) for name, p in variants.items()}
    book, base = EloBook(), BaseRates()
    rows: dict[str, list[tuple[Probs, int]]] = {n: [] for n in [*models, "base rates", "uniform 1/3"]}
    goals_pred: dict[str, float] = {n: 0.0 for n in models}
    goals_actual = 0
    draws_pred = {n: 0.0 for n in models}

    for m in matches:
        in_window = m.date >= start and (end is None or m.date <= end)
        eligible = (in_window and book.games[m.home] >= min_games and book.games[m.away] >= min_games
                    and not (exclude_friendlies and m.tournament == "Friendly"))
        if eligible:
            rh, ra = book.pre_match(m)
            for name, f in models.items():
                probs, total = f(rh, ra, m.neutral)
                rows[name].append((probs, m.outcome))
                goals_pred[name] += total
                draws_pred[name] += probs[1]
            rows["base rates"].append((base.predict(m.neutral), m.outcome))
            rows["uniform 1/3"].append(((1 / 3, 1 / 3, 1 / 3), m.outcome))
            goals_actual += m.home_goals + m.away_goals
        book.update(m)
        base.update(m)

    n = len(rows["uniform 1/3"])
    first = next(iter(models))
    return {
        "n": n,
        "summary": {name: summarize(r) for name, r in rows.items()},
        "goals": {"actual_mean": goals_actual / n if n else 0,
                  **{name: goals_pred[name] / n if n else 0 for name in models}},
        "draws": {"actual_rate": sum(1 for _, o in rows[first] if o == 1) / n if n else 0,
                  **{name: draws_pred[name] / n if n else 0 for name in models}},
        "calibration": {k: calibration(rows[first], i) for i, k in enumerate(("H", "D", "A"))},
    }
