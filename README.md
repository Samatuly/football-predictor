# football-predictor

**A Claude Code plugin for probabilistic football match forecasting.**

The plugin estimates team strength, computes probabilities for match outcomes and the main betting markets, and compares them with bookmaker odds after removing the margin. Every model is validated with walk-forward backtests on historical international matches.

> ⚠️ The model produces probability estimates, not betting advice. See the [Disclaimer](#disclaimer).

## Features

- **Two models.** Primary: Dixon–Coles with time decay. Fallback: Elo → Poisson.
- **Markets.** 1X2, double chance, totals, both teams to score, correct score, half-time outcomes.
- **Market comparison.** Margin removal from bookmaker odds and detection of gaps between the model and the market.
- **Quality checks.** Walk-forward backtesting (log-loss, Brier score, RPS) and probability calibration.
- **Prediction ledger.** Each forecast can be logged and later checked against the actual result.

## Installation

Requires Python 3.10+, `numpy` and [Claude Code](https://claude.com/claude-code).

```bash
git clone https://github.com/samatuly/football-predictor.git
cd football-predictor
claude --plugin-dir .
```

In Claude Code, the main skill is invoked with `/football-predictor:predict`, for example:

```
/football-predictor:predict Kazakhstan vs Slovakia, odds 4.2 / 3.4 / 1.9
```

## Data

Historical results are not stored in the repository. Download them into `data/raw/` using the links in `data/raw/*.SOURCE.txt`:

| File | Source | License |
|---|---|---|
| `results.csv` | [martj42/international_results](https://github.com/martj42/international_results) | CC0-1.0 |
| `en.teams.tsv` | [eloratings.net](https://www.eloratings.net) | not specified |

You can add your own results in `data/manual/*.csv`, using the same format plus a `source` column.

## Command-line usage

```bash
# Forecast a round of matches (Dixon–Coles)
python core/predict.py --fixtures core/tests/fixtures/2026-11-13.csv --as-of 2026-11-13

# Same with the Elo → Poisson model
python core/predict.py --model elo_poisson --elo <World.tsv> --fixtures core/tests/fixtures/2026-11-13.csv

# Backtesting, calibration and model comparison
python core/backtest_cli.py         --results data/raw/results.csv --start 2010-01-01
python core/calibrate_cli.py        --results data/raw/results.csv
python core/calibrate_totals_cli.py --results data/raw/results.csv
python core/compare_cli.py          --results data/raw/results.csv

# Tests
python -m unittest discover -s core/tests
```

Fixtures file format:

```
home,away,odds_1,odds_x,odds_2,odds_under25,odds_over25,neutral
```

Teams are identified by eloratings.net codes. Odds and `neutral` are optional.

## Project structure

| Path | Purpose |
|---|---|
| `skills/` | Claude Code skills: prediction, data, odds, backtesting, ratings |
| `agents/` | Helper agents: match context research, model review |
| `core/predictor_core/` | Models, markets, metrics, data handling |
| `core/*.py` | Command-line tools |
| `core/tests/` | Tests |

## Roadmap

- [x] Elo → Poisson, markets, margin removal, prediction ledger
- [x] Backtesting and calibration (1X2, totals)
- [x] Dixon–Coles as the primary model
- [ ] Club competitions, xG, blending the model with market odds
- [ ] Checking the ledger against results, tournament simulation

> Skill prompts and generated reports are currently in Russian.

## Disclaimer

This project is for research and educational purposes only.

- The model outputs **probability estimates**, not predictions of certain outcomes and **not betting advice**.
- Football is highly random. Even a well-calibrated model will be wrong on many individual matches.
- A gap between the model and the bookmaker's odds is not a guaranteed edge. Models can miss information the market has, such as injuries, line-ups or motivation.
- Past backtest performance does not guarantee future results.
- The author accepts no responsibility for any financial losses resulting from use of this software.
- If you choose to bet, follow the laws of your jurisdiction, only bet what you can afford to lose, and seek help if gambling stops being fun (for example, [BeGambleAware](https://www.begambleaware.org)).

## License

[MIT](LICENSE). Borrowed ideas and data sources are listed in [NOTICE.md](NOTICE.md).
