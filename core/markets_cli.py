"""CLI: model vs market across all markets of one match.

python core/markets_cli.py --odds predictions/odds/2026-11-14_KO-IL.json --as-of 2026-11-14 [--json]

Odds file: {"home": code, "away": code, "<group>": {"<outcome>": odds, ...}, ...};
group and outcome names are as in predictor_core.markets.markets_full / first_half.
Margin is removed proportionally within a group ("double chance" probabilities sum to 2).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import predict as base  # noqa: E402
from predictor_core.data.results import load_with_extra  # noqa: E402
from predictor_core.data.team_map import load_team_map  # noqa: E402
from predictor_core.markets import first_half, markets_full  # noqa: E402
from predictor_core.models import dixon_coles as dc  # noqa: E402

UNTESTED = {"1st half 1X2", "1st half total 0.5", "1st half total 1.5", "1st half BTTS"}


def compare(odds: dict, as_of: date, results: str = str(base.DEFAULT_RESULTS)) -> dict:
    tmap = load_team_map()
    h, a = tmap[odds["home"]], tmap[odds["away"]]
    extra = sorted(str(p) for p in base.MANUAL_DIR.glob("*.csv"))
    matches, _ = load_with_extra(results, extra)
    fit = dc.fit(matches, as_of, dc.DCConfig(half_life_days=base.DC_HALF_LIFE))
    g = fit.grid(h, a, neutral=False)
    model = {**markets_full(g), **first_half(g.lam_home, g.lam_away)}
    if "Correct score" in model:
        model["Correct score"]["Other"] = 0.0  # filled in below from the market list
    out = {"home": h, "away": a, "lam": [round(g.lam_home, 3), round(g.lam_away, 3)], "groups": {}}
    for group, sel in odds.items():
        if group.startswith("_") or group in ("home", "away"):
            continue
        if group not in model:
            out["groups"][group] = {"error": "the model does not price this market"}
            continue
        mp = dict(model[group])
        if group == "Correct score":
            listed = [k for k in sel if k != "Other"]
            mp = {k: model[group].get(k, 0.0) for k in listed}
            mp["Other"] = max(0.0, 1 - sum(mp.values()))
        priced = {k: v for k, v in sel.items() if v}
        inv = {k: 1 / v for k, v in priced.items()}
        total = 2.0 if group == "Double chance" else 1.0
        complete = group == "Double chance" or set(priced) == set(sel) and len(sel) == len(mp)
        s = sum(inv.values())
        rows = []
        for k, o in priced.items():
            fair = inv[k] / s * total if complete else None
            p = mp.get(k)
            rows.append({"sel": k, "odds": o, "model": p, "market_fair": fair,
                         "diff": (p - fair) if (p is not None and fair is not None) else None,
                         "ev": (p * o - 1) if p is not None else None})
        out["groups"][group] = {"margin": s / total - 1 if complete else None, "rows": rows,
                                "untested": group in UNTESTED}
    return out


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--odds", required=True)
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    r = compare(json.loads(Path(a.odds).read_text(encoding="utf-8")), date.fromisoformat(a.as_of))
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    print(f"{r['home']} — {r['away']}, λ {r['lam'][0]:.2f}–{r['lam'][1]:.2f}")
    for gname, gr in r["groups"].items():
        if "error" in gr:
            print(f"\n{gname}: {gr['error']}")
            continue
        m = f"margin {gr['margin']:.1%}" if gr["margin"] is not None else "margin —"
        print(f"\n{gname} ({m}{', UNTESTED' if gr['untested'] else ''})")
        for x in gr["rows"]:
            fair = f"{x['market_fair']:.1%}" if x["market_fair"] is not None else "—"
            diff = f"{x['diff'] * 100:+.1f}" if x["diff"] is not None else "—"
            print(f"  {x['sel']:8} {x['odds']:7.2f}  model {x['model']:.1%}  market {fair:>6}  Δ {diff:>6}  EV {x['ev']:+.2f}")


if __name__ == "__main__":
    main()
