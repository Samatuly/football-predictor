"""CLI: калибровка рынков голов на 1990–2009, проверка на 2010–2026.

python core/calibrate_totals_cli.py --results data/raw/results.csv --out predictions/reports/X.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from predictor_core import totals  # noqa: E402
from predictor_core.data.results import load_results  # noqa: E402
from predictor_core.models.elo_poisson import CALIBRATED  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()

    matches = load_results(a.results)
    train = totals.collect(matches, date(1990, 1, 1), date(2009, 12, 31))
    test = totals.collect(matches, date(2010, 1, 1), None)
    print(f"Обучение: {len(train)}; тест: {len(test)}\n")

    best = totals.fit(train, CALIBRATED)
    out = {"params_before": CALIBRATED.as_dict(), "params_after": best.as_dict(),
           "baseline_test": totals.baseline(train, test)}
    for label, p in (("до", CALIBRATED), ("после", best)):
        for w, rows in (("train", train), ("test", test)):
            out[f"{label}_{w}"] = totals.evaluate(rows, p)

    print("\nТЕСТ 2010–2026         до       после    базовые частоты")
    b = out["baseline_test"]
    for k in totals.LINES:
        print(f"log-loss {k:10} {out['до_test']['log_loss'][k]:.4f}   {out['после_test']['log_loss'][k]:.4f}   "
              f"{b['log_loss'][k]:.4f}")
    print(f"сумма              {out['до_test']['objective']:.4f}   {out['после_test']['objective']:.4f}   {b['objective']:.4f}")
    print(f"log-loss 1X2       {out['до_test']['log_loss_1x2']:.4f}   {out['после_test']['log_loss_1x2']:.4f}")
    print(f"голов за матч      {out['до_test']['goals_pred']:.2f}     {out['после_test']['goals_pred']:.2f}     "
          f"(факт {out['после_test']['goals_actual']:.2f})")
    print("\nЧастоты на тесте (модель до / после / факт):")
    for k in totals.LINES:
        print(f"  {k:10} {out['до_test']['pred_rate'][k]:.1%} / {out['после_test']['pred_rate'][k]:.1%} / "
              f"{out['после_test']['actual_rate'][k]:.1%}")
    print("\nКалибровка ТБ2.5 на тесте, после (прогноз→факт):")
    print("  " + "  ".join(f"{c['predicted']:.2f}→{c['observed']:.2f}(n={c['n']})"
                         for c in out["после_test"]["calibration"]["over_2.5"]))
    print("Калибровка ОЗ на тесте, после:")
    print("  " + "  ".join(f"{c['predicted']:.2f}→{c['observed']:.2f}(n={c['n']})"
                         for c in out["после_test"]["calibration"]["btts_yes"]))
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
