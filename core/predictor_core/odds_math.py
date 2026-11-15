"""Снятие маржи букмекера и сравнение с моделью."""
from __future__ import annotations


def overround(odds: list[float]) -> float:
    """Маржа: сумма обратных коэффициентов минус 1."""
    return sum(1 / o for o in odds) - 1


def devig_proportional(odds: list[float]) -> list[float]:
    """Пропорциональное снятие маржи (метод отчёта 13.11)."""
    inv = [1 / o for o in odds]
    s = sum(inv)
    return [x / s for x in inv]


def devig_power(odds: list[float]) -> list[float]:
    """Степенной метод: p_i = (1/o_i)^k, k подбирается так, чтобы сумма = 1.

    Сильнее, чем пропорциональный, режет аутсайдеров (учитывает перекос рынка в их сторону).
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
    """Ожидаемая прибыль на 1 единицу ставки при вероятности prob."""
    return prob * odds - 1
