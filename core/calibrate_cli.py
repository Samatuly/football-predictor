"""CLI: подбор параметров на обучающем окне, проверка на тестовом.

python core/calibrate_cli.py --results data/raw/results.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from predictor_core import calibrate  # noqa: E402
from predictor_core.data.results import load_results  # noqa: E402
from predictor_core.models.elo_poisson import ORIGINAL  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--train-start", default="1990-01-01")
    ap.add_argument("--train-end", default="2009-12-31")
    ap.add_argument("--test-start", default="2010-01-01")
    ap.add_argument("--out", help="JSON с итогами")
    a = ap.parse_args()

    matches = load_results(a.results)
    train = calibrate.collect(matches, date.fromisoformat(a.train_start), date.fromisoformat(a.train_end))
    test = calibrate.collect(matches, date.fromisoformat(a.test_start), None)
    print(f"Обучение: {len(train)} матчей; тест: {len(test)} матчей\n")

    best = calibrate.fit(train)
    out = {"params_original": ORIGINAL.as_dict(), "params_calibrated": best.as_dict(),
           "n_train": len(train), "n_test": len(test)}
    for label, p in (("исходная", ORIGINAL), ("откалиброванная", best)):
        for window, rows in (("train", train), ("test", test)):
            s = calibrate.evaluate(rows, p)
            scored = s.pop("_scored")
            out[f"{label}_{window}"] = s
            if window == "test":
                out[f"{label}_calibration_test"] = {k: calibrate.calibration_table(scored, i)
                                                    for i, k in enumerate(("П1", "Х", "П2"))}

    print("\nОкно     Модель            log-loss  Brier   RPS    Угадано  Голы(м/ф)   Ничьи(м/ф)")
    for window in ("train", "test"):
        for label in ("исходная", "откалиброванная"):
            s = out[f"{label}_{window}"]
            print(f"{window:8} {label:17} {s['log_loss']:.4f}  {s['brier']:.4f}  {s['rps']:.4f}  {s['accuracy']:6.1%}"
                  f"   {s['goals_pred']:.2f}/{s['goals_actual']:.2f}   {s['draws_pred']:.1%}/{s['draws_actual']:.1%}")
    for label in ("исходная", "откалиброванная"):
        print(f"\nКалибровка на тесте, {label}:")
        for k, rows in out[f"{label}_calibration_test"].items():
            print(f"  {k}: " + "  ".join(f"{r['predicted']:.2f}→{r['observed']:.2f}" for r in rows))
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
