"""Дата й час: зараз(), сьогодні(), година(), хвилина(), секунди()."""

import time
from datetime import datetime


def зараз():
    """Рядок «РРРР-ММ-ДД ГГ:ХХ:СС» за місцевим часом."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def сьогодні():
    return datetime.now().strftime("%Y-%m-%d")


def година():
    return datetime.now().hour


def хвилина():
    return datetime.now().minute


def секунди():
    """Секунди з довільної точки відліку (дробове число) — для вимірювання
    тривалості: хай старт = секунди() ... друкуй(секунди() - старт)."""
    return time.monotonic()
