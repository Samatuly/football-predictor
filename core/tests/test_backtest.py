"""Тесты метрик и бэктеста, включая проверку на утечку будущего."""
import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from predictor_core import backtest  # noqa: E402
from predictor_core.data.results import Match  # noqa: E402
from predictor_core.metrics import brier, log_loss, rps  # noqa: E402
from predictor_core.ratings_elo import EloBook  # noqa: E402


def _m(day: int, h: str, a: str, hg: int, ag: int) -> Match:
    return Match(date(2000, 1, 1) + timedelta(days=day), h, a, hg, ag, "Friendly", False)


class TestMetrics(unittest.TestCase):
    def test_perfect(self):
        self.assertAlmostEqual(log_loss((1, 0, 0), 0), 0.0)
        self.assertAlmostEqual(brier((1, 0, 0), 0), 0.0)
        self.assertAlmostEqual(rps((1, 0, 0), 0), 0.0)

    def test_rps_order(self):
        # промах «в соседний» исход штрафуется меньше, чем «через один»
        self.assertLess(rps((0, 1, 0), 0), rps((0, 0, 1), 0))

    def test_uniform_brier(self):
        self.assertAlmostEqual(brier((1 / 3, 1 / 3, 1 / 3), 0), 2 / 3)


class TestNoLeakage(unittest.TestCase):
    def test_prediction_uses_only_past(self):
        """Рейтинг на момент матча не зависит от его результата и от будущих матчей."""
        hist = [_m(i, "A", "B", 1, 0) for i in range(5)]
        target_win, target_loss = _m(10, "A", "B", 5, 0), _m(10, "A", "B", 0, 5)
        future = [_m(20, "A", "B", 0, 9)]

        def pre(seq, target):
            book = EloBook()
            for m in seq:
                if m is target:
                    return book.pre_match(m)
                book.update(m)

        self.assertEqual(pre(hist + [target_win] + future, target_win),
                         pre(hist + [target_loss] + future, target_loss))

    def test_backtest_outcome_independent(self):
        """Прогноз на матч не меняется, если поменять его результат."""
        base = [_m(i, "A" if i % 2 else "B", "B" if i % 2 else "A", i % 3, 1) for i in range(80)]
        flipped = base[:-1] + [_m(79, base[-1].home, base[-1].away, 7, 0)]
        r1 = backtest.run(base, date(2000, 1, 1) + timedelta(days=79), min_games=10)
        r2 = backtest.run(flipped, date(2000, 1, 1) + timedelta(days=79), min_games=10)
        self.assertEqual(r1["n"], 1)
        # одна и та же вероятность «хозяева не проиграли» при разных результатах -> одинаковый прогноз
        name = next(iter(r1["summary"]))
        self.assertNotEqual(r1["summary"][name]["log_loss"], r2["summary"][name]["log_loss"])
        self.assertAlmostEqual(r1["draws"][name], r2["draws"][name])


if __name__ == "__main__":
    unittest.main()
