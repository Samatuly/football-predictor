"""CLI: прогноз матчей.

Модель по умолчанию — dixon_coles (нужны numpy и файл результатов):
    python core/predict.py --fixtures fixtures.csv [--results data/raw/results.csv] [--as-of 2026-11-14] [--json] [--log]
Модель elo_poisson (без внешних пакетов):
    python core/predict.py --model elo_poisson --elo World.tsv --fixtures fixtures.csv

Команды в fixtures.csv — коды eloratings.net (NL, GR, ...). Для dixon_coles код переводится
в название набора результатов через core/predictor_core/data/team_map.csv.
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
DC_HALF_LIFE = 1460.0  # выбран на 2005–2009
STALE_DAYS = 30

WARNINGS = {
    "elo_poisson": "ТБ1.5 завышен примерно на 5 п.п.; тотал не учитывает стиль команд.",
    "dixon_coles": "Сильнее elo_poisson на бэктесте 2010–2026; по 1X2 рынок на 13.11 был точнее.",
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
    """Прогноз моделью elo_poisson."""
    elo = load_world_tsv(elo_path)
    results, unmatched = [], []
    for row in _fixtures(fixtures_path):
        h, a = row["home"].strip(), row["away"].strip()
        missing = [c for c in (h, a) if c not in elo]
        if missing:
            unmatched.append(f"{h}-{a}: нет в рейтинге {','.join(missing)}")
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
    """Прогноз моделью dixon_coles, подогнанной по матчам строго до as_of."""
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
            unmatched.append(f"{h}-{a}: нет в team_map.csv: {','.join(miss)}")
            continue
        nh, na = names
        absent = [n for n in (nh, na) if not fit.has(n)]
        if absent:
            unmatched.append(f"{h}-{a}: нет матчей в окне подгонки: {','.join(absent)}")
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
    ap = argparse.ArgumentParser(description="Прогноз матчей сборных.")
    ap.add_argument("--model", choices=["dixon_coles", "elo_poisson"], default="dixon_coles")
    ap.add_argument("--fixtures", required=True,
                    help="CSV: home,away[,odds_1,odds_x,odds_2,odds_under25,odds_over25,neutral]; коды eloratings")
    ap.add_argument("--results", default=str(DEFAULT_RESULTS), help="results.csv (для dixon_coles)")
    ap.add_argument("--no-manual", action="store_true", help="не подмешивать data/manual/*.csv")
    ap.add_argument("--as-of", default=date.today().isoformat(), help="дата прогноза; модель видит только матчи до неё")
    ap.add_argument("--elo", help="World.tsv с eloratings.net (для elo_poisson)")
    ap.add_argument("--params", choices=["calibrated", "original"], default="calibrated", help="параметры elo_poisson")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--log", action="store_true", help=f"записать в журнал {LEDGER}")
    args = ap.parse_args()

    info: dict = {}
    if args.model == "elo_poisson":
        if not args.elo:
            ap.error("для elo_poisson нужен --elo")
        params = elo_poisson.CALIBRATED if args.params == "calibrated" else elo_poisson.ORIGINAL
        results, unmatched = run(args.elo, args.fixtures, params)
        source = {"elo_file": args.elo}
    else:
        results, unmatched, info = run_dc(args.results, args.fixtures, date.fromisoformat(args.as_of),
                                          [] if args.no_manual else None)
        source = {"results_file": args.results, "extra_files": info.get("extra_files", [])}

    warnings = [WARNINGS[args.model]]
    if info.get("days_stale") is not None and info["days_stale"] > STALE_DAYS:
        warnings.append(f"Данные устарели: последний матч {info['last_match_in_data']}, "
                        f"{info['days_stale']} дн. до даты прогноза. Обнови results.csv.")

    if args.log:
        for r in results:
            ledger.append(LEDGER, {**source, **r})

    if args.json:
        print(json.dumps({"model": args.model, "fit": info, "warnings": warnings, "predictions": results,
                          "unmatched": unmatched}, ensure_ascii=False, indent=2))
        return

    print(f"Модель {args.model}. Не совет делать ставки.")
    for w in warnings:
        print("ВНИМАНИЕ:", w)
    print()
    for r in results:
        m = r["markets"]
        line = (f"{r['home']}-{r['away']} | λ {r['lam_home']:.2f}-{r['lam_away']:.2f} | "
                f"{pct(m['1'])}/{pct(m['X'])}/{pct(m['2'])} ТБ2.5 {pct(m['over_2.5'])} ОЗ {pct(m['btts_yes'])} | "
                + " ".join(f"{s}({pct(q)})" for s, q in r["top_scores"]))
        if "market_1x2" in r:
            d = r["market_1x2"]["diff"]
            line += f" | Δ рынок {d[0]*100:+.0f}/{d[1]*100:+.0f}/{d[2]*100:+.0f} п.п."
        if "market_ou25" in r:
            line += f", ТБ2.5 {r['market_ou25']['diff_over']*100:+.0f} п.п."
        print(line)
    for u in unmatched:
        print("НЕ СОПОСТАВЛЕНО:", u)


if __name__ == "__main__":
    main()
