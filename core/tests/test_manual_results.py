"""Тесты ручных дополнений результатов (data/manual/*.csv)."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from predictor_core.data.results import load_with_extra  # noqa: E402

ROOT = HERE.parents[1]
RESULTS = ROOT / "data" / "raw" / "results.csv"
MANUAL = sorted((ROOT / "data" / "manual").glob("*.csv"))
HEADER = "date,home_team,away_team,home_score,away_score,tournament,city,country,neutral,source\n"


class TestManualFiles(unittest.TestCase):
    def test_every_row_has_source_and_score(self):
        for p in MANUAL:
            with open(p, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    self.assertTrue(r["source"].strip(), f"{p.name}: нет источника")
                    int(r["home_score"]), int(r["away_score"])

    @unittest.skipUnless(RESULTS.exists(), "нет data/raw/results.csv")
    def test_team_names_exist_in_results(self):
        names = set()
        with open(RESULTS, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                names.update((r["home_team"], r["away_team"]))
        for p in MANUAL:
            with open(p, encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    self.assertIn(r["home_team"], names, p.name)
                    self.assertIn(r["away_team"], names, p.name)


class TestMerge(unittest.TestCase):
    def test_duplicates_skipped_and_new_added(self):
        with tempfile.TemporaryDirectory() as d:
            base, extra = Path(d) / "base.csv", Path(d) / "extra.csv"
            base.write_text(HEADER + "2026-01-01,A,B,1,0,Friendly,,,FALSE,x\n", encoding="utf-8")
            extra.write_text(HEADER + "2026-01-01,A,B,1,0,Friendly,,,FALSE,x\n"
                             "2026-01-05,B,A,2,2,Friendly,,,FALSE,x\n", encoding="utf-8")
            ms, info = load_with_extra(str(base), [str(extra)])
        self.assertEqual(len(ms), 2)
        self.assertEqual(info["extra_added"], 1)
        self.assertEqual(info["extra_duplicates"], 1)
        self.assertEqual([m.date.day for m in ms], [1, 5])


if __name__ == "__main__":
    unittest.main()
