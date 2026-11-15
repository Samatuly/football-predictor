"""Соответствие кодов eloratings.net (World.tsv) и названий в наборе результатов martj42.

Таблица team_map.csv построена из eloratings.net/en.teams.tsv (код + варианты названия):
строка добавлена, только если ровно один вариант названия ТОЧНО совпал с названием в results.csv.
Нечёткого поиска нет; пары, где названия различаются (Czechia / Czech Republic), добавляются
вручную после проверки человеком. Код без строки — «не сопоставлен»
и попадает в отчёт, прогноз по нему не делается.
"""
from __future__ import annotations

import csv
from pathlib import Path

MAP_FILE = Path(__file__).with_name("team_map.csv")


def load_team_map(path: Path = MAP_FILE) -> dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        return {r["elo_code"].strip(): r["results_name"].strip() for r in csv.DictReader(fh)}
