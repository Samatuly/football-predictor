"""Core tests. Run: python -m unittest discover -s core/tests"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from predictor_core.markets import halftime_fulltime_scores, markets  # noqa: E402
from predictor_core.models import elo_poisson  # noqa: E402
from predictor_core.odds_math import devig_power, devig_proportional, overround  # noqa: E402
from predictor_core.scoregrid import ScoreGrid  # noqa: E402

import predict as cli  # noqa: E402

WORLD_TSV = HERE.parents[2] / "scripts" / "world.tsv"
FIXTURES = HERE / "fixtures" / "2026-11-13.csv"

# Expected goals from the 13 Nov 2026 analysis report, section 4
REPORT_LAMBDAS = {
    ("NL", "GR"): (2.21, 0.61), ("RS", "DE"): (0.98, 1.66), ("SQ", "NM"): (2.26, 0.58),
    ("SI", "CH"): (0.87, 1.82), ("BG", "IS"): (1.14, 1.42), ("LU", "EE"): (1.53, 1.06),
    ("SK", "FO"): (2.56, 0.40), ("LI", "AZ"): (0.48, 2.43), ("AD", "GI"): (1.69, 0.96),
}


class TestScoreGrid(unittest.TestCase):
    def test_sums_to_one(self):
        g = ScoreGrid.poisson(1.6, 1.1)
        self.assertAlmostEqual(sum(g.outcome()), 1.0, places=5)

    def test_markets_consistent(self):
        m = markets(ScoreGrid.poisson(1.6, 1.1))
        self.assertAlmostEqual(m["over_2.5"] + m["under_2.5"], 1.0, places=5)
        self.assertAlmostEqual(m["btts_yes"] + m["btts_no"], 1.0, places=9)
        self.assertAlmostEqual(m["1X"], m["1"] + m["X"], places=9)


class TestEloPoisson(unittest.TestCase):
    def test_matches_we(self):
        p = elo_poisson.predict(1900, 1800)
        w, d, _ = p["grid"].outcome()
        self.assertAlmostEqual(w + d / 2, p["we"], places=4)

    def test_neutral_symmetric(self):
        g = elo_poisson.predict(1800, 1800, neutral=True)["grid"]
        self.assertAlmostEqual(g.lam_home, g.lam_away, places=5)

    def test_reports_params(self):
        self.assertIn("draw_delta", elo_poisson.predict(1800, 1700)["params"])

    def test_draw_boost_raises_draws(self):
        g = ScoreGrid.poisson(1.3, 1.1)
        b = g.with_low_score_boost(0.15)
        self.assertGreater(b.outcome()[1], g.outcome()[1])
        self.assertAlmostEqual(sum(b.outcome()), sum(g.outcome()) / sum(map(sum, g.grid)), places=5)

    def test_draw_delta_keeps_we(self):
        p = elo_poisson.predict(1900, 1800, params=elo_poisson.EloPoissonParams(draw_delta=0.2))
        w, d, _ = p["grid"].outcome()
        self.assertAlmostEqual(w + d / 2, p["we"], places=4)


class TestOdds(unittest.TestCase):
    def test_devig(self):
        odds = [1.49, 4.43, 5.15]
        for f in (devig_proportional, devig_power):
            self.assertAlmostEqual(sum(f(odds)), 1.0, places=5)
        self.assertGreater(overround(odds), 0)
        # the power method cuts the outsider more
        self.assertLess(devig_power(odds)[2], devig_proportional(odds)[2])


@unittest.skipUnless(WORLD_TSV.exists(), "scripts/world.tsv not found")
class TestReproducesReport(unittest.TestCase):
    """Stage 1: the core must reproduce the 13 Nov 2026 report (scripts/m.py)."""

    def test_lambdas(self):
        results, unmatched = cli.run(str(WORLD_TSV), str(FIXTURES), elo_poisson.ORIGINAL)
        self.assertEqual(unmatched, [])
        self.assertEqual(len(results), 9)
        for r in results:
            eh, ea = REPORT_LAMBDAS[(r["home"], r["away"])]
            self.assertAlmostEqual(r["lam_home"], eh, delta=0.006, msg=f"{r['home']}-{r['away']}")
            self.assertAlmostEqual(r["lam_away"], ea, delta=0.006, msg=f"{r['home']}-{r['away']}")

    def test_ht_ft_slovakia(self):
        # report, section 10: Slovakia — Faroe Islands 1-0 -> 2-0, 8.4%
        top = halftime_fulltime_scores(2.56, 0.40)
        self.assertEqual(top[0][0], "1-0 -> 2-0")
        self.assertAlmostEqual(top[0][1], 0.084, delta=0.001)


if __name__ == "__main__":
    unittest.main()


class TestMarketsFull(unittest.TestCase):
    def test_groups_sum_to_one(self):
        from predictor_core.markets import first_half, markets_full
        from predictor_core.models.dixon_coles import dc_grid
        g = dc_grid(1.8, 1.3, -0.05)
        from predictor_core.markets import NOT_EXHAUSTIVE
        for name, grp in {**markets_full(g), **first_half(1.8, 1.3)}.items():
            if name == "Win to nil":
                self.assertIn(name, NOT_EXHAUSTIVE)
                continue
            total = sum(grp.values())
            expected = 2.0 if name == "Double chance" else 1.0
            tol = 5e-3 if name == "Correct score" else 1e-6  # correct score is truncated at 6 goals
            self.assertAlmostEqual(total, expected, delta=tol, msg=name)
