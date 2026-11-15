"""Detailed round breakdown as HTML (and PDF via headless Edge/Chrome).

python core/breakdown.py --notes predictions/fixtures/<...>_notes.json --out predictions/reports/<...>.html [--pdf]

Numbers (form, tables, model and market probabilities) are computed here from the data;
text (motivation, arguments, candidate picks) comes from notes.json, written by the analyst
on the basis of these numbers.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import predict as base  # noqa: E402
from predictor_core.data.results import load_with_extra  # noqa: E402
from predictor_core.data.team_map import load_team_map  # noqa: E402
from predictor_core.markets import markets_full  # noqa: E402
from predictor_core.models import dixon_coles as dc  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

TOUR = {"UEFA Nations League": "UNL", "Friendly": "friendly", "FIFA World Cup": "WC", "Baltic Cup": "Baltic Cup"}


def ru(name: str) -> str:
    """Display name of a team (kept as a hook for localisation)."""
    return name


def pct(x: float) -> str:
    return f"{x * 100:.0f}%"


CSS = """
body{font-family:'Segoe UI',DejaVu Sans,Arial,sans-serif;font-size:12.5px;color:#111;max-width:860px;margin:24px auto;line-height:1.45}
h1{font-size:24px;margin:0 0 6px} h2{color:#c0392b;font-size:18px;margin:26px 0 6px} h3{color:#c0392b;font-size:17px;margin:24px 0 4px}
table{border-collapse:collapse;margin:6px 0 8px} th{background:#2c3e50;color:#fff;text-align:left;padding:4px 8px;font-weight:600}
td{border:1px solid #bbb;padding:3px 8px} .c{margin-left:auto;margin-right:auto} .small{font-size:11px;color:#333}
.W{background:#2ecc71} .D{background:#f1c40f} .L{background:#e74c3c;color:#fff}
.lo{background:#d5f5e3} .mid{background:#fdf2cc} .hi{background:#fadbd8} .sum th{background:#ff6f00}
.box{background:#f6f8fa;border-left:3px solid #2c3e50;padding:6px 10px;margin:6px 0} .page{page-break-before:always}
"""


def form_rows(matches, team: str, n: int = 6) -> list[str]:
    rows = []
    for m in [m for m in matches if team in (m.home, m.away)][-n:]:
        gf, ga = (m.home_goals, m.away_goals) if m.home == team else (m.away_goals, m.home_goals)
        r, cls = ("W", "W") if gf > ga else (("D", "D") if gf == ga else ("L", "L"))
        note = f" ({TOUR.get(m.tournament, m.tournament)}{', neutral' if m.neutral else ''})"
        rows.append(f"<tr><td>{m.date:%d.%m.%y}</td><td>{html.escape(ru(m.home))} {m.home_goals}:{m.away_goals} "
                    f"{html.escape(ru(m.away))}{note}</td><td class='{cls}'>{r}</td></tr>")
    return rows


def form_stats(matches, team: str, n: int = 6) -> str:
    L = [m for m in matches if team in (m.home, m.away)][-n:]
    gf = sum(m.home_goals if m.home == team else m.away_goals for m in L)
    ga = sum(m.away_goals if m.home == team else m.home_goals for m in L)
    o25 = sum(m.home_goals + m.away_goals > 2 for m in L)
    bt = sum(m.home_goals > 0 and m.away_goals > 0 for m in L)
    return f"goals {gf}:{ga} · over 2.5 in {o25} of {len(L)} · both scored in {bt} of {len(L)}"


def standings(matches, teams: list[str], order: list[str]) -> str:
    S = {t: [0, 0, 0, 0] for t in teams}
    for m in matches:
        if m.tournament == "UEFA Nations League" and m.date >= date(2026, 9, 1) and m.home in S and m.away in S:
            for t, f, a in ((m.home, m.home_goals, m.away_goals), (m.away, m.away_goals, m.home_goals)):
                s = S[t]
                s[0] += 1
                s[2] += f
                s[3] += a
                s[1] += 3 if f > a else (1 if f == a else 0)
    rows = "".join(f"<tr><td>{i}</td><td>{html.escape(ru(t))}</td><td>{S[t][0]}</td><td>{S[t][1]}</td>"
                   f"<td>{S[t][2]}:{S[t][3]}</td></tr>" for i, t in enumerate(order, 1))
    return f"<table class='c'><tr><th>#</th><th>Team</th><th>P</th><th>Pts</th><th>Goals</th></tr>{rows}</table>"


def build(notes_path: Path) -> str:
    N = json.loads(notes_path.read_text(encoding="utf-8"))
    as_of = date.fromisoformat(N["as_of"])
    extra = sorted(str(p) for p in base.MANUAL_DIR.glob("*.csv"))
    matches, _ = load_with_extra(str(base.DEFAULT_RESULTS), extra)
    fit = dc.fit(matches, as_of, dc.DCConfig(half_life_days=base.DC_HALF_LIFE))
    tmap = load_team_map()
    with open(ROOT / N["fixtures"], encoding="utf-8") as fh:
        fixtures = list(csv.DictReader(fh))
    dcq = {}
    if N.get("double_chance"):
        with open(ROOT / N["double_chance"], encoding="utf-8") as fh:
            dcq = {(r["home"], r["away"]): r for r in csv.DictReader(fh)}

    out = [f"<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(N['title'])}</title>"
           f"<style>{CSS}</style></head><body><h1>{html.escape(N['title'])}</h1><p>{html.escape(N['intro'])}</p>",
           "<h2>Standings and motivation</h2>"]
    for g in N["groups"]:
        out.append(f"<p><b>{html.escape(g['name'])}</b> <span class='small'>({html.escape(g['zones'])})</span></p>")
        out.append(standings(matches, g["order"], g["order"]))
        out.append(f"<p>{html.escape(g['motivation'])}</p>")

    summary = []
    for i, r in enumerate(fixtures, 1):
        code = f"{r['home']}-{r['away']}"
        note = N["matches"][code]
        h, a = tmap[r["home"]], tmap[r["away"]]
        g = fit.grid(h, a, False)
        M = markets_full(g)
        has_odds = all((r.get(k) or "").strip() for k in ("odds_1", "odds_x", "odds_2"))
        has_ou = all((r.get(k) or "").strip() for k in ("odds_under25", "odds_over25"))
        out.append(f"<h3 class='{'page' if i > 1 else ''}'>{i}. {html.escape(ru(h))} – {html.escape(ru(a))} | "
                   f"{note['time']} | {html.escape(note['group'])}</h3>")
        if has_odds:
            o1 = [float(r[k]) for k in ("odds_1", "odds_x", "odds_2")]
            s1 = sum(1 / x for x in o1)
            f1 = [pct(1 / x / s1) for x in o1]
            ou = [float(r["odds_under25"]), float(r["odds_over25"])] if has_ou else None
            fo = pct((1 / ou[1]) / sum(1 / x for x in ou)) if ou else "—"
            q = dcq.get((r["home"], r["away"]), {})
            dc_line = " · ".join(f"{k} {q[k]}" for k in ("1X", "12", "X2") if q.get(k))
            out.append(f"<p>Odds (1/X/2): {o1[0]:.2f} / {o1[1]:.2f} / {o1[2]:.2f} · " + (f"U2.5 {ou[0]:.2f} · " if ou else "")
                       + (f"O2.5 {ou[1]:.2f}" if ou else "total: no line") + f"{' · ' + dc_line if dc_line else ''}</p>")
        else:
            f1, fo = ["—"] * 3, "—"
            out.append("<p><i>No odds: no market comparison, model probabilities only.</i></p>")
        out.append("<table><tr><th></th><th>1</th><th>X</th><th>2</th><th>1X</th><th>X2</th><th>O 2.5</th>"
                   "<th>BTTS</th><th>Exp. goals</th><th>Top 3 scores</th></tr>"
                   f"<tr><td><b>Model</b></td><td>{pct(M['1X2']['1'])}</td><td>{pct(M['1X2']['X'])}</td>"
                   f"<td>{pct(M['1X2']['2'])}</td><td>{pct(M['Double chance']['1X'])}</td><td>{pct(M['Double chance']['X2'])}</td>"
                   f"<td>{pct(M['Total 2.5']['O'])}</td><td>{pct(M['BTTS']['Yes'])}</td>"
                   f"<td>{g.lam_home:.2f}–{g.lam_away:.2f}</td><td>"
                   + ", ".join(f"{s} {pct(p)}" for s, p in g.top_scores(3)) + "</td></tr>"
                   f"<tr><td><b>Market</b> <span class='small'>(margin removed)</span></td><td>{f1[0]}</td>"
                   f"<td>{f1[1]}</td><td>{f1[2]}</td><td>—</td><td>—</td><td>{fo}</td><td>—</td><td>—</td><td>—</td></tr></table>")
        for team, where in ((h, "home"), (a, "away")):
            out.append(f"<p><b>{html.escape(ru(team))}</b> ({where}) — {form_stats(matches, team)}</p>")
            out.append("<table class='c' style='width:80%'><tr><th>Date</th><th>Match</th><th>Result</th></tr>"
                       + "".join(form_rows(matches, team)) + "</table>")
        if note.get("lineups"):
            out.append(f"<div class='box'><b>Lineups and absences:</b> {html.escape(note['lineups'])}</div>")
        out.append(f"<div class='box'><b>Arguments:</b> {html.escape(note['args'])}</div>")
        out.append(f"<div class='box'><b>Picks:</b> {html.escape(note['picks'])}</div>")
        for pick, odd, risk, why in note["summary"]:
            summary.append((f"{ru(h)} – {ru(a)}", pick, odd, risk, why))

    risk_cls = {"Low": "lo", "Medium": "mid", "High": "hi"}
    order = {"Low": 0, "Medium": 1, "High": 2}
    out.append("<h2 class='page'>Summary of forecasts and risks</h2><table class='sum' style='width:100%'>"
               "<tr><th>Match</th><th>Pick</th><th>Odds</th><th>Risk</th><th>Main risk / motivation</th></tr>")
    for m, pick, odd, risk, why in sorted(summary, key=lambda x: order[x[3]]):
        out.append(f"<tr><td>{html.escape(m)}</td><td>{html.escape(pick)}</td><td>{odd}</td>"
                   f"<td class='{risk_cls[risk]}'>{risk}</td><td>{html.escape(why)}</td></tr>")
    out.append("</table>")
    out.append(f"<p class='small'>{html.escape(N.get('risk_note', 'Risk: "Low" means both the model and the market give the event 70% or more; "Medium" means 55–70% or the model and the market disagree; "High" means below 55%.'))}</p>")
    out.append(f"<p>{html.escape(N['express_note'])}</p><p>{html.escape(N['footer'])}</p>")
    last = max(m.date for m in matches if m.date < as_of)
    out.append(f"<p class='small'>Sources: results from martj42/international_results (CC0) plus manual additions from data/manual; last match in the data {last:%d.%m.%Y}; model: dixon_coles (football-predictor), fitted on {as_of:%d.%m.%Y}; {N.get('odds_source', 'odds supplied by the user')}. Form over 6 matches is a small sample and is not evidence.</p></body></html>")
    return "\n".join(out)


def to_pdf(html_path: Path) -> Path | None:
    # Chrome first: headless Edge failed on this machine with ERR_TOO_MANY_REDIRECTS for file:// links.
    pdf = html_path.resolve().with_suffix(".pdf")
    for exe in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                shutil.which("chromium"), shutil.which("google-chrome")):
        if exe and Path(exe).exists():
            subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                            f"--print-to-pdf={pdf}", html_path.resolve().as_uri()], check=False, timeout=120,
                           capture_output=True)
            if pdf.exists():
                return pdf
    return None


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--notes", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pdf", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    out.write_text(build(Path(a.notes)), encoding="utf-8")
    print("HTML:", out)
    if a.pdf:
        print("PDF:", to_pdf(out) or "failed (no Edge/Chrome found)")


if __name__ == "__main__":
    main()
