"""Forecast ledger (JSONL): one line per match, append-only."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def append(path: str | Path, record: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"logged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
