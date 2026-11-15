"""Mapping between eloratings.net codes (World.tsv) and team names in the martj42 results dataset.

team_map.csv is built from eloratings.net/en.teams.tsv (code + name variants):
a row is added only if exactly one name variant EXACTLY matches a name in results.csv.
There is no fuzzy matching; pairs whose names differ (Czechia / Czech Republic) are added
by hand after human review. A code without a row is "unmatched"
and is reported; no forecast is made for it.
"""
from __future__ import annotations

import csv
from pathlib import Path

MAP_FILE = Path(__file__).with_name("team_map.csv")


def load_team_map(path: Path = MAP_FILE) -> dict[str, str]:
    with open(path, encoding="utf-8") as fh:
        return {r["elo_code"].strip(): r["results_name"].strip() for r in csv.DictReader(fh)}
