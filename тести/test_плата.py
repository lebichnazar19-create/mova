"""1.3: зв'язок з платами (yadro/plata.py) — протокол, симуляція, вбудовані
дії мови, вибір транспорту, помилки українською; агенти в agent/
реалізують ті самі коди команд."""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from yadro import plata as п
from yadro.errors import ПомилкаВиконання
from yadro.kompilyator import компілювати
from yadro.parser import парсити_текст
from yadro.vm import виконати_байткод

КОРІНЬ = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _чисто():
    п.увімкнути_симуляцію(True)
    п.задати_транспорт(None)
    п.відключись()
    yield
    п.відключись()
    п.задати_транспорт(None)
    п.увімкнути_симуляцію(False)


def запустити(джерело, capsys):
    виконати_байткод(компілювати(парсити_текст(джерело)), без_пристрою=True)
    return capsys.readouterr().out


# ---- протокол --------------------------------------------------------------------

def test_запакувати_розпакувати():
    assert п.запакувати(п.КОМАНДА["зачекай"], 0, 500) == bytes.fromhex("060001f4")
    assert п.запакувати(п.КОМАНДА["пиши"], 2, 1) == bytes.fromhex("02020001")
    assert п.розпакувати(bytes.fromhex("000001")) == (0, 1)
    assert п.розпакувати(bytes.fromhex("020000")) == (2, 0)
    with pytest.raises(ПомилкаВиконання):
        п.запакувати(1, 2, 70000)
    with pytest.raises(ПомилкаВиконання):
        п.розпакувати(b"\x00\x00")


def test_агенти_мають_ті_самі_коди_що_й_протокол():
    for файл in ("agent/agent_arduino/agent_arduino.ino", "agent/agent_esp32/agent_esp32.ino"):
        текст = (КОРІНЬ / файл).read_text(encoding="utf-8")
        коди = dict(re.findall(r"CMD_(\w+) = (\d+)", текст))
        assert коди == {"PIN": "1", "WRITE": "2", "READ": "3", "ANALOG": "4", "PWM": "5", "DELAY": "6", "PING": "7", "BLINK": "8"}
        assert re.search(r"ST_OK = 0, ST_UNKNOWN = 1, ST_BAD_PIN = 2, ST_BAD_VALUE = 3", текст)
        assert f"PROTOCOL_VERSION = {п.ВЕРСІЯ_ПРОТОКОЛУ}" in текст
        assert "Serial.begin(115200)" in текст
    assert "WiFi.softAP" in (КОРІНЬ / "agent/agent_esp32/agent_esp32.ino").read_text(encoding="utf-8")
    assert "WiFi" not in (КОРІНЬ / "agent/agent_arduino/agent_arduino.ino").read_text(encoding="utf-8")
    протокол = (КОРІНЬ / "PROTOCOL.md").read_text(encoding="utf-8")
    for назва, код in п.КОМАНДА.items():
        assert f"| {код} |" in протокол, назва


# ---- симуляція і вбудовані дії -------------------------------------------------

def test_симуляція_наскрізь_у_програмі(capsys):
    вивід = запустити(
        'друкуй(плати())\n'
        'друкуй(підключись("USB"))\n'
        'пін(2, вихід)\nпиши(2, 1)\nдрукуй(читай(2))\n'
        'пін(7, вхід_підтяжка)\nдрукуй(читай(7))\n'
        'шим(9, 128)\nдрукуй(аналог(0))\n'
        'зачекай(50)\nвідключись()\nдрукуй("готово")\n',
        capsys,
    )
    assert вивід.strip().split("\n") == ["[Симуляція]", "Симуляція", "1", "1", "0", "готово"]


def test_зачекай_виконується_на_платі_і_триває():
    п.підключись("Симуляція")
    старт = time.monotonic()
    п.зачекай(150)
    assert 0.12 <= time.monotonic() - старт < 1.0
    сим = п._підключення
    assert сим.журнал[-1] == (п.КОМАНДА["зачекай"], 0, 150)


def test_режими_рядком_числом_і_помилки_значень():
    п.підключись("Симуляція")
    п.пін(3, "вихід")
    п.пін(4, 2)
    сим = п._підключення
    assert сим.режими == {3: 0, 4: 2}
    with pytest.raises(ПомилкаВиконання) as info:
        п.пін(3, "вгору")
    assert "вихід, вхід або вхід_підтяжка" in str(info.value)
    with pytest.raises(ПомилкаВиконання):
        п.пиши(3, 2)
    with pytest.raises(ПомилкаВиконання):
        п.шим(3, 300)
    with pytest.raises(ПомилкаВиконання):
        п.читай(300)
    with pytest.raises(ПомилкаВиконання):
        п.зачекай(-1)
    п.пиши(3, True)
    assert сим.піни[3] == 1


def test_без_підключення_зрозуміла_помилка(capsys):
    for код in ("пиши(2, 1)\n", "читай(2)\n", "зачекай(10)\n", "пін(2, вихід)\n"):
        with pytest.raises(ПомилкаВиконання) as info:
            запустити(код, capsys)
        assert "Плата не підключена" in str(info.value) and 'підключись("USB")' in str(info.value)
    # у програмі це ловиться «спробуй», а не валить Python
    вивід = запустити('спробуй\n    пиши(2, 1)\nякщо помилка\n    друкуй(помилка)\n', capsys)
    assert вивід.startswith("Плата не підключена")


def test_перевірити_блимає_вбудованим_світлодіодом():
    п.підключись("Симуляція")
    п.перевірити(3)
    assert п._підключення.піни["LED"] == 3 and п.підключено() == "Симуляція"


def test_статус_помилки_від_плати_текстом():
    п.підключись("Симуляція")
    п._підключення._відповідь = b""
    п._підключення.send = lambda дані: setattr(п._підключення, "_відповідь", b"\x02\x00\x00")
    with pytest.raises(ПомилкаВиконання) as info:
        п.читай(99)
    assert "немає такого піна" in str(info.value)


def test_плата_не_відповідає():
    п.підключись("Симуляція")
    п._підключення.send = lambda дані: setattr(п._підключення, "_відповідь", b"")
    with pytest.raises(ПомилкаВиконання) as info:
        п.читай(1)
    assert "не відповідає" in str(info.value)


def test_інша_версія_протоколу_відхиляється():
    class Старий(п.Симуляція):
        def send(self, дані):
            self._відповідь = b"\x00\x00\x09"
    п.задати_транспорт(Старий())
    with pytest.raises(ПомилкаВиконання) as info:
        п.підключись("USB")
    assert "протокол інший" in str(info.value) and п.підключено() is None


# ---- вибір транспорту (без симуляції) --------------------------------------------

def test_вибір_транспорту_за_назвою():
    п.увімкнути_симуляцію(False)
    assert п.обрати_транспорт("USB") == ("usb", {"індекс": 0})
    assert п.обрати_транспорт("USB:1") == ("usb", {"індекс": 1})
    assert п.обрати_транспорт("USB: CH340") == ("usb", {"індекс": 0})
    assert п.обрати_транспорт("Wi-Fi") == ("wifi", {"хост": "192.168.4.1", "порт": 5555})
    assert п.обрати_транспорт("Wi-Fi: 192.168.4.1") == ("wifi", {"хост": "192.168.4.1", "порт": 5555})
    assert п.обрати_транспорт("tcp://10.0.0.5:6000") == ("wifi", {"хост": "10.0.0.5", "порт": 6000})
    assert п.обрати_транспорт("192.168.1.7") == ("wifi", {"хост": "192.168.1.7", "порт": 5555})
    assert п.обрати_транспорт("Симуляція") == ("симуляція", {})
    with pytest.raises(ПомилкаВиконання) as info:
        п.обрати_транспорт("щось")
    assert "Невідома плата" in str(info.value)
    with pytest.raises(ПомилкаВиконання):
        п.обрати_транспорт("")


def test_usb_на_компютері_дає_зрозумілу_помилку():
    п.увімкнути_симуляцію(False)
    if "jnius" in sys.modules or __import__("importlib").util.find_spec("jnius"):
        pytest.skip("тут є pyjnius")
    with pytest.raises(ПомилкаВиконання) as info:
        п.підключись("USB")
    assert "лише в застосунку на Android" in str(info.value)


def test_wifi_без_плати_дає_зрозумілу_помилку():
    п.увімкнути_симуляцію(False)
    with pytest.raises(ПомилкаВиконання) as info:
        п.підключись("tcp://127.0.0.1:1")   # порт 1 — точно ніхто не слухає
    assert "по Wi-Fi" in str(info.value)


def test_wifi_транспорт_з_фальшивим_агентом():
    """WifiTcp наскрізь: TCP-сервер у потоці відповідає як агент."""
    import socket
    import struct
    import threading

    п.увімкнути_симуляцію(False)
    сервер = socket.socket()
    сервер.bind(("127.0.0.1", 0))
    сервер.listen(1)
    порт = сервер.getsockname()[1]
    сим = п.Симуляція()

    def агент():
        з, _ = сервер.accept()
        з.settimeout(3)
        try:
            while True:
                запит = z_recv(з, 4)
                if not запит:
                    break
                сим.send(запит)
                з.sendall(сим.recv(3))
        finally:
            з.close()

    def z_recv(з, n):
        д = b""
        while len(д) < n:
            ш = з.recv(n - len(д))
            if not ш:
                return д
            д += ш
        return д

    потік = threading.Thread(target=агент, daemon=True)
    потік.start()
    assert п.підключись(f"tcp://127.0.0.1:{порт}") == f"Wi-Fi: 127.0.0.1:{порт}"
    п.пін(5, "вихід")
    п.пиши(5, 1)
    assert п.читай(5) == 1
    п.відключись()
    потік.join(2)
    сервер.close()
    assert сим.піни[5] == 1


def test_приклад_блимавка_розбирається_і_йде_в_симуляції(capsys):
    текст = (КОРІНЬ / "приклади" / "блимавка.мова").read_text(encoding="utf-8")
    # нескінченний цикл — обмежимо: замість «поки істина» три ітерації
    текст = текст.replace("поки істина", "для к у [1, 2, 3]")
    запустити(текст, capsys)
    assert п.підключено() == "Симуляція" and п._підключення.піни[2] == 0


def test_довідка_і_константи_режимів(capsys):
    from yadro import dovidka
    for імя in п.РЕЖИМ:
        assert dovidka.опис(імя)
    вивід = запустити("друкуй(вихід, вхід, вхід_підтяжка)\n", capsys)
    assert вивід.split() == ["вихід", "вхід", "вхід_підтяжка"]
