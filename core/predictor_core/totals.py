"""Калибровка рынков голов (ТБ/ТМ 1.5/2.5/3.5, «обе забьют»).

Параметры 1X2 (home_adv, elo_scale, draw_delta) фиксированы — их уже подобрали по 1X2.
Подбираются только base_total и total_slope. Цель — сумма бинарных log-loss по четырём
рынкам голов на обучающем окне. После подбора проверяется, что 1X2 на тесте не ухудшился.
"""
from __future__ import annotations

import math
from dataclasses import replace
from datetime import date

from .data.results import Match
from .markets import markets
from .metrics import log_loss
from .models import elo_poisson
from .models.elo_poisson import EloPoissonParams
from .ratings_elo import EloBook

GoalRow = tuple[float, bool, int, int]  # (Elo_дом - Elo_гости, нейтральное, голы хозяев, голы гостей)

LINES = {
    "over_1.5": lambda h, a: h + a > 1,
    "over_2.5": lambda h, a: h + a > 2,
    "over_3.5": lambda h, a: h + a > 3,
    "btts_yes": lambda h, a: h > 0 and a > 0,
}


def collect(matches: list[Match], start: date, end: date | None, min_games: int = 30) -> list[GoalRow]:
    book = EloBook()
    rows: list[GoalRow] = []
    for m in matches:
        if (m.date >= start and (end is None or m.date <= end)
                and book.games[m.home] >= min_games and book.games[m.away] >= min_games):
            rh, ra = book.pre_match(m)
            rows.append((rh - ra, m.neutral, m.home_goals, m.away_goals))
        book.update(m)
    return rows


def _bin_ll(p: float, y: bool) -> float:
    p = min(max(p, 1e-12), 1 - 1e-12)
    return -math.log(p if y else 1 - p)


def evaluate(rows: list[GoalRow], p: EloPoissonParams, fast: bool = False) -> dict:
    kw = {"iters": 30, "max_goals": 9} if fast else {}
    step = 5 if fast else 1
    cache: dict[tuple[int, bool], tuple[dict, tuple, float]] = {}
    ll = {k: 0.0 for k in LINES}
    brier = {k: 0.0 for k in LINES}
    pred_rate = {k: 0.0 for k in LINES}
    act_rate = {k: 0 for k in LINES}
    ll_1x2 = goals_pred = goals_act = 0.0
    calib: dict[str, list[list[float]]] = {k: [[0.0, 0, 0] for _ in range(10)] for k in LINES}
    for diff, neutral, h, a in rows:
        key = (round(diff / step) * step, neutral)
        if key not in cache:
            r = elo_poisson.predict(key[0], 0, neutral=neutral, params=p, **kw)
            cache[key] = (markets(r["grid"]), r["grid"].outcome(), r["total"])
        m, probs, total = cache[key]
        for k, f in LINES.items():
            y = f(h, a)
            ll[k] += _bin_ll(m[k], y)
            brier[k] += (m[k] - (1 if y else 0)) ** 2
            pred_rate[k] += m[k]
            act_rate[k] += 1 if y else 0
            b = calib[k][min(int(m[k] * 10), 9)]
            b[0] += m[k]; b[1] += 1 if y else 0; b[2] += 1
        ll_1x2 += log_loss(probs, 0 if h > a else (1 if h == a else 2))
        goals_pred += total
        goals_act += h + a
    n = len(rows)
    return {
        "n": n,
        "objective": sum(ll.values()) / n,
        "log_loss": {k: v / n for k, v in ll.items()},
        "brier": {k: v / n for k, v in brier.items()},
        "pred_rate": {k: v / n for k, v in pred_rate.items()},
        "actual_rate": {k: v / n for k, v in act_rate.items()},
        "log_loss_1x2": ll_1x2 / n,
        "goals_pred": goals_pred / n,
        "goals_actual": goals_act / n,
        "calibration": {k: [{"bin": f"{i/10:.1f}-{(i+1)/10:.1f}", "n": c, "predicted": s / c, "observed": o / c}
                            for i, (s, o, c) in enumerate(v) if c] for k, v in calib.items()},
    }


def baseline(train: list[GoalRow], test: list[GoalRow]) -> dict:
    """Базовый прогноз: частоты рынков голов на обучающем окне, одинаковые для всех матчей."""
    rates = {k: sum(1 for _, _, h, a in train if f(h, a)) / len(train) for k, f in LINES.items()}
    ll = {k: sum(_bin_ll(rates[k], f(h, a)) for _, _, h, a in test) / len(test) for k, f in LINES.items()}
    return {"rates": rates, "log_loss": ll, "objective": sum(ll.values())}


GRID = {
    "base_total": [round(2.0 + 0.1 * i, 1) for i in range(10)],          # 2.0 … 2.9
    "total_slope": [round(0.0003 * i, 4) for i in range(13)],            # 0 … 0.0036
}


def fit(rows: list[GoalRow], start: EloPoissonParams, rounds: int = 3, log=print) -> EloPoissonParams:
    best, best_obj = start, evaluate(rows, start, fast=True)["objective"]
    log(f"старт: {best_obj:.4f} base_total={best.base_total} total_slope={best.total_slope}")
    for r in range(rounds):
        improved = False
        for name, values in GRID.items():
            for v in values:
                cand = replace(best, **{name: v})
                obj = evaluate(rows, cand, fast=True)["objective"]
                if obj < best_obj - 1e-6:
                    best, best_obj, improved = cand, obj, True
            log(f"проход {r + 1}, {name}: {best_obj:.4f} base_total={best.base_total} total_slope={best.total_slope}")
        if not improved:
            break
    return best
