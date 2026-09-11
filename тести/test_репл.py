"""Етап 6: REPL — стан (змінні, дії) має жити між окремо введеними рядками."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ядро import repl


def _запустити_з_вводом(рядки, monkeypatch, capsys):
    введення = iter(рядки)

    def фейковий_input(prompt=""):
        try:
            return next(введення)
        except StopIteration:
            raise EOFError

    monkeypatch.setattr("builtins.input", фейковий_input)
    repl.запустити(без_пристрою=True)
    return capsys.readouterr().out


def test_глобальна_змінна_живе_між_рядками(monkeypatch, capsys):
    вивід = _запустити_з_вводом(
        ["хай х = 5", "друкуй(х)", "х = х + 1", "друкуй(х)", "вихід"],
        monkeypatch, capsys,
    )
    assert "5" in вивід.splitlines()
    assert "6" in вивід.splitlines()


def test_дія_оголошена_в_одному_рядку_викликається_в_іншому(monkeypatch, capsys):
    вивід = _запустити_з_вводом(
        [
            "дія подвій(n)",
            "    поверни n * 2",
            "",             # порожній рядок завершує тіло дії
            "друкуй(подвій(21))",
            "вихід",
        ],
        monkeypatch, capsys,
    )
    assert "42" in вивід.splitlines()


def test_помилка_не_перериває_сеанс(monkeypatch, capsys):
    вивід = _запустити_з_вводом(
        ["друкуй(невідома_змінна)", 'друкуй("живий")', "вихід"],
        monkeypatch, capsys,
    )
    assert "Невідома змінна" in вивід
    assert "живий" in вивід


def test_eof_замість_вихід_теж_завершує_сеанс(monkeypatch, capsys):
    # без явного "вихід" — просто закінчився ввід (Ctrl+D)
    вивід = _запустити_з_вводом(["друкуй(1)"], monkeypatch, capsys)
    assert "1" in вивід.splitlines()
