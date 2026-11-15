"""Walk-forward comparison of elo_poisson and dixon_coles on the same matches.

Dixon–Coles is refitted every refit_days days using only matches before the fit date;
a match is scored with the latest fit made no later than its date.
The match set is the same as in the Elo backtest: both teams played >= min_games matches.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from .data.results import Match
from .markets import markets
from .metrics import calibration, summarize
from .models import dixon_coles as dc
from .models import elo_poisson as ep
from .ratings_elo import EloBook

GOAL_LINES = {
    "over_1.5": lambda h, a: h + a > 1,
    "over_2.5": lambda h, a: h + a > 2,
    "over_3.5": lambda h, a: h + a > 3,
    "btts_yes": lambda h, a: h > 0 and a > 0,
}


def _bll(p: float, y: bool) -> float:
    p = min(max(p, 1e-12), 1 - 1e-12)
    return -math.log(p if y else 1 - p)


def run(matches: list[Match], start: date, end: date | None, cfg: dc.DCConfig,
        refit_days: int = 30, min_games: int = 30, log=print) -> dict:
    book = EloBook()
    models = ("elo_poisson", "dixon_coles")
    rows = {m: [] for m in models}
    goal_ll = {m: {k: 0.0 for k in GOAL_LINES} for m in models}
    goal_pred = {m: {k: 0.0 for k in GOAL_LINES} for m in models}
    goal_act = {k: 0 for k in GOAL_LINES}
    exp_goals = {m: 0.0 for m in models}
    act_goals = 0
    skipped = 0
    fit: dc.DCFit | None = None
    next_refit = start
    for m in matches:
        in_win = m.date >= start and (end is None or m.date <= end)
        if in_win and m.date >= next_refit:
            fit = dc.fit(matches, m.date, cfg)
            next_refit = m.date + timedelta(days=refit_days)
            log(f"  fit on {m.date}: {fit.n_matches} matches, {len(fit.teams)} teams, ρ={fit.rho:+.2f}, home={fit.home:+.2f}")
        if (in_win and book.games[m.home] >= min_games and book.games[m.away] >= min_games):
            if fit is None or not (fit.has(m.home) and fit.has(m.away)):
                skipped += 1
            else:
                rh, ra = book.pre_match(m)
                grids = {
                    "elo_poisson": ep.predict(rh, ra, neutral=m.neutral, params=ep.CALIBRATED)["grid"],
                    "dixon_coles": fit.grid(m.home, m.away, m.neutral),
                }
                for name, g in grids.items():
                    rows[name].append((g.outcome(), m.outcome))
                    mk = markets(g)
                    for k, f in GOAL_LINES.items():
                        goal_ll[name][k] += _bll(mk[k], f(m.home_goals, m.away_goals))
                        goal_pred[name][k] += mk[k]
                    exp_goals[name] += g.lam_home + g.lam_away
                for k, f in GOAL_LINES.items():
                    goal_act[k] += 1 if f(m.home_goals, m.away_goals) else 0
                act_goals += m.home_goals + m.away_goals
        book.update(m)

    n = len(rows["elo_poisson"])
    out = {"n": n, "skipped_no_fit": skipped, "config": cfg.__dict__}
    for name in models:
        out[name] = {
            "1x2": summarize(rows[name]),
            "goal_log_loss": {k: v / n for k, v in goal_ll[name].items()},
            "goal_log_loss_sum": sum(goal_ll[name].values()) / n,
            "goal_pred_rate": {k: v / n for k, v in goal_pred[name].items()},
            "expected_goals": exp_goals[name] / n,
            "draw_pred": sum(p[1] for p, _ in rows[name]) / n,
            "calibration_1": calibration(rows[name], 0),
        }
    out["actual"] = {"goal_rate": {k: v / n for k, v in goal_act.items()}, "goals": act_goals / n,
                     "draws": sum(1 for _, o in rows["elo_poisson"] if o == 1) / n}
    return out
