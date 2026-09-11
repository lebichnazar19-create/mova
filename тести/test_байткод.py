"""Етап 6: збереження/завантаження .байт файлів (мова -к / мова -б)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import мова as мова_cli


def test_компілювати_записує_байт_файл(tmp_path):
    джерело = tmp_path / "приклад.мова"
    джерело.write_text('друкуй("з файлу байткоду:", 2 + 2)\n', encoding="utf-8")

    мова_cli.команда_компілювати(str(джерело))

    байт_файл = tmp_path / "приклад.байт"
    assert байт_файл.exists()
    вміст = json.loads(байт_файл.read_text(encoding="utf-8"))
    assert вміст["версія"] == 1
    assert "код" in вміст and "константи" in вміст
    assert any(інстр[0] == "HALT" for інстр in вміст["код"])


def test_виконати_байт_файл_дає_той_самий_результат(tmp_path, capsys):
    джерело = tmp_path / "приклад2.мова"
    джерело.write_text('друкуй("значення:", 6 * 7)\n', encoding="utf-8")
    мова_cli.команда_компілювати(str(джерело))
    capsys.readouterr()  # відкинути повідомлення "Скомпільовано -> ..."

    байт_файл = tmp_path / "приклад2.байт"
    мова_cli.команда_виконати_байткод(str(байт_файл), без_пристрою=True)

    assert capsys.readouterr().out.strip() == "значення: 42"
