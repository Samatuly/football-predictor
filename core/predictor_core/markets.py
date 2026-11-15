"""Betting markets from the scoreline matrix (ported from scripts/mk.py and scripts/ht.py)."""
from __future__ import annotations

from .scoregrid import ScoreGrid, poisson_pmf


def markets(g: ScoreGrid) -> dict[str, float]:
    w, d, l = g.outcome()
    a, b = g.lam_home, g.lam_away
    btts = (1 - poisson_pmf(a, 0)) * (1 - poisson_pmf(b, 0))
    return {
        "1": w, "X": d, "2": l,
        "1X": w + d, "X2": d + l, "12": w + l,
        "over_1.5": g.prob(lambda i, j: i + j > 1),
        "over_2.5": g.prob(lambda i, j: i + j > 2),
        "under_2.5": g.prob(lambda i, j: i + j < 3),
        "under_3.5": g.prob(lambda i, j: i + j < 4),
        "over_3.5": g.prob(lambda i, j: i + j > 3),
        "btts_yes": btts,
        "btts_no": 1 - btts,
        "home_over_0.5": 1 - poisson_pmf(a, 0),
        "away_over_0.5": 1 - poisson_pmf(b, 0),
        "home_over_1.5": 1 - poisson_pmf(a, 0) - poisson_pmf(a, 1),
        "away_over_1.5": 1 - poisson_pmf(b, 0) - poisson_pmf(b, 1),
    }


NOT_EXHAUSTIVE = {"Double chance", "Win to nil"}


def markets_full(g: ScoreGrid) -> dict[str, dict[str, float]]:
    """Extended set of full-time markets, all derived from the scoreline matrix (including the DC correction).

    Groups are complete sets of mutually exclusive outcomes (needed for margin removal), except:
    "Double chance" (sum = 2) and "Win to nil" (incomplete set: separate "yes" bets).
    NOT_EXHAUSTIVE lists such groups.
    """
    p = g.prob
    out: dict[str, dict[str, float]] = {}
    w, d, l = g.outcome()
    out["1X2"] = {"1": w, "X": d, "2": l}
    out["Double chance"] = {"1X": w + d, "12": w + l, "X2": d + l}
    for line in (0.5, 1.5, 2.5, 3.5, 4.5):
        out[f"Total {line}"] = {"U": p(lambda i, j, t=line: i + j < t), "O": p(lambda i, j, t=line: i + j > t)}
    for line in (0.5, 1.5, 2.5):
        out[f"Home total {line}"] = {"U": p(lambda i, j, t=line: i < t), "O": p(lambda i, j, t=line: i > t)}
        out[f"Away total {line}"] = {"U": p(lambda i, j, t=line: j < t), "O": p(lambda i, j, t=line: j > t)}
    out["BTTS"] = {"Yes": p(lambda i, j: i > 0 and j > 0), "No": p(lambda i, j: i == 0 or j == 0)}
    out["Total 2.5 + BTTS"] = {
        "O+Yes": p(lambda i, j: i + j > 2 and i > 0 and j > 0), "U+Yes": p(lambda i, j: i + j < 3 and i > 0 and j > 0),
        "O+No": p(lambda i, j: i + j > 2 and (i == 0 or j == 0)), "U+No": p(lambda i, j: i + j < 3 and (i == 0 or j == 0)),
    }
    res = {"1": lambda i, j: i > j, "X": lambda i, j: i == j, "2": lambda i, j: i < j}
    for line in (1.5, 2.5, 3.5):
        out[f"1X2 + Total {line}"] = {
            f"{k}+{s}": p(lambda i, j, f=f, t=line, s=s: f(i, j) and ((i + j < t) if s == "U" else (i + j > t)))
            for k, f in res.items() for s in ("U", "O")}
    out["1X2 + BTTS"] = {f"{k}+{s}": p(lambda i, j, f=f, s=s: f(i, j) and ((i > 0 and j > 0) == (s == "Yes")))
                       for k, f in res.items() for s in ("Yes", "No")}
    out["Total goals"] = {"0-1": p(lambda i, j: i + j <= 1), "2-3": p(lambda i, j: 2 <= i + j <= 3),
                            "4-5": p(lambda i, j: 4 <= i + j <= 5), "6+": p(lambda i, j: i + j >= 6)}
    out["Odd/Even"] = {"Odd": p(lambda i, j: (i + j) % 2 == 1), "Even": p(lambda i, j: (i + j) % 2 == 0)}
    out["Win to nil"] = {"Home": p(lambda i, j: i > 0 and j == 0), "Away": p(lambda i, j: j > 0 and i == 0)}
    out["Home fails to score"] = {"Yes": p(lambda i, j: i == 0), "No": p(lambda i, j: i > 0)}
    out["Away fails to score"] = {"Yes": p(lambda i, j: j == 0), "No": p(lambda i, j: j > 0)}
    n = len(g.grid)
    out["Correct score"] = {f"{i}:{j}": g.grid[i][j] for i in range(n) for j in range(n) if i <= 6 and j <= 6}
    return out


def first_half(lam_home: float, lam_away: float, share: float = 0.45) -> dict[str, dict[str, float]]:
    """First-half markets. ASSUMPTION, not backtested: half goals are Poisson with a share of the match total."""
    g = ScoreGrid.poisson(lam_home * share, lam_away * share, 8)
    w, d, l = g.outcome()
    out = {"1st half 1X2": {"1": w, "X": d, "2": l}}
    for line in (0.5, 1.5):
        out[f"1st half total {line}"] = {"U": g.prob(lambda i, j, t=line: i + j < t),
                                        "O": g.prob(lambda i, j, t=line: i + j > t)}
    out["1st half BTTS"] = {"Yes": g.prob(lambda i, j: i > 0 and j > 0), "No": g.prob(lambda i, j: i == 0 or j == 0)}
    return out


def halftime_fulltime_scores(lam_home: float, lam_away: float, first_half_share: float = 0.45,
                             max_goals: int = 6, k: int = 3) -> list[tuple[str, float]]:
    """Most likely pairs "first-half score -> final score".

    Assumption: goals in each half are independent Poissons with shares first_half_share and 1 - first_half_share.
    """
    f = first_half_share
    P = poisson_pmf
    out: dict[tuple[int, int, int, int], float] = {}
    r = range(max_goals + 1)
    for i in r:
        for j in r:
            p1 = P(lam_home * f, i) * P(lam_away * f, j)
            for x in r:
                for y in r:
                    key = (i, j, i + x, j + y)
                    out[key] = out.get(key, 0.0) + p1 * P(lam_home * (1 - f), x) * P(lam_away * (1 - f), y)
    best = sorted(out.items(), key=lambda kv: -kv[1])[:k]
    return [(f"{a}-{b} -> {c}-{d}", p) for (a, b, c, d), p in best]
