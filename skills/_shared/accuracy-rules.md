# football-predictor: accuracy rules

The model supplies the numbers, the agent supplies context and explanation, and the checks supply correctness.
This file is the single source of the plugin's rules; every skill reads it before working.

1. **Probabilities come only from the model** (`core/`). Claude does not invent percentages. If the core cannot compute something, say so.
2. **No look-ahead leakage.** Features are built only from data before the forecast date (`as_of`).
3. **No validation, no trust.** Name the model and its validation status (see "Model status").
4. **Quality metrics:** log-loss, Brier, RPS, calibration, comparison with the market. Not the share of correct picks.
5. **Always remove the margin** before comparing with the market, and name the method (currently proportional).
6. **A gap from the market is not a "value bet"** until the model has beaten the market in a backtest.
7. **Join by ID**, not by name; unmatched rows go into the report.
8. **Provider facts** come from football-docs (nutmeg), with the document named; xG variants are never mixed.
9. **Every report** has "Sources", "Assumptions" and "Limitations" sections and a confidence level.
10. **Not betting advice.** No "sure things" or "accas of the day"; for accumulators, state the combined probability (the product).

## Model status

| Model | Validation | Known weaknesses |
|---|---|---|
| `elo_poisson` (CALIBRATED) | 1X2 and goal markets calibrated on international matches 1990–2009, tested on 2010–2026 | Over 1.5 is overestimated by about 5 pp; the edges of O2.5/BTTS are imprecise; the total ignores team style; international teams only; not compared with the market on history |
| **`dixon_coles`** (default in `/predict`, half_life 1460 days) | Walk-forward on international matches 2010–2026: better than `elo_poisson` on 1X2 and goal markets, O1.5 is calibrated | Freshness depends on `results.csv` (see `days_stale`); only teams in `team_map.csv`; international teams only; not compared with the market on history; in the 13 Nov round the market was more accurate on 1X2 |
