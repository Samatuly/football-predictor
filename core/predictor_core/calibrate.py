"""Fit elo_poisson parameters on the training window and evaluate on the test window.

Elo ratings are computed once, step by step (EloBook); they do not depend on model parameters,
so the fit cannot peek at the test window through the ratings.
The fit objective is the mean 1X2 log-loss on the training window.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date

from .data.results import Match
from .metrics import calibration, summarize
from .models import elo_poisson
from .models.elo_poisson import EloPoissonParams
from .ratings_elo import EloBook

Row = tuple[float, bool, int, int]  # (Elo_home - Elo_away, neutral venue, outcome, goals)


def collect(matches: list[Match], start: date, end: date | None, min_games: int = 30) -> list[Row]:
    book = EloBook()
    rows: list[Row] = []
    for m in matches:
        if (m.date >= start and (end is None or m.date <= end)
                and book.games[m.home] >= min_games and book.games[m.away] >= min_games):
            rh, ra = book.pre_match(m)
            rows.append((rh - ra, m.neutral, m.outcome, m.home_goals + m.away_goals))
        book.update(m)
    return rows


def _probs_table(rows: list[Row], p: EloPoissonParams, fast: bool) -> dict:
    """Forecast cache keyed by (rounded Elo difference, neutral venue)."""
    cache: dict[tuple[int, bool], tuple[tuple[float, float, float], float]] = {}
    kw = {"iters": 30, "max_goals": 8} if fast else {}
    for diff, neutral, _, _ in rows:
        key = (round(diff / 5) * 5 if fast else round(diff), neutral)
        if key not in cache:
            r = elo_poisson.predict(key[0], 0, neutral=neutral, params=p, **kw)
            cache[key] = (r["grid"].outcome(), r["total"])
    return cache


def evaluate(rows: list[Row], p: EloPoissonParams, fast: bool = False) -> dict:
    cache = _probs_table(rows, p, fast)
    scored, goals_pred = [], 0.0
    for diff, neutral, outcome, _ in rows:
        probs, total = cache[(round(diff / 5) * 5 if fast else round(diff), neutral)]
        scored.append((probs, outcome))
        goals_pred += total
    n = len(rows)
    s = summarize(scored)
    s["goals_pred"] = goals_pred / n
    s["goals_actual"] = sum(r[3] for r in rows) / n
    s["draws_pred"] = sum(p_[1] for p_, _ in scored) / n
    s["draws_actual"] = sum(1 for _, o in scored if o == 1) / n
    s["_scored"] = scored
    return s


GRID = {
    "home_adv": [40, 60, 80, 100, 120],
    "elo_scale": [0.7, 0.8, 0.9, 1.0, 1.1],
    "draw_delta": [0.0, 0.05, 0.1, 0.15, 0.2, 0.25],
    "base_total": [2.3, 2.4, 2.5, 2.6, 2.7],
    "total_slope": [0.0, 0.0006, 0.0012, 0.0018],
}


def fit(rows: list[Row], start: EloPoissonParams = EloPoissonParams(), rounds: int = 3,
        log=print) -> EloPoissonParams:
    """Coordinate-wise search over the GRID (several passes)."""
    best, best_ll = start, evaluate(rows, start, fast=True)["log_loss"]
    log(f"start: log-loss {best_ll:.4f} {best.as_dict()}")
    for r in range(rounds):
        improved = False
        for name, values in GRID.items():
            for v in values:
                cand = replace(best, **{name: v})
                ll = evaluate(rows, cand, fast=True)["log_loss"]
                if ll < best_ll - 1e-6:
                    best, best_ll, improved = cand, ll, True
            log(f"pass {r + 1}, {name}: log-loss {best_ll:.4f} {best.as_dict()}")
        if not improved:
            break
    return best


def calibration_table(scored, outcome: int):
    return calibration(scored, outcome)
