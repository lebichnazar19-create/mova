"""Зупинка виконання ззовні (кнопка «Стоп» у застосунку): ВМ.зупинено."""
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from yadro.kompilyator import компілювати
from yadro.parser import парсити_текст
from yadro.vm import ВМ, ВиконанняЗупинено
from zapusk import виконати_код, ПОВІДОМЛЕННЯ_ЗУПИНЕНО

НЕСКІНЧЕННИЙ = "хай н = 0\nпоки істина\n    хай н = н + 1\n"


def _зупинити_через(вм, сек):
    def _():
        time.sleep(сек)
        вм.зупинено = True
    threading.Thread(target=_, daemon=True).start()


def test_прапорець_зупиняє_нескінченний_цикл():
    вм = ВМ(без_пристрою=True)
    _зупинити_через(вм, 0.2)
    старт = time.monotonic()
    with pytest.raises(ВиконанняЗупинено):
        вм.виконати(компілювати(парсити_текст(НЕСКІНЧЕННИЙ)))
    assert time.monotonic() - старт < 3


def test_прапорець_перериває_довгий_спи():
    вм = ВМ(без_пристрою=True)
    _зупинити_через(вм, 0.2)
    старт = time.monotonic()
    with pytest.raises(ВиконанняЗупинено):
        вм.виконати(компілювати(парсити_текст("спи(30)\n")))
    assert time.monotonic() - старт < 3


def test_виконати_код_повертає_зупинено():
    тримач = {}

    def при_старті(вм):
        тримач["вм"] = вм
        _зупинити_через(вм, 0.2)

    вивід, успіх = виконати_код('друкуй("старт")\n' + НЕСКІНЧЕННИЙ, при_старті=при_старті)
    assert not успіх
    assert вивід == "старт\n" + ПОВІДОМЛЕННЯ_ЗУПИНЕНО + "\n"
    assert тримач["вм"].зупинено


def test_без_зупинки_працює_як_раніше():
    вивід, успіх = виконати_код('друкуй(1 + 1)', при_старті=lambda вм: None)
    assert успіх and вивід == "2\n"
