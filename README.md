# football-predictor

**Плагин Claude Code для вероятностного прогноза футбольных матчей.**

Плагин оценивает силу команд, считает вероятности исходов и основных рынков и сравнивает их с коэффициентами букмекера, предварительно сняв маржу. Каждая модель проверена бэктестом на исторических матчах сборных.

> Плагин даёт вероятностную оценку, а не рекомендации для ставок.

## Возможности

- **Две модели.** Основная: Диксон–Коулз с затуханием по времени. Запасная: Elo → Пуассон.
- **Рынки.** 1X2, двойной шанс, тоталы, «обе забьют», точный счёт, исходы таймов.
- **Сравнение с рынком.** Снятие маржи с коэффициентов, поиск расхождений между моделью и букмекером.
- **Проверка качества.** Walk-forward бэктест (log-loss, Brier, RPS) и калибровка вероятностей.
- **Журнал прогнозов.** Каждый прогноз можно записать, чтобы потом сверить его с результатом.

## Установка

Нужны Python 3.10+, `numpy` и [Claude Code](https://claude.com/claude-code).

```bash
git clone https://github.com/samatuly/football-predictor.git
cd football-predictor
claude --plugin-dir .
```

В Claude Code основной скилл вызывается командой `/football-predictor:predict`, например:

```
/football-predictor:predict Казахстан — Словакия, коэффициенты 4.2 / 3.4 / 1.9
```

## Данные

Исторические результаты не хранятся в репозитории. Скачайте их в `data/raw/` по ссылкам из файлов `data/raw/*.SOURCE.txt`:

| Файл | Источник | Лицензия |
|---|---|---|
| `results.csv` | [martj42/international_results](https://github.com/martj42/international_results) | CC0-1.0 |
| `en.teams.tsv` | [eloratings.net](https://www.eloratings.net) | не указана |

Свои дополнительные результаты можно положить в `data/manual/*.csv`: тот же формат плюс столбец `source`.

## Запуск из командной строки

```bash
# Прогноз тура (Диксон–Коулз)
python core/predict.py --fixtures core/tests/fixtures/2026-11-13.csv --as-of 2026-11-13

# То же на модели Elo → Пуассон
python core/predict.py --model elo_poisson --elo <World.tsv> --fixtures core/tests/fixtures/2026-11-13.csv

# Бэктест, калибровка и сравнение моделей
python core/backtest_cli.py       --results data/raw/results.csv --start 2010-01-01
python core/calibrate_cli.py      --results data/raw/results.csv
python core/calibrate_totals_cli.py --results data/raw/results.csv
python core/compare_cli.py        --results data/raw/results.csv

# Тесты
python -m unittest discover -s core/tests
```

Формат файла матчей:

```
home,away,odds_1,odds_x,odds_2,odds_under25,odds_over25,neutral
```

Команды указываются кодами eloratings.net. Коэффициенты и `neutral` необязательны.

## Структура

| Путь | Назначение |
|---|---|
| `skills/` | Скиллы Claude Code: прогноз, данные, коэффициенты, бэктест, рейтинги |
| `agents/` | Вспомогательные агенты: сбор контекста матча, ревью модели |
| `core/predictor_core/` | Модели, рынки, метрики, работа с данными |
| `core/*.py` | Командные утилиты |
| `core/tests/` | Тесты |

## Дорожная карта

- [x] Elo → Пуассон, рынки, снятие маржи, журнал
- [x] Бэктест и калибровка (1X2, тоталы)
- [x] Диксон–Коулз как основная модель
- [ ] Клубные турниры, xG, смешивание модели с рынком
- [ ] Сверка журнала с результатами, симуляция турниров

## Лицензия

[MIT](LICENSE). Заимствованные идеи и источники перечислены в [NOTICE.md](NOTICE.md).
