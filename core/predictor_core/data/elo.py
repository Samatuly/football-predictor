"""Reader for World.tsv from eloratings.net.

Columns (from the project file of 13 Nov 2026): 0 = rank, 2 = country code, 3 = rating.
There is no official format documentation; if the file changes, check the columns.
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
