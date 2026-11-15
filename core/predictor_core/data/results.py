"""International match results: martj42/international_results (CC0-1.0).

Columns: date,home_team,away_team,home_score,away_score,tournament,city,country,neutral.
Teams are identified by name, but names are consistent within one dataset (the dataset author
handles country renames). Join with other sources by ID only.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Match:
    date: date
    home: str
    away: str
    home_goals: int
    away_goals: int
    tournament: str
    neutral: bool

    @property
    def outcome(self) -> int:
        """0 = home win, 1 = draw, 2 = away win."""
        if self.home_goals > self.away_goals:
            return 0
        return 1 if self.home_goals == self.away_goals else 2


def load_results(path: str) -> list[Match]:
    out: list[Match] = []
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["home_score"] in ("", "NA") or r["away_score"] in ("", "NA"):
                continue  # future or unplayed matches
            out.append(Match(
                date=date.fromisoformat(r["date"]),
                home=r["home_team"], away=r["away_team"],
                home_goals=int(r["home_score"]), away_goals=int(r["away_score"]),
                tournament=r["tournament"],
                neutral=r["neutral"].strip().upper() == "TRUE",
            ))
    out.sort(key=lambda m: m.date)
    return out


def load_with_extra(path: str, extra_paths: list[str]) -> tuple[list[Match], dict]:
    """Main dataset + manual additions (data/manual/*.csv, same format plus a source column).

    A manual match is skipped if the main dataset already has a match with the same date
    and the same teams (the main dataset takes priority, so duplicates disappear once its author updates it).
    """
    base = load_results(path)
    seen = {(m.date, m.home, m.away) for m in base}
    added, dup = 0, 0
    for p in extra_paths:
        for m in load_results(p):
            if (m.date, m.home, m.away) in seen:
                dup += 1
                continue
            base.append(m)
            seen.add((m.date, m.home, m.away))
            added += 1
    base.sort(key=lambda m: m.date)
    return base, {"extra_files": [str(p) for p in extra_paths], "extra_added": added, "extra_duplicates": dup}
