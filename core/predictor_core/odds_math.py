"""Bookmaker margin removal and comparison with the model."""
from __future__ import annotations


def overround(odds: list[float]) -> float:
    """Margin: sum of inverse odds minus 1."""
    return sum(1 / o for o in odds) - 1


def devig_proportional(odds: list[float]) -> list[float]:
    """Proportional margin removal."""
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]


def devig_power(odds: list[float]) -> list[float]:
    """Power method: p_i = (1/o_i)^k, with k chosen so that the sum is 1.

    Cuts outsiders more than the proportional method (accounts for the market skew towards them).
    """
    inv = [1 / o for o in odds]
    lo, hi = 1.0, 10.0
    for _ in range(200):
        k = (lo + hi) / 2
        if sum(x**k for x in inv) > 1:
            lo = k
        else:
            hi = k
    return [x**k for x in inv]


def expected_value(prob: float, odds: float) -> float:
    """Expected profit per 1 unit staked at probability prob."""
    return prob * odds - 1
