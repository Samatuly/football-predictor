"""Модель Диксона–Коулза (Dixon & Coles, 1997) с затуханием по времени.

    log λ_дом   = μ + h·[не нейтральное поле] + att[дом]   − def[гости]
    log λ_гости = μ +                          att[гости] − def[дом]
    P(x, y) = τ(x, y; λ, μ_, ρ) · Poisson(x; λ) · Poisson(y; μ_)

τ — поправка низких счетов из статьи DC: τ(0,0)=1−λμρ, τ(0,1)=1+λρ, τ(1,0)=1+μρ, τ(1,1)=1−ρ.
Вес матча: exp(−ln2 · дней_до_даты_подгонки / half_life). L2-регуляризация att/def (ridge).

Подгонка в два шага (стандартное упрощение):
  1. μ, h, att, def — градиентным спуском (Adam) по взвешенному правдоподобию Пуассона;
  2. ρ — одномерным поиском по взвешенному правдоподобию с τ.

Идея затухания и регуляризации — по Mintahandrews/football-predictor (MIT, TypeScript);
код написан заново на Python/numpy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np

from ..data.results import Match
from ..scoregrid import ScoreGrid, poisson_pmf

NAME = "dixon_coles"


@dataclass(frozen=True)
class DCConfig:
    half_life_days: float = 730.0
    window_years: float = 8.0
    ridge: float = 0.05
    iters: int = 400
    lr: float = 0.05


@dataclass
class DCFit:
    as_of: date
    teams: dict[str, int]
    mu: float
    home: float
    att: np.ndarray
    dfn: np.ndarray
    rho: float
    n_matches: int

    def has(self, team: str) -> bool:
        return team in self.teams

    def lambdas(self, home: str, away: str, neutral: bool) -> tuple[float, float]:
        i, j = self.teams[home], self.teams[away]
        lh = math.exp(self.mu + (0 if neutral else self.home) + self.att[i] - self.dfn[j])
        la = math.exp(self.mu + self.att[j] - self.dfn[i])
        return lh, la

    def grid(self, home: str, away: str, neutral: bool, max_goals: int = 10) -> ScoreGrid:
        lh, la = self.lambdas(home, away, neutral)
        return dc_grid(lh, la, self.rho, max_goals)


def dc_grid(lh: float, la: float, rho: float, max_goals: int = 10) -> ScoreGrid:
    ph = [poisson_pmf(lh, i) for i in range(max_goals + 1)]
    pa = [poisson_pmf(la, j) for j in range(max_goals + 1)]
    g = [[ph[i] * pa[j] for j in range(max_goals + 1)] for i in range(max_goals + 1)]
    g[0][0] *= max(1 - lh * la * rho, 1e-9)
    g[0][1] *= max(1 + lh * rho, 1e-9)
    g[1][0] *= max(1 + la * rho, 1e-9)
    g[1][1] *= max(1 - rho, 1e-9)
    s = sum(map(sum, g))
    return ScoreGrid(lh, la, tuple(tuple(x / s for x in row) for row in g))


def fit(matches: list[Match], as_of: date, cfg: DCConfig = DCConfig()) -> DCFit:
    """Подгонка только по матчам строго ДО as_of (без утечки будущего)."""
    lo = as_of.toordinal() - int(cfg.window_years * 365.25)
    rows = [m for m in matches if lo <= m.date.toordinal() < as_of.toordinal()]
    teams: dict[str, int] = {}
    for m in rows:
        for t in (m.home, m.away):
            teams.setdefault(t, len(teams))
    n_t = len(teams)
    hi = np.array([teams[m.home] for m in rows])
    ai = np.array([teams[m.away] for m in rows])
    hg = np.array([m.home_goals for m in rows], dtype=float)
    ag = np.array([m.away_goals for m in rows], dtype=float)
    nh = np.array([0.0 if m.neutral else 1.0 for m in rows])
    days = as_of.toordinal() - np.array([m.date.toordinal() for m in rows], dtype=float)
    w = np.exp(-math.log(2) * days / cfg.half_life_days)
    w = w / w.sum() * len(rows)

    # параметры: [mu, home, att(n_t), def(n_t)]
    theta = np.zeros(2 + 2 * n_t)
    theta[0] = math.log(max(float((hg.sum() + ag.sum()) / (2 * len(rows))), 0.1))
    m1 = np.zeros_like(theta)
    v1 = np.zeros_like(theta)
    b1, b2, eps = 0.9, 0.999, 1e-8
    n = len(rows)
    for t in range(1, cfg.iters + 1):
        mu, h = theta[0], theta[1]
        att, dfn = theta[2:2 + n_t], theta[2 + n_t:]
        lh = np.exp(mu + h * nh + att[hi] - dfn[ai])
        la = np.exp(mu + att[ai] - dfn[hi])
        rh = w * (hg - lh)  # d logL / d log λ_дом
        ra = w * (ag - la)
        g = np.zeros_like(theta)
        g[0] = rh.sum() + ra.sum()
        g[1] = (rh * nh).sum()
        g_att = np.bincount(hi, rh, n_t) + np.bincount(ai, ra, n_t)
        g_def = -np.bincount(ai, rh, n_t) - np.bincount(hi, ra, n_t)
        g[2:2 + n_t] = g_att - cfg.ridge * n * att / n_t
        g[2 + n_t:] = g_def - cfg.ridge * n * dfn / n_t
        g = -g / n  # минимизируем −logL/n
        m1 = b1 * m1 + (1 - b1) * g
        v1 = b2 * v1 + (1 - b2) * g * g
        theta -= cfg.lr * (m1 / (1 - b1**t)) / (np.sqrt(v1 / (1 - b2**t)) + eps)
        # идентифицируемость: средние att и def = 0
        theta[2:2 + n_t] -= theta[2:2 + n_t].mean()
        theta[2 + n_t:] -= theta[2 + n_t:].mean()

    mu, h = float(theta[0]), float(theta[1])
    att, dfn = theta[2:2 + n_t].copy(), theta[2 + n_t:].copy()
    lh = np.exp(mu + h * nh + att[hi] - dfn[ai])
    la = np.exp(mu + att[ai] - dfn[hi])
    rho = _fit_rho(lh, la, hg, ag, w)
    return DCFit(as_of, teams, mu, h, att, dfn, rho, n)


def _fit_rho(lh, la, hg, ag, w) -> float:
    low = (hg <= 1) & (ag <= 1)
    lh, la, hg, ag, w = lh[low], la[low], hg[low], ag[low], w[low]
    best, best_ll = 0.0, -math.inf
    for rho in np.arange(-0.30, 0.31, 0.01):
        tau = np.where((hg == 0) & (ag == 0), 1 - lh * la * rho,
              np.where((hg == 0) & (ag == 1), 1 + lh * rho,
              np.where((hg == 1) & (ag == 0), 1 + la * rho, 1 - rho)))
        if (tau <= 0).any():
            continue
        ll = float((w * np.log(tau)).sum())
        if ll > best_ll:
            best, best_ll = float(rho), ll
    return best
