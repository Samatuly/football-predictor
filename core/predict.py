"""CLI: match forecasts.

Default model is dixon_coles (needs numpy and a results file):
    python core/predict.py --fixtures fixtures.csv [--results data/raw/results.csv] [--as-of 2026-11-14] [--json] [--log]
The elo_poisson model (no external packages):
    python core/predict.py --model elo_poisson --elo World.tsv --fixtures fixtures.csv

Teams in fixtures.csv are eloratings.net codes (NL, GR, ...). For dixon_coles the code is mapped
to the name used in the results dataset via core/predictor_core/data/team_map.csv.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from predictor_core import ledger  # noqa: E402
from predictor_core.data.elo import load_world_tsv  # noqa: E402
from predictor_core.data.team_map import load_team_map  # noqa: E402
from predictor_core.markets import halftime_fulltime_scores, markets  # noqa: E402
from predictor_core.models import elo_poisson  # noqa: E402
from predictor_core.odds_math import devig_proportional, overround  # noqa: E402
from predictor_core.scoregrid import ScoreGrid  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "predictions" / "ledger.jsonl"
DEFAULT_RESULTS = ROOT / "data" / "raw" / "results.csv"
MANUAL_DIR = ROOT / "data" / "manual"
DC_HALF_LIFE = 1460.0  # chosen on 2005–2009
STALE_DAYS = 30

WARNINGS = {
    "elo_poisson": "Over 1.5 is overestimated by about 5 pp; the total ignores team style.",
    "dixon_coles": "Stronger than elo_poisson in the 2010–2026 backtest; on 13 Nov the bookmaker odds were more accurate on 1X2.",
}


def _f(row: dict, key: str) -> float | None:
    v = (row.get(key) or "").strip()
    return float(v) if v else None


def _fixtures(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _neutral(row: dict) -> bool:
    return (row.get("neutral") or "").strip().lower() in {"1", "true", "yes"}


def _record(row: dict, g: ScoreGrid, base: dict) -> dict:
    rec = {
        **base,
        "lam_home": round(g.lam_home, 3), "lam_away": round(g.lam_away, 3),
        "markets": {k: round(v, 4) for k, v in markets(g).items()},
        "top_scores": [(s, round(q, 4)) for s, q in g.top_scores(3)],
        "ht_ft": [(s, round(q, 4)) for s, q in halftime_fulltime_scores(g.lam_home, g.lam_away)],
    }
    o1x2 = [_f(row, k) for k in ("odds_1", "odds_x", "odds_2")]
    if all(o1x2):
        fair = devig_proportional(o1x2)
        rec["market_1x2"] = {"odds": o1x2, "margin": round(overround(o1x2), 4),
                             "fair": [round(x, 4) for x in fair],
                             "diff": [round(m - f, 4) for m, f in
                                      zip((rec["markets"]["1"], rec["markets"]["X"], rec["markets"]["2"]), fair)]}
    ou = [_f(row, k) for k in ("odds_over25", "odds_under25")]
    if all(ou):
        fair = devig_proportional(ou)
        rec["market_ou25"] = {"odds": ou, "margin": round(overround(ou), 4),
                              "fair_over": round(fair[0], 4),
                              "diff_over": round(rec["markets"]["over_2.5"] - fair[0], 4)}
    return rec


def run(elo_path: str, fixtures_path: str, params=elo_poisson.CALIBRATED) -> tuple[list[dict], list[str]]:
    """Forecast with the elo_poisson model."""
    elo = load_world_tsv(elo_path)
    results, unmatched = [], []
    for row in _fixtures(fixtures_path):
        h, a = row["home"].strip(), row["away"].strip()
        missing = [c for c in (h, a) if c not in elo]
        if missing:
            unmatched.append(f"{h}-{a}: not in the rating table: {','.join(missing)}")
            continue
        neutral = _neutral(row)
        p = elo_poisson.predict(elo[h].rating, elo[a].rating, neutral=neutral, params=params)
        results.append(_record(row, p["grid"], {
            "home": h, "away": a, "neutral": neutral,
            "model": p["model"], "validated": p["validated"], "params": p["params"],
            "elo_home": elo[h].rating, "elo_away": elo[a].rating,
            "rank_home": elo[h].rank, "rank_away": elo[a].rank,
            "dr": round(p["dr"], 1), "we": round(p["we"], 4),
        }))
    return results, unmatched


def run_dc(results_path: str, fixtures_path: str, as_of: date,
           extra_paths: list[str] | None = None) -> tuple[list[dict], list[str], dict]:
    """Forecast with dixon_coles, fitted strictly on matches before as_of."""
    from predictor_core.data.results import load_with_extra
    from predictor_core.models import dixon_coles as dc

    if extra_paths is None:
        extra_paths = sorted(str(p) for p in MANUAL_DIR.glob("*.csv"))
    matches, extra_info = load_with_extra(results_path, extra_paths)
    cfg = dc.DCConfig(half_life_days=DC_HALF_LIFE)
    fit = dc.fit(matches, as_of, cfg)
    last = max((m.date for m in matches if m.date < as_of), default=None)
    info = {"as_of": as_of.isoformat(), "last_match_in_data": last.isoformat() if last else None,
            "days_stale": (as_of - last).days if last else None, "n_fit": fit.n_matches,
            "rho": round(fit.rho, 3), "home_adv_log": round(fit.home, 3), "half_life_days": cfg.half_life_days,
            **extra_info}

    tmap = load_team_map()
    results, unmatched = [], []
    for row in _fixtures(fixtures_path):
        h, a = row["home"].strip(), row["away"].strip()
        names = [tmap.get(c) for c in (h, a)]
        if None in names:
            miss = [c for c, n in zip((h, a), names) if n is None]
            unmatched.append(f"{h}-{a}: not in team_map.csv: {','.join(miss)}")
            continue
        nh, na = names
        absent = [n for n in (nh, na) if not fit.has(n)]
        if absent:
            unmatched.append(f"{h}-{a}: no matches in the fit window: {','.join(absent)}")
            continue
        neutral = _neutral(row)
        results.append(_record(row, fit.grid(nh, na, neutral), {
            "home": h, "away": a, "home_name": nh, "away_name": na, "neutral": neutral,
            "model": dc.NAME, "validated": True,
            "params": {"half_life_days": cfg.half_life_days, "window_years": cfg.window_years,
                       "ridge": cfg.ridge, "rho": info["rho"], "home_adv_log": info["home_adv_log"]},
            "as_of": info["as_of"], "last_match_in_data": info["last_match_in_data"],
        }))
    return results, unmatched, info


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Forecast international football matches.")
    ap.add_argument("--model", choices=["dixon_coles", "elo_poisson"], default="dixon_coles")
    ap.add_argument("--fixtures", required=True,
                    help="CSV: home,away[,odds_1,odds_x,odds_2,odds_under25,odds_over25,neutral]; eloratings codes")
    ap.add_argument("--results", default=str(DEFAULT_RESULTS), help="results.csv (for dixon_coles)")
    ap.add_argument("--no-manual", action="store_true", help="do not merge data/manual/*.csv")
    ap.add_argument("--as-of", default=date.today().isoformat(),
                    help="forecast date; the model only sees matches before it")
    ap.add_argument("--elo", help="World.tsv from eloratings.net (for elo_poisson)")
    ap.add_argument("--params", choices=["calibrated", "original"], default="calibrated", help="elo_poisson parameters")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--log", action="store_true", help=f"append to the ledger {LEDGER}")
    args = ap.parse_args()

    info: dict = {}
    if args.model == "elo_poisson":
        if not args.elo:
            ap.error("elo_poisson requires --elo")
        params = elo_poisson.CALIBRATED if args.params == "calibrated" else elo_poisson.ORIGINAL
        results, unmatched = run(args.elo, args.fixtures, params)
        source = {"elo_file": args.elo}
    else:
        results, unmatched, info = run_dc(args.results, args.fixtures, date.fromisoformat(args.as_of),
                                          [] if args.no_manual else None)
        source = {"results_file": args.results, "extra_files": info.get("extra_files", [])}

    warnings = [WARNINGS[args.model]]
    if info.get("days_stale") is not None and info["days_stale"] > STALE_DAYS:
        warnings.append(f"Data is stale: last match {info['last_match_in_data']}, "
                        f"{info['days_stale']} days before the forecast date. Update results.csv.")

    if args.log:
        for r in results:
            ledger.append(LEDGER, {**source, **r})

    if args.json:
        print(json.dumps({"model": args.model, "fit": info, "warnings": warnings, "predictions": results,
                          "unmatched": unmatched}, ensure_ascii=False, indent=2))
        return

    print(f"Model {args.model}. Not betting advice.")
    for w in warnings:
        print("WARNING:", w)
    print()
    for r in results:
        m = r["markets"]
        line = (f"{r['home']}-{r['away']} | λ {r['lam_home']:.2f}-{r['lam_away']:.2f} | "
                f"{pct(m['1'])}/{pct(m['X'])}/{pct(m['2'])} O2.5 {pct(m['over_2.5'])} BTTS {pct(m['btts_yes'])} | "
                + " ".join(f"{s}({pct(q)})" for s, q in r["top_scores"]))
        if "market_1x2" in r:
            d = r["market_1x2"]["diff"]
            line += f" | vs market {d[0]*100:+.0f}/{d[1]*100:+.0f}/{d[2]*100:+.0f} pp"
        if "market_ou25" in r:
            line += f", O2.5 {r['market_ou25']['diff_over']*100:+.0f} pp"
        print(line)
    for u in unmatched:
        print("UNMATCHED:", u)


if __name__ == "__main__":
    main()
