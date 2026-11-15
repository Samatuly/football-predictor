"""Модель Elo -> Пуассон (перенос scripts/m.py) с калибруемыми параметрами.

1. dr = elo_scale * (Elo_дом - Elo_гости) + home_adv (на нейтральном поле home_adv = 0).
2. We = 1 / (1 + 10^(-dr/400)) — ожидаемый результат Elo.
3. Тотал T = base_total + total_slope * |dr|.
4. T делится на λ_дом и λ_гости так, чтобы P(П1) + P(Х)/2 = We (бисекция),
   с поправкой низких счетов draw_delta (0-0 и 1-1 вверх, 1-0 и 0-1 вниз).

Параметры по умолчанию — исходные из отчёта 13.11 (scripts/m.py).
Откалиброванные — CALIBRATED (подобраны на 1990–2009, проверены на 2010–2026).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from ..scoregrid import ScoreGrid

NAME = "elo_poisson"
VALIDATED = True  # walk-forward бэктест 2010–2026 на матчах сборных; с рынком не сравнивалась

ASSUMPTIONS = (
    "Рейтинг Elo сборных отражает силу команды на дату матча",
    "Голы команд — Пуассоны с поправкой низких счетов",
    "Параметры подобраны на матчах сборных 1990–2009; к клубам не переносятся",
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
# Заполняется по итогам core/calibrate_cli.py
# base_total/total_slope — из калибровки рынков голов (2026-11-13_totals_calibration.md)
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
