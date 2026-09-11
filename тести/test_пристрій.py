"""Регресійні тести на вібрацію: termux-vibrate фізично спрацьовує, але
процес не завжди вчасно повертає керування — вібруй() має бути
fire-and-forget (subprocess.Popen, без очікування), а не чекати завершення
з таймаутом, інакше VM помилково кидає «Помилка виконання» попри те, що
вібрація реально відбулась."""

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import ядро.пристрій as пристрій
from ядро.помилки import ПомилкаВиконання


@pytest.fixture(autouse=True)
def _без_симуляції():
    # ці тести перевіряють саме "реальний" шлях (Popen), тому вимикаємо
    # симуляцію на час тесту й гарантовано повертаємо її назад
    пристрій.увімкнути_симуляцію(False)
    yield
    пристрій.увімкнути_симуляцію(False)


class _ФальшивийПроцесЩоНіколиНеЗавершується:
    """Імітує саме той збій, що стався на реальному пристрої: команда вже
    зробила свою справу, але сам процес "живе" довше, ніж будь-який
    розумний таймаут. Якщо вібруй() випадково почне його чекати (.wait()/
    .communicate()) — тест зависне і його вб'є pytest-таймаут середовища,
    що само по собі буде ознакою регресії."""

    def __init__(self, *а, **кв):
        pass

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired(cmd="termux-vibrate", timeout=timeout or 9999)

    def communicate(self, *а, **кв):
        raise subprocess.TimeoutExpired(cmd="termux-vibrate", timeout=9999)


def test_вібруй_не_чекає_на_завершення_процесу(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda ім_я: "/usr/bin/termux-vibrate")
    monkeypatch.setattr(
        subprocess, "Popen", lambda *а, **кв: _ФальшивийПроцесЩоНіколиНеЗавершується()
    )

    старт = time.monotonic()
    результат = пристрій.вібруй(1000)
    тривалість = time.monotonic() - старт

    assert результат is None
    assert тривалість < 1.0, "вібруй() не повинен чекати на завершення процесу"


def test_вібруй_використовує_popen_а_не_run(monkeypatch):
    виклики = {"popen": 0, "run": 0}

    def фейковий_which(ім_я):
        return "/usr/bin/termux-vibrate"

    def фейковий_popen(*а, **кв):
        виклики["popen"] += 1
        return _ФальшивийПроцесЩоНіколиНеЗавершується()

    def фейковий_run(*а, **кв):
        виклики["run"] += 1
        raise AssertionError("вібруй() не повинен використовувати subprocess.run")

    import shutil
    monkeypatch.setattr(shutil, "which", фейковий_which)
    monkeypatch.setattr(subprocess, "Popen", фейковий_popen)
    monkeypatch.setattr(subprocess, "run", фейковий_run)

    пристрій.вібруй(1000)

    assert виклики["popen"] == 1
    assert виклики["run"] == 0


def test_вібруй_відсутня_утиліта_дає_чисту_помилку(monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, "which", lambda ім_я: None)
    with pytest.raises(ПомилкаВиконання, match="не знайдена"):
        пристрій.вібруй(200)


def test_вібруй_неправильний_тип_аргументу():
    with pytest.raises(ПомилкаВиконання, match="число"):
        пристрій.вібруй("довго")


def test_вібруй_у_симуляції_друкує_і_не_викликає_subprocess(monkeypatch, capsys):
    пристрій.увімкнути_симуляцію(True)
    try:
        def заборонено(*а, **кв):
            raise AssertionError("у симуляції subprocess не повинен викликатись")

        monkeypatch.setattr(subprocess, "Popen", заборонено)
        monkeypatch.setattr(subprocess, "run", заборонено)

        пристрій.вібруй(500)
        вивід = capsys.readouterr().out
        assert "termux-vibrate" in вивід
        assert "500" in вивід
    finally:
        пристрій.увімкнути_симуляцію(False)
