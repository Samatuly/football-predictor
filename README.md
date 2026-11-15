# football-predictor — football match probability model for Claude Code

![version](https://img.shields.io/badge/version-0.1.0-blue) ![status](https://img.shields.io/badge/status-pre--release-orange) ![python](https://img.shields.io/badge/python-3.10%2B-blue) ![license](https://img.shields.io/badge/license-MIT-green)

**A Claude Code plugin that forecasts football (soccer) matches with Dixon–Coles and Elo–Poisson models, prices the main betting markets, and compares the result with bookmaker odds after removing the margin.**

Built with Python and NumPy. Validated with leak-free walk-forward backtests on 15,000+ international matches (2010–2026).

> ⚠️ The model produces probability estimates, not betting advice. See the [Disclaimer](#disclaimer).
>
> **Status: v0.1.0 pre-release.** The core models and the `predict` skill work; several other skills are still placeholders (see the [Roadmap](#roadmap)).

## Table of contents

[Results](#results) · [Features](#features) · [Example](#example-output) · [Installation](#installation) · [Methodology](#methodology) · [Data](#data) · [Command-line usage](#command-line-usage) · [Project structure](#project-structure) · [Roadmap](#roadmap) · [Disclaimer](#disclaimer) · [License](#license)

## Results

Walk-forward test on **15,685 international matches, 2010 – 6 Oct 2026**. Lower is better. Parameters were tuned on 2005–2009 only, and the test window never took part in tuning.

| Model | 1X2 log-loss | Brier | RPS | Over 2.5 | BTTS |
|---|---|---|---|---|---|
| Elo → Poisson (calibrated) | 0.8862 | 0.5220 | 0.1738 | 0.6793 | **0.6763** |
| **Dixon–Coles** | **0.8748** | **0.5148** | **0.1711** | **0.6744** | 0.6770 |

Calibration (model vs. observed frequency):

| | Goals per match | Draws | Over 1.5 | Over 2.5 | Over 3.5 | BTTS |
|---|---|---|---|---|---|---|
| Dixon–Coles | 2.65 | 23.8% | 71.7% | 47.3% | 27.4% | 42.1% |
| Observed | 2.67 | 23.4% | 71.8% | 48.0% | 27.6% | 42.5% |

**Limitation, stated plainly:** on a small sample of 9 matches (13 Nov 2026) bookmaker odds were more accurate than the model (1X2 log-loss 0.722 vs. 0.862). The model has no lineups, injuries or xG, so it should not be expected to beat the market on individual matches.

## Features

- **Two models.** Primary: Dixon–Coles with time decay. Fallback: Elo → Poisson.
- **Markets.** 1X2, double chance, totals, both teams to score (BTTS), correct score, half-time outcomes.
- **Market comparison.** Margin removal from bookmaker odds and detection of gaps between the model and the market.
- **Quality checks.** Walk-forward backtesting (log-loss, Brier score, RPS) and probability calibration.
- **Prediction ledger.** Each forecast can be logged and later checked against the actual result.
- **Tested.** Unit tests include a check that the model never sees future matches.

## Example output

```bash
python core/predict.py --fixtures core/tests/fixtures/2026-11-13.csv --as-of 2026-11-13
```

```
Model dixon_coles. Not betting advice.
WARNING: Stronger than elo_poisson in the 2010–2026 backtest; on 13 Nov the bookmaker odds were more accurate on 1X2.

NL-GR | λ 1.82-0.87 | 59%/24%/17% O2.5 50% BTTS 49% | 1-0(12%) 2-0(11%) 1-1(11%) | vs market -2/+3/-1 pp, O2.5 -13 pp
RS-DE | λ 1.21-1.95 | 23%/23%/54% O2.5 61% BTTS 60% | 1-1(10%) 1-2(10%) 0-2(8%) | vs market +13/+8/-22 pp, O2.5 -4 pp
```

How to read a line:

- `NL-GR`: Netherlands vs Greece (eloratings.net team codes).
- `λ 1.82-0.87`: expected goals for home and away.
- `59%/24%/17%`: home win / draw / away win.
- `O2.5`: over 2.5 goals. `BTTS`: both teams to score.
- `1-0(12%) 2-0(11%) 1-1(11%)`: the most likely correct scores.
- `vs market`: difference from the margin-free bookmaker probabilities, in percentage points.

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

## Methodology

- **Model.** Every national team has its own attacking and defensive strength, plus a shared home-advantage factor and the Dixon–Coles low-score correction ρ for 0-0, 1-0, 0-1 and 1-1.
- **Weighting.** Matches are weighted by recency (half-life 1,460 days, chosen on 2005–2009), over an 8-year window with L2 regularisation.
- **No look-ahead.** The model is refitted every 30 days using only matches before the fit date. This is enforced by a unit test (`test_no_future_leak`).
- **Evaluation.** Log-loss, Brier score and ranked probability score (RPS) on 1X2, plus log-loss on goal markets. Accuracy of picked outcomes is deliberately not the headline metric.
- **Market comparison.** Bookmaker margin is always removed before comparing probabilities.

References: Dixon & Coles (1997), *Modelling Association Football Scores and Inefficiencies in the Football Betting Market*. Borrowed ideas are listed in [NOTICE.md](NOTICE.md).

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
- [ ] Skills `backtest`, `odds`, `ratings`, `track` (code exists for the first two)
- [ ] Club competitions, xG, blending the model with market odds
- [ ] Checking the ledger against results, tournament simulation

> The `predict` command-line output is in English. Skill prompts, market names in generated reports and some code comments are still in Russian.

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

---

**Keywords:** football prediction, soccer analytics, Dixon–Coles model, Elo rating, Poisson model, expected goals, betting odds margin removal, probability calibration, walk-forward backtesting, Claude Code plugin.
