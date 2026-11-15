"""CLI: walk-forward бэктест.

python core/backtest_cli.py --results data/raw/results.csv --start 2010-01-01 [--no-friendlies] [--json]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from predictor_core import backtest  # noqa: E402
from predictor_core.data.results import load_results  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Walk-forward бэктест моделей 1X2 на матчах сборных.")
    ap.add_argument("--results", required=True)
    ap.add_argument("--start", default="2010-01-01")
    ap.add_argument("--end")
    ap.add_argument("--min-games", type=int, default=30)
    ap.add_argument("--no-friendlies", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    res = backtest.run(load_results(a.results), date.fromisoformat(a.start),
                       date.fromisoformat(a.end) if a.end else None, a.min_games, a.no_friendlies)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    print(f"Матчей в оценке: {res['n']}\n")
    print(f"{'Модель':45} {'log-loss':>9} {'Brier':>7} {'RPS':>7} {'Угадано':>8}")
    for name, s in sorted(res["summary"].items(), key=lambda kv: kv[1]["log_loss"]):
        print(f"{name:45} {s['log_loss']:9.4f} {s['brier']:7.4f} {s['rps']:7.4f} {s['accuracy']:8.1%}")
    print(f"\nГолов за матч: факт {res['goals']['actual_mean']:.2f}; " +
          "; ".join(f"{k}: {v:.2f}" for k, v in res["goals"].items() if k != "actual_mean"))
    print(f"Доля ничьих: факт {res['draws']['actual_rate']:.1%}; " +
          "; ".join(f"{k}: {v:.1%}" for k, v in res["draws"].items() if k != "actual_rate"))
    for k, rows in res["calibration"].items():
        print(f"\nКалибровка {k} (прогноз → факт, n):")
        for r in rows:
            print(f"  {r['bin']}: {r['predicted']:.2f} → {r['observed']:.2f}  (n={r['n']})")


if __name__ == "__main__":
    main()
