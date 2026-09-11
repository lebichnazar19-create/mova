"""Міст до заліза пристрою через termux-api.

Єдине місце в усьому проєкті, де є `subprocess`. Жодна інша частина мови
(лексер, парсер, компілятор, VM) не повинна імпортувати subprocess напряму.

Режим без пристрою (`--без-пристрою` / БЕЗ_ПРИСТРОЮ=1) вмикається функцією
`увімкнути_симуляцію()` — тоді усі виклики просто друкують те, що вони
зробили б, і повертають розумні заглушки. Потрібен для тестів на комп'ютері
без Termux:API і для CI.
"""

import json
import shutil
import subprocess

from .помилки import ПомилкаВиконання

ТАЙМАУТ_СЕК = 5

_СИМУЛЯЦІЯ = False


def увімкнути_симуляцію(увімкнено=True):
    global _СИМУЛЯЦІЯ
    _СИМУЛЯЦІЯ = увімкнено


def _немає_утиліти(команда):
    return ПомилкаВиконання(
        f"Утиліта «{команда}» не знайдена. Встанови пакет termux-api "
        f"(`pkg install termux-api`) і застосунок Termux:API з F-Droid."
    )


def _виконати(команда, *аргументи, ввід=None):
    """Запустити termux-* утиліту і повернути її stdout (текст)."""
    якщо_симуляція = _СИМУЛЯЦІЯ
    if якщо_симуляція:
        print(f"[симуляція пристрою] {команда} {' '.join(map(str, аргументи))}")
        return ""

    if shutil.which(команда) is None:
        raise _немає_утиліти(команда)

    try:
        результат = subprocess.run(
            [команда, *[str(а) for а in аргументи]],
            input=ввід,
            capture_output=True,
            text=True,
            timeout=ТАЙМАУТ_СЕК,
        )
    except subprocess.TimeoutExpired:
        raise ПомилкаВиконання(
            f"Утиліта «{команда}» не відповіла за {ТАЙМАУТ_СЕК} секунд (таймаут)."
        )
    except OSError as e:
        raise ПомилкаВиконання(f"Не вдалося запустити «{команда}»: {e}")

    if результат.returncode != 0:
        повідомлення = (результат.stderr or результат.stdout or "").strip()
        raise ПомилкаВиконання(
            f"Утиліта «{команда}» завершилась з помилкою"
            + (f": {повідомлення}" if повідомлення else ".")
        )
    return результат.stdout


def _виконати_без_очікування(команда, *аргументи):
    """Запустити termux-* утиліту, не чекаючи на її завершення (fire-and-forget).

    Потрібно для вібрації: termux-vibrate фізично спрацьовує одразу, але сам
    процес не завжди вчасно повертає керування (спостережено на реальному
    пристрої) — і тоді звичайний _виконати() з таймаутом 5с помилково валить
    вібро, яка насправді відпрацювала. Результат виконання нам тут і не
    потрібен, тож просто запускаємо процес і одразу йдемо далі.
    """
    if _СИМУЛЯЦІЯ:
        print(f"[симуляція пристрою] {команда} {' '.join(map(str, аргументи))}")
        return

    if shutil.which(команда) is None:
        raise _немає_утиліти(команда)

    try:
        subprocess.Popen(
            [команда, *[str(а) for а in аргументи]],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as e:
        raise ПомилкаВиконання(f"Не вдалося запустити «{команда}»: {e}")


def _json_або_помилка(текст, команда):
    if not текст.strip():
        return {}
    try:
        return json.loads(текст)
    except json.JSONDecodeError:
        raise ПомилкаВиконання(f"Утиліта «{команда}» повернула не-JSON відповідь: {текст!r}")


# ---- функції мови, що відповідають таблиці з ТЗ -----------------------------

def вібруй(мс):
    if not isinstance(мс, (int, float)) or isinstance(мс, bool):
        raise ПомилкаВиконання("Функція «вібруй» очікує число (мілісекунди).")
    # fire-and-forget — див. докладніше в _виконати_без_очікування()
    _виконати_без_очікування("termux-vibrate", "-d", int(мс))
    return None


def сповісти(назва, текст):
    _виконати("termux-notification", "-t", str(назва), "-c", str(текст))
    return None


def скажи(текст):
    _виконати("termux-tts-speak", str(текст))
    return None


def тост(текст):
    _виконати("termux-toast", str(текст))
    return None


def яскравість(рівень):
    if not isinstance(рівень, (int, float)) or isinstance(рівень, bool):
        raise ПомилкаВиконання("Функція «яскравість» очікує число від 0 до 255.")
    _виконати("termux-brightness", int(рівень))
    return None


def гучність(рівень):
    _виконати("termux-volume", "music", int(рівень))
    return None


def батарея():
    вивід = _виконати("termux-battery-status")
    if _СИМУЛЯЦІЯ:
        return {"percentage": 100, "status": "СИМУЛЯЦІЯ", "temperature": 25.0}
    return _json_або_помилка(вивід, "termux-battery-status")


def ліхтар(увімкнено):
    _виконати("termux-torch", "on" if увімкнено else "off")
    return None


def буфер():
    return _виконати("termux-clipboard-get").rstrip("\n")


def запиши_буфер(текст):
    _виконати("termux-clipboard-set", str(текст))
    return None


def датчик(назва):
    вивід = _виконати("termux-sensor", "-s", str(назва), "-n", "1")
    if _СИМУЛЯЦІЯ:
        return {назва: {"values": []}}
    return _json_або_помилка(вивід, "termux-sensor")


def зніми(шлях):
    _виконати("termux-camera-photo", str(шлях))
    return None


def місце():
    вивід = _виконати("termux-location")
    if _СИМУЛЯЦІЯ:
        return {"latitude": 0.0, "longitude": 0.0}
    return _json_або_помилка(вивід, "termux-location")


def відкрий(шлях):
    """Відкрити файл системним переглядачем (termux-open). Використовується
    зсередини ядро/малюнок.py — покажи() зберігає SVG і кличе цю функцію,
    щоб subprocess лишався лише в цьому модулі."""
    _виконати_без_очікування("termux-open", str(шлях))
    return None
