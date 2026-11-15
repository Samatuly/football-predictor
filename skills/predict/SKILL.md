---
name: predict
description: "Probabilistic forecast for a match or a round of international fixtures: Dixon–Coles model (or Elo → Poisson) → markets (1X2, totals, BTTS, correct score, halves) → comparison with bookmaker odds after margin removal → report and ledger entry. Use when the user asks for a forecast, outcome probabilities, or a comparison with odds."
argument-hint: "[match(es) or round, odds optional]"
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep"]
---

# Predict

Read `${CLAUDE_PLUGIN_ROOT}/skills/_shared/accuracy-rules.md` and follow it.

## Steps

1. **Matches.** Write them to a CSV: `home,away,odds_1,odds_x,odds_2,odds_under25,odds_over25,neutral`.
   - Team codes are eloratings.net codes (`NL`, `GR`, ...).
   - Totals order: "under 2.5" first, then "over 2.5". If the source does not make it clear which odds belong to which,
     ask the user. Do not guess.
   - Take odds only from the user or from a source the user named.
2. **Model.** The default is `dixon_coles`, which is stronger in the backtest (needs numpy and
   `${CLAUDE_PLUGIN_ROOT}/data/raw/results.csv`). `elo_poisson` is the fallback without external packages
   (needs a fresh `World.tsv`).
3. **Calculation** goes through the core only. No numbers from memory:
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/core/predict.py" --fixtures <fixtures.csv> --as-of <match date> --json --log
   ```
   For Elo, add `--model elo_poisson --elo <World.tsv>`. `--log` writes the forecast to `predictions/ledger.jsonl`;
   do not use `--log` for matches that have already been played.
4. **Check the output:**
   - `warnings`: carry them into the report. If the data is stale (`days_stale` > 30), tell the user and suggest
     updating `results.csv` (source: `data/raw/results.SOURCE.txt`; download only with the user's consent).
   - `extra_added`: how many matches were merged from `data/manual/*.csv` (manual additions with a source on every row).
   - `unmatched`: name every row. Add a code missing from `core/predictor_core/data/team_map.csv` only after
     checking that the name exists exactly in `results.csv`; otherwise ask the user.
5. **Context** (injuries, rotation) is optional, via the `context-scout` agent. It returns facts with sources, not percentages.
6. **Report** follows `skills/_shared/report-template.md` and goes to `predictions/reports/YYYY-MM-DD_<topic>.md`.

## Limitations (state them in the report)

- Model status and weaknesses are in `accuracy-rules.md`, section "Model status".
- The first-half goal share of 45% (half-time/full-time markets) is an assumption with no source and no backtest.
- There is no xG, injury or lineup data.
