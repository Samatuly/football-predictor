"""Чтение World.tsv с eloratings.net.

Столбцы (по файлу проекта от 13.11.2026): 0 — место, 2 — код страны, 3 — рейтинг.
Официальной документации формата нет; если файл изменится, проверь столбцы.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass


@dataclass(frozen=True)
class EloEntry:
    code: str
    rank: int
    rating: int


def load_world_tsv(path: str) -> dict[str, EloEntry]:
    out: dict[str, EloEntry] = {}
    with open(path, encoding="utf-8") as fh:
        for row in csv.reader(fh, delimiter="\t"):
            if len(row) < 4:
                continue
            try:
                out[row[2]] = EloEntry(row[2], int(row[0]), int(row[3]))
            except ValueError:
                continue
    return out
