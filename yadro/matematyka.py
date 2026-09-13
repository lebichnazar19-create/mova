"""Математичні вбудовані дії: корінь, степінь, округли, модуль, мінімум,
максимум, синус, косинус, тангенс, арктангенс2, випадкове. Стала ПІ
живе у ВМ (глобальна змінна, задана на старті)."""

import math
import random

from .errors import ПомилкаВиконання

ПІ = math.pi


def _є_число(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _число(x, дія, що="аргумент"):
    if not _є_число(x):
        raise ПомилкаВиконання(f"Функція «{дія}» очікує число як {що}, а отримала {_тип(x)}.")
    return x


def _тип(x):
    from .vm import _тип_укр
    return _тип_укр(x)


def _ціле_якщо_можна(r):
    if isinstance(r, float) and r.is_integer() and abs(r) < 1e15:
        return int(r)
    return r


def корінь(x):
    _число(x, "корінь")
    if x < 0:
        raise ПомилкаВиконання(f"Корінь з від'ємного числа ({x}) не існує.")
    return _ціле_якщо_можна(math.sqrt(x))


def степінь(a, b):
    _число(a, "степінь", "основу")
    _число(b, "степінь", "показник")
    try:
        r = a ** b
    except (OverflowError, ZeroDivisionError):
        raise ПомилкаВиконання(f"Не вдалося обчислити {a} у степені {b}.")
    if isinstance(r, complex):
        raise ПомилкаВиконання(f"Дробовий степінь від'ємного числа ({a} у степені {b}) не є дійсним числом.")
    return _ціле_якщо_можна(r) if isinstance(r, float) else r


def округли(x, знаків=0):
    _число(x, "округли")
    if not isinstance(знаків, int) or isinstance(знаків, bool):
        raise ПомилкаВиконання("Функція «округли» очікує ціле число знаків після коми.")
    # «половина — вгору» (2.5 -> 3, -2.5 -> -3), а не банківське round()
    множник = 10 ** знаків
    r = math.copysign(math.floor(abs(x) * множник + 0.5), x) / множник
    if знаків <= 0:
        return int(r)
    return round(r, знаків)


def модуль(x):
    _число(x, "модуль")
    return abs(x)


def _числа_для(дія, args):
    if len(args) == 1 and isinstance(args[0], list):
        args = args[0]
    if not args:
        raise ПомилкаВиконання(f"Функція «{дія}» очікує хоча б одне число або непорожній список.")
    for x in args:
        _число(x, дія)
    return args


def мінімум(*args):
    return min(_числа_для("мінімум", args))


def максимум(*args):
    return max(_числа_для("максимум", args))


def синус(x):
    return math.sin(_число(x, "синус", "кут у радіанах"))


def косинус(x):
    return math.cos(_число(x, "косинус", "кут у радіанах"))


def тангенс(x):
    return math.tan(_число(x, "тангенс", "кут у радіанах"))


def арктангенс2(y, x):
    _число(y, "арктангенс2", "y")
    _число(x, "арктангенс2", "x")
    return math.atan2(y, x)


def випадкове(від, до):
    """Ціле від..до включно, якщо обидві межі цілі; інакше дробове."""
    _число(від, "випадкове", "нижню межу")
    _число(до, "випадкове", "верхню межу")
    if від > до:
        raise ПомилкаВиконання(f"Функція «випадкове»: нижня межа ({від}) більша за верхню ({до}).")
    if isinstance(від, int) and isinstance(до, int):
        return random.randint(від, до)
    return random.uniform(від, до)
