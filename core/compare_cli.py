"""CLI: choose the DC decay period on 2005–2009 and compare with elo_poisson on 2010–2026.

python core/compare_cli.py --results data/raw/results.csv --out predictions/reports/X.json
Requires numpy.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from predictor_core import compare  # noqa: E402
from predictor_core.data.results import load_results  # noqa: E402
from predictor_core.models.dixon_coles import DCConfig  # noqa: E402


def show(label: str, r: dict) -> None:
    print(f"\n{label}: n={r['n']}, skipped (no fit): {r['skipped_no_fit']}")
    print(f"{'':12} {'1X2 ll':>8} {'Brier':>7} {'RPS':>7} {'O1.5':>7} {'O2.5':>7} {'O3.5':>7} {'BTTS':>7} {'Σ goals':>7} {'goals':>6} {'draws':>6}")
    for m in ("elo_poisson", "dixon_coles"):
        s, g = r[m]["1x2"], r[m]["goal_log_loss"]
        print(f"{m:12} {s['log_loss']:8.4f} {s['brier']:7.4f} {s['rps']:7.4f} {g['over_1.5']:7.4f} {g['over_2.5']:7.4f} "
              f"{g['over_3.5']:7.4f} {g['btts_yes']:7.4f} {r[m]['goal_log_loss_sum']:7.4f} {r[m]['expected_goals']:6.2f} {r[m]['draw_pred']:6.1%}")
    a = r["actual"]
    print(f"{'actual':12} goals {a['goals']:.2f}, draws {a['draws']:.1%}, " +
          ", ".join(f"{k} {v:.1%}" for k, v in a["goal_rate"].items()))
    for m in ("elo_poisson", "dixon_coles"):
        print(f"  {m} frequencies: " + ", ".join(f"{k} {v:.1%}" for k, v in r[m]["goal_pred_rate"].items()))


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out")
    ap.add_argument("--half-lives", default="365,730,1460")
    a = ap.parse_args()
    matches = load_results(a.results)
    out = {"validation": {}}

    print("Choosing the decay period on 2005–2009 (refit every 90 days):")
    best_hl, best_ll = None, 1e9
    for hl in [float(x) for x in a.half_lives.split(",")]:
        cfg = DCConfig(half_life_days=hl)
        r = compare.run(matches, date(2005, 1, 1), date(2009, 12, 31), cfg, refit_days=90, log=lambda *_: None)
        ll = r["dixon_coles"]["1x2"]["log_loss"] + r["dixon_coles"]["goal_log_loss_sum"]
        out["validation"][str(hl)] = r
        print(f"  half_life={hl:.0f} d: 1X2 {r['dixon_coles']['1x2']['log_loss']:.4f}, "
              f"goals {r['dixon_coles']['goal_log_loss_sum']:.4f}, sum {ll:.4f}")
        if ll < best_ll:
            best_hl, best_ll = hl, ll
    print(f"Chosen half_life = {best_hl:.0f} days")

    cfg = replace(DCConfig(), half_life_days=best_hl)
    print("\nTest 2010–2026 (refit every 30 days):")
    test = compare.run(matches, date(2010, 1, 1), None, cfg, refit_days=30, log=lambda *_: None)
    out["test"] = test
    show("TEST 2010–2026", test)
    if a.out:
        Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
