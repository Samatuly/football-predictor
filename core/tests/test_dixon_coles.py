"""Tests for the Dixon–Coles model."""
import random
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import numpy  # noqa: F401
    HAVE_NP = True
except ImportError:
    HAVE_NP = False

from predictor_core.data.results import Match  # noqa: E402


def _poisson(rng: random.Random, lam: float) -> int:
    k, p, l_ = 0, 1.0, pow(2.718281828459045, -lam)
    while True:
        p *= rng.random()
        if p <= l_:
            return k
        k += 1


def synthetic(n_rounds: int = 60, seed: int = 1) -> list[Match]:
    """A league of 6 teams with known attacking strength."""
    rng = random.Random(seed)
    strength = {"A": 0.5, "B": 0.25, "C": 0.0, "D": 0.0, "E": -0.25, "F": -0.5}
    teams = list(strength)
    out, d = [], date(2000, 1, 1)
    for _ in range(n_rounds):
        rng.shuffle(teams)
        for i in range(0, 6, 2):
            h, a = teams[i], teams[i + 1]
            lh = 1.3 * 2.718281828459045 ** (strength[h] - strength[a] + 0.2)
            la = 1.3 * 2.718281828459045 ** (strength[a] - strength[h])
            out.append(Match(d, h, a, _poisson(rng, lh), _poisson(rng, la), "Friendly", False))
        d += timedelta(days=7)
    return out


@unittest.skipUnless(HAVE_NP, "numpy required")
class TestDixonColes(unittest.TestCase):
    def setUp(self):
        from predictor_core.models import dixon_coles as dc
        self.dc = dc

    def test_grid_sums_to_one(self):
        g = self.dc.dc_grid(1.4, 1.1, -0.1)
        self.assertAlmostEqual(sum(map(sum, g.grid)), 1.0, places=9)

    def test_negative_rho_raises_low_draws(self):
        from predictor_core.scoregrid import ScoreGrid
        base = ScoreGrid.poisson(1.4, 1.1)
        g = self.dc.dc_grid(1.4, 1.1, -0.1)
        self.assertGreater(g.grid[0][0], base.grid[0][0])
        self.assertGreater(g.grid[1][1], base.grid[1][1])

    def test_recovers_order_of_strength(self):
        ms = synthetic()
        fit = self.dc.fit(ms, ms[-1].date + timedelta(days=1), self.dc.DCConfig(half_life_days=10_000))
        net = {t: fit.att[i] + fit.dfn[i] for t, i in fit.teams.items()}
        self.assertGreater(net["A"], net["C"])
        self.assertGreater(net["C"], net["F"])
        self.assertGreater(fit.home, 0)

    def test_no_future_leak(self):
        """A fit for a date does not depend on matches on or after that date."""
        ms = synthetic()
        cut = ms[len(ms) // 2].date
        future_changed = [m if m.date < cut else Match(m.date, m.home, m.away, 9, 0, m.tournament, m.neutral)
                          for m in ms]
        f1 = self.dc.fit(ms, cut)
        f2 = self.dc.fit(future_changed, cut)
        self.assertEqual(f1.n_matches, f2.n_matches)
        self.assertAlmostEqual(f1.mu, f2.mu, places=12)
        self.assertAlmostEqual(f1.rho, f2.rho, places=12)


if __name__ == "__main__":
    unittest.main()
