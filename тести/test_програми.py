import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yadro.kompilyator import компілювати
from yadro.parser import парсити_текст
from yadro.vm import виконати_байткод

ПРИКЛАДИ = Path(__file__).resolve().parent.parent / "приклади"


def запустити_файл(шлях, capsys):
    джерело = шлях.read_text(encoding="utf-8")
    байткод = компілювати(парсити_текст(джерело))
    виконати_байткод(байткод, без_пристрою=True)
    return capsys.readouterr().out


def test_привіт(capsys):
    вивід = запустити_файл(ПРИКЛАДИ / "привіт.мова", capsys)
    assert "Привіт, світ!" in вивід
    assert "2 + 2 * 3 = 8" in вивід
    assert "Привіт, Termux!" in вивід
    assert "Рахую: 1" in вивід and "Рахую: 3" in вивід


def test_батарея(capsys):
    вивід = запустити_файл(ПРИКЛАДИ / "батарея.мова", capsys)
    assert "Заряд:" in вивід
    assert "Стан:" in вивід


def test_будильник_компілюється_і_виконується(capsys):
    # у симуляції батарея() завжди повертає 100%, тому має спрацювати гілка "норм"
    вивід = запустити_файл(ПРИКЛАДИ / "будильник.мова", capsys)
    assert "Поточний заряд:" in вивід
    assert "будильник мовчить" in вивід


def test_будильник_розряджена_батарея_вібрує_і_сповіщає(capsys, monkeypatch):
    import yadro.prystriy as пристрій

    виклики = []
    monkeypatch.setattr(пристрій, "батарея", lambda: {"percentage": 5, "status": "тест"})
    monkeypatch.setattr(пристрій, "вібруй", lambda мс: виклики.append(("вібруй", мс)))
    monkeypatch.setattr(
        пристрій, "сповісти", lambda н, т: виклики.append(("сповісти", н, т))
    )

    джерело = (ПРИКЛАДИ / "будильник.мова").read_text(encoding="utf-8")
    байткод = компілювати(парсити_текст(джерело))
    from yadro.vm import ВМ

    вм = ВМ(без_пристрою=False)
    # підмінити прив'язки нативних функцій уже після їх реєстрації в __init__
    вм._native["батарея"] = пристрій.батарея
    вм._native["вібруй"] = пристрій.вібруй
    вм._native["сповісти"] = пристрій.сповісти
    вм.виконати(байткод)

    типи_викликів = [в[0] for в in виклики]
    assert типи_викликів.count("вібруй") == 3
    assert "сповісти" in типи_викликів
