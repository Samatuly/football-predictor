"""Quality metrics for probabilistic 1X2 forecasts.

The outcome is encoded as an index: 0 = home win, 1 = draw, 2 = away win. probs = (p1, px, p2).
For all metrics, lower is better.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

EPS = 1e-12


def log_loss(probs: Sequence[float], outcome: int) -> float:
    return -math.log(max(probs[outcome], EPS))


def brier(probs: Sequence[float], outcome: int) -> float:
    """Multi-class Brier score: sum of squared errors over the three outcomes (0..2)."""
    return sum((p - (1.0 if k == outcome else 0.0)) ** 2 for k, p in enumerate(probs))


def rps(probs: Sequence[float], outcome: int) -> float:
    """Ranked Probability Score: respects the ordering home < draw < away (0..1)."""
    cp = co = s = 0.0
    for k in range(len(probs) - 1):
        cp += probs[k]
        co += 1.0 if k == outcome else 0.0
        s += (cp - co) ** 2
    return s / (len(probs) - 1)


def summarize(rows: list[tuple[Sequence[float], int]]) -> dict[str, float]:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    return {
        "n": n,
        "log_loss": sum(log_loss(p, o) for p, o in rows) / n,
        "brier": sum(brier(p, o) for p, o in rows) / n,
        "rps": sum(rps(p, o) for p, o in rows) / n,
        "accuracy": sum(1 for p, o in rows if max(range(3), key=lambda k: p[k]) == o) / n,
    }


def calibration(rows: list[tuple[Sequence[float], int]], outcome: int, bins: int = 10) -> list[dict]:
    """Calibration table for one outcome: mean forecast vs observed frequency per bin."""
    buckets: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, o in rows:
        b = min(int(p[outcome] * bins), bins - 1)
        buckets[b].append((p[outcome], 1 if o == outcome else 0))
    out = []
    for i, b in enumerate(buckets):
        if not b:
            continue
        out.append({
            "bin": f"{i / bins:.1f}-{(i + 1) / bins:.1f}",
            "n": len(b),
            "predicted": sum(x for x, _ in b) / len(b),
            "observed": sum(y for _, y in b) / len(b),
        })
    return out
