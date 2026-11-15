# Third-party material

| Component | Source | License | How it is used |
|---|---|---|---|
| Elo → Poisson, margin removal, half-time markets | the author's own scripts (`scripts/m.py`, `mk.py`, `ht.py`) | author's own | basis of `core/` |
| Data, IDs, metrics | withqwerty/nutmeg, football-docs | not specified | used as an external service; no code is copied |
| Time decay and regularisation in the Dixon–Coles model | Mintahandrews/football-predictor | MIT | idea only; code rewritten in Python/numpy |
| Low-score correction τ | Dixon & Coles (1997) | paper | formula |
| Blending with the market, score given outcome (planned) | DOsinga/football_predictions | not specified | ideas only |
