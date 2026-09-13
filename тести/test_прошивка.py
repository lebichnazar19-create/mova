"""Етап 3: прошивання ESP32 (yadro/proshyvka.py) із симулятором
завантажувача (yadro/esp32_sym.py) — SLIP, кадри, контрольні суми, DTR/RTS,
успішна заливка і кожна відмова, дії мови в симуляції."""

import os
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from yadro import plata, proshyvka as п
from yadro.errors import ПомилкаВиконання
from yadro.esp32_sym import СимуляторESP32
from yadro.kompilyator import компілювати
from yadro.parser import парсити_текст
from yadro.vm import виконати_байткод


@pytest.fixture(autouse=True)
def _симуляція():
    plata.увімкнути_симуляцію(True)
    yield
    plata.увімкнути_симуляцію(False)
    п.при_прогресі = None


# ---- SLIP і кадри -------------------------------------------------------------------

def test_slip_кодування_і_екранування():
    assert п.slip_закодувати(b"\x01\xc0\x02\xdb\x03") == b"\xc0\x01\xdb\xdc\x02\xdb\xdd\x03\xc0"
    for дані in (b"", b"\xc0", b"\xdb", os.urandom(300)):
        assert п.slip_розкодувати(п.slip_закодувати(дані)[1:-1]) == дані
    with pytest.raises(ПомилкаВиконання):
        п.slip_розкодувати(b"\x01\xdb")
    with pytest.raises(ПомилкаВиконання):
        п.slip_розкодувати(b"\xdb\x01")


def test_контрольна_сума_і_пакети():
    assert п.контрольна_сума(b"") == 0xEF
    assert п.контрольна_сума(b"\xef") == 0
    assert п.контрольна_сума(b"\x01\x02") == 0xEF ^ 0x01 ^ 0x02
    пакет = п.запакувати_запит(п.CMD["READ_REG"], struct.pack("<I", 0x40001000))
    assert пакет == b"\x00\x0a\x04\x00\x00\x00\x00\x00" + struct.pack("<I", 0x40001000)
    команда, значення, дані, статус, помилка = п.розпакувати_відповідь(
        struct.pack("<BBHI", 1, 0x0A, 4, 0x00F01D83) + b"\x00\x00\x00\x00")
    assert (команда, значення, дані, статус, помилка) == (0x0A, 0x00F01D83, b"", 0, 0)
    with pytest.raises(ПомилкаВиконання):
        п.розпакувати_відповідь(b"\x00" * 5)
    with pytest.raises(ПомилкаВиконання):
        п.розпакувати_відповідь(struct.pack("<BBHI", 0, 0x0A, 4, 0) + b"\x00" * 4)


# ---- симулятор: успіх ------------------------------------------------------------------

def test_вхід_у_завантажувач_dtr_rts_sync_чип_mac_флеш():
    с = СимуляторESP32(mac="AA:BB:CC:DD:EE:FF")
    з = п.Завантажувач(с)
    assert з.підключитись() == "ESP32"
    assert с.у_завантажувачі and с.журнал[0] == "SYNC"
    assert з.mac() == "AA:BB:CC:DD:EE:FF"
    assert з.розмір_флешу_байт() == 4 * 1024 * 1024
    assert "SPI_ATTACH" in с.журнал and "WRITE_REG" in с.журнал


def test_без_послідовності_dtr_rts_плата_мовчить():
    с = СимуляторESP32()
    з = п.Завантажувач(с)
    with pytest.raises(ПомилкаВиконання) as info:
        з.sync()
    assert "не відповідає на SYNC" in str(info.value) and not с.у_завантажувачі


def test_заливка_блоками_по_4096_із_прогресом_і_перезавантаженням():
    с = СимуляторESP32(затримка=0.001)
    відсотки = []
    з = п.Завантажувач(с, прогрес=lambda в, т: відсотки.append(в))
    з.підключитись()
    образ = os.urandom(4096 * 3 + 100)
    assert з.записати(образ, 0x1000) == 4
    assert с.образ(0x1000)[:len(образ)] == образ
    assert с.образ(0x1000)[len(образ):] == b"\xFF" * (4096 * 4 - len(образ))
    assert відсотки[0] == 0 and відсотки[-1] == 100 and відсотки == sorted(відсотки)
    assert с.журнал.count("FLASH_DATA") == 4 and с.журнал[-1] == "FLASH_END"
    assert с.перезавантажень == 1 and not с.у_завантажувачі   # FLASH_END з reboot


def test_стерти_весь_флеш():
    с = СимуляторESP32()
    з = п.Завантажувач(с)
    з.підключитись()
    з.записати(b"\x01" * 100, 0)
    з.підключитись()
    assert з.стерти() == 4 * 1024 * 1024
    assert с.флеш == {} and с.стерто == 4 * 1024 * 1024


# ---- симулятор: кожна відмова ----------------------------------------------------------

def test_відмова_неправильна_контрольна_сума():
    с = СимуляторESP32(збій="контрольна_сума")
    з = п.Завантажувач(с)
    з.підключитись()
    with pytest.raises(ПомилкаВиконання) as info:
        з.записати(os.urandom(5000))
    assert "неправильна контрольна сума" in str(info.value)


def test_відмова_таймаут_sync():
    с = СимуляторESP32(збій="таймаут")
    з = п.Завантажувач(с)
    with pytest.raises(ПомилкаВиконання) as info:
        з.підключитись()
    assert "SYNC" in str(info.value) and с.журнал.count("SYNC") == п.СПРОБ_SYNC


def test_відмова_обрив_посеред_заливки(monkeypatch):
    monkeypatch.setattr(п, "ТАЙМАУТ_С", 0.3)
    с = СимуляторESP32(збій="обрив", обрив_після=2)
    з = п.Завантажувач(с)
    з.підключитись()
    with pytest.raises(ПомилкаВиконання) as info:
        з.записати(os.urandom(4096 * 5))
    assert "не відповідає на FLASH_DATA" in str(info.value)
    assert len(с.флеш) == 2   # записано рівно два блоки до обриву


def test_зіпсована_сума_з_боку_телефона_відхиляється_платою():
    с = СимуляторESP32()
    з = п.Завантажувач(с)
    з.підключитись()
    з.flash_begin(4096, 0)
    with pytest.raises(ПомилкаВиконання) as info:
        з._команда("FLASH_DATA", struct.pack("<IIII", 4096, 0, 0, 0) + b"\x00" * 4096, сума=0x12)
    assert "контрольна сума" in str(info.value)


def test_flash_end_без_усіх_блоків_відхиляється():
    с = СимуляторESP32()
    з = п.Завантажувач(с)
    з.підключитись()
    з.flash_begin(4096 * 2, 0)
    з.flash_data(b"\x01" * 4096, 0)
    with pytest.raises(ПомилкаВиконання) as info:
        з.flash_end()
    assert "не вдалося виконати" in str(info.value)


# ---- дії мови -----------------------------------------------------------------------

def запустити(джерело, capsys, тека=None):
    виконати_байткод(компілювати(парсити_текст(джерело)), без_пристрою=True, тека_файлів=тека)
    return capsys.readouterr().out


def test_проший_стерти_інфо_у_програмі(tmp_path, capsys):
    (tmp_path / "агент.bin").write_bytes(os.urandom(9000))
    вивід = запустити(
        'хай х = інфо("USB")\nдрукуй(х.чип, х.флеш)\n'
        'друкуй("блоків:", проший("агент.bin", "USB"))\n'
        'друкуй("стерто:", стерти("Симуляція"))\n',
        capsys, str(tmp_path),
    )
    рядки = вивід.strip().split("\n")
    assert рядки[0] == "ESP32 4194304"
    assert any(р.startswith("Заливка: 0%") for р in рядки) and any(р.startswith("Заливка: 100%") for р in рядки)
    assert "блоків: 3" in вивід and "стерто: 4194304" in вивід


def test_помилки_дій_українською(tmp_path, capsys):
    (tmp_path / "не_бін.txt").write_text("x", encoding="utf-8")
    (tmp_path / "є.bin").write_bytes(b"\x01" * 10)
    for код, текст in (
        ('проший("нема.bin", "USB")\n', "не знайдено"),
        ('проший("не_бін.txt", "USB")\n', "має бути файлом .bin"),
        ('проший("є.bin", "Wi-Fi")\n', "потрібен USB-кабель"),
    ):
        with pytest.raises(ПомилкаВиконання) as info:
            запустити(код, capsys, str(tmp_path))
        assert текст in str(info.value), код
    # без симуляції: невідома назва — помилка (у симуляції будь-яка назва йде в симулятор)
    plata.увімкнути_симуляцію(False)
    with pytest.raises(ПомилкаВиконання) as info:
        запустити('інфо("щось")\n', capsys, str(tmp_path))
    assert "Невідома плата" in str(info.value)
    вивід = запустити('спробуй\n    інфо("tcp://1.2.3.4")\nякщо помилка\n    друкуй(помилка)\n', capsys)
    assert "USB-кабель" in вивід


def test_прогрес_віддається_застосунку():
    отримано = []
    п.при_прогресі = lambda в, т: отримано.append(в)
    с = СимуляторESP32()
    з = п.Завантажувач(с)
    з.підключитись()
    з.записати(os.urandom(4096 * 2))
    assert отримано[0] == 0 and отримано[-1] == 100


def test_знайти_агента(tmp_path):
    assert п.знайти_агента(tmp_path, tmp_path) is None
    (tmp_path / "agent_esp32.bin").write_bytes(b"\x00")
    assert п.знайти_агента(tmp_path, tmp_path).name == "agent_esp32.bin"
    корінь = tmp_path / "репо"
    (корінь / "agent" / "agent_esp32").mkdir(parents=True)
    (корінь / п.ФАЙЛ_АГЕНТА).write_bytes(b"\x00")
    assert п.знайти_агента(корінь, None) == корінь / п.ФАЙЛ_АГЕНТА
