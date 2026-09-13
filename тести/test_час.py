"""0.7: дата й час."""

import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yadro.kompilyator import компілювати
from yadro.parser import парсити_текст
from yadro.vm import виконати_байткод


def запустити(джерело, capsys):
    виконати_байткод(компілювати(парсити_текст(джерело)), без_пристрою=True)
    return capsys.readouterr().out


def test_зараз_і_сьогодні_формат(capsys):
    вивід = запустити("друкуй(зараз())\nдрукуй(сьогодні())\n", capsys).strip().split("\n")
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", вивід[0])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", вивід[1])
    assert вивід[0].startswith(вивід[1])
    assert вивід[1] == datetime.now().strftime("%Y-%m-%d")


def test_година_хвилина_цілі_в_межах(capsys):
    г, х = запустити("друкуй(година(), хвилина())\n", capsys).split()
    assert 0 <= int(г) <= 23 and 0 <= int(х) <= 59


def test_секунди_вимірюють_тривалість(capsys):
    вивід = запустити(
        "хай старт = секунди()\nспи(0.05)\nхай минуло = секунди() - старт\n"
        "друкуй(минуло >= 0.04, минуло < 5)\n",
        capsys,
    )
    assert вивід.split() == ["істина", "істина"]
