# football-predictor

Плагин Claude Code для вероятностного прогноза футбольных матчей.

## Статус

| Этап | Состояние |
|---|---|
| 0. Каркас | готов |
| 1. Ядро Elo → Пуассон, рынки, снятие маржи, журнал | готово |
| 2. Бэктест | готов |
| 3a. Калибровка 1X2 (сборные) | готова |
| 3b. Калибровка рынков голов | готова |
| 3c. Диксон–Коулз (сборные) | готов, лучше Elo |
| 3d. DC — основная модель `/predict` | готово |
| 4. Клубы, xG, сравнение с рынком | следующий |

## Подключение к Claude Code

Для разработки (на одну сессию, нужен CLI `claude`):

```bash
claude --plugin-dir .
```

Скилл вызывается как `/football-predictor:predict`; после правок — `/reload-plugins`.
Проверка манифеста и заголовков: `claude plugin validate .`.

## Быстрый старт

```bash
python core/predict.py --fixtures core/tests/fixtures/2026-11-13.csv --as-of 2026-11-13          # dixon_coles, нужен numpy
python core/predict.py --model elo_poisson --elo <World.tsv> --fixtures core/tests/fixtures/2026-11-13.csv
python -m unittest discover -s core/tests
python core/backtest_cli.py --results data/raw/results.csv --start 2010-01-01
python core/calibrate_cli.py --results data/raw/results.csv
python core/calibrate_totals_cli.py --results data/raw/results.csv
python core/compare_cli.py --results data/raw/results.csv   # нужен numpy
```

Формат `fixtures.csv`: `home,away,odds_1,odds_x,odds_2,odds_under25,odds_over25,neutral`
(коды команд как в eloratings.net; коэффициенты и `neutral` необязательны).

Это вероятностная оценка, а не совет делать ставки.
