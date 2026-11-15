"""Tests for wiring dixon_coles into predict.py."""
import csv
import sys
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import predict as cli  # noqa: E402
from predictor_core.data.team_map import load_team_map  # noqa: E402

RESULTS = HERE.parents[1] / "data" / "raw" / "results.csv"
FIXTURES = HERE / "fixtures" / "2026-11-13.csv"


class TestTeamMap(unittest.TestCase):
    def test_codes_unique_and_cover_fixture(self):
        m = load_team_map()
        self.assertEqual(len(m), len(set(m.values())), "one name for two codes")
        with open(FIXTURES, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                self.assertIn(r["home"], m)
                self.assertIn(r["away"], m)

    @unittest.skipUnless(RESULTS.exists(), "data/raw/results.csv not found")
    def test_names_exist_in_results(self):
        names = set()
        with open(RESULTS, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                names.update((r["home_team"], r["away_team"]))
        for code, name in load_team_map().items():
            self.assertIn(name, names, f"{code} -> {name} not in results.csv")


@unittest.skipUnless(RESULTS.exists(), "data/raw/results.csv not found")
class TestPredictDC(unittest.TestCase):
    def test_runs_on_fixture(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy required")
        results, unmatched, info = cli.run_dc(str(RESULTS), str(FIXTURES), date(2026, 11, 13))
        self.assertEqual(unmatched, [])
        self.assertEqual(len(results), 9)
        self.assertTrue(info["last_match_in_data"] < "2026-11-13")
        for r in results:
            m = r["markets"]
            self.assertAlmostEqual(m["1"] + m["X"] + m["2"], 1.0, delta=3e-4)  # rounded to 4 decimals
            self.assertEqual(r["model"], "dixon_coles")
        ad = next(r for r in results if r["home"] == "AD")
        self.assertLess(ad["markets"]["over_2.5"], 0.3)  # low-scoring match, as the market also says

    def test_unknown_code_reported(self):
        try:
            import numpy  # noqa: F401
        except ImportError:
            self.skipTest("numpy required")
        tmp = HERE / "fixtures" / "_tmp_unknown.csv"
        tmp.write_text("home,away\nXX,NL\n", encoding="utf-8")
        try:
            results, unmatched, _ = cli.run_dc(str(RESULTS), str(tmp), date(2026, 11, 13))
        finally:
            tmp.unlink()
        self.assertEqual(results, [])
        self.assertEqual(len(unmatched), 1)
        self.assertIn("XX", unmatched[0])


if __name__ == "__main__":
    unittest.main()
