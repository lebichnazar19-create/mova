"""«Зробити застосунок»: програма мовою «Мова» стає окремим Android-застосунком.

створити_застосунок(корінь, назва, код) кладе в теку корінь/застосунки/назва/:
    програма.мова   — сама програма;
    main.py         — запускач без редактора (виконує програма.мова, показує
                      вивід, поле для «питай», кнопки програми, полотно креслення);
    buildozer.spec  — назва, латинське ім'я пакета, іконка, ті самі
                      налаштування Android, що й у головного застосунку;
    icon.png        — іконка (колір від назви), згенерована без сторонніх бібліотек.
Ядро мови (yadro/, zapusk.py, vidzhety.py) у теку НЕ копіюється — його
докладає workflow .github/workflows/zastosunky.yml під час збірки, тож у
репозиторії ядро лишається в одному місці.

Без Kivy; тестується на комп'ютері (тести/test_застосунки.py). Запуск з
командного рядка: python3 zastosunky.py Назва програма.мова [корінь_репо]
"""

import re
import struct
import sys
import zlib
from pathlib import Path

ТЕКА = "застосунки"
ФАЙЛ_ПРОГРАМИ = "програма.мова"
ФАЙЛИ_ЯДРА = ("yadro", "zapusk.py", "vidzhety.py")  # докладає workflow при збірці

_ЗАБОРОНЕНО_В_НАЗВІ = re.compile(r'[\\/:*?"<>|\x00-\x1f]')

_ТРАНСЛІТ = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie",
    "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l",
    "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ю": "iu",
    "я": "ia", "ь": "", "'": "", "ʼ": "", "’": "",
}


class ПомилкаЗастосунку(Exception):
    pass


def безпечна_назва(назва):
    """Назва застосунку -> ім'я теки: без символів шляху, обрізана; None,
    якщо порожня."""
    назва = _ЗАБОРОНЕНО_В_НАЗВІ.sub("", назва or "").strip().strip(".")
    назва = re.sub(r"\s+", " ", назва)
    return назва[:40] or None


def слаг(назва):
    """Латинське ім'я пакета для Android: [a-z0-9_], починається з літери."""
    літери = []
    for ч in (назва or "").lower():
        if ч in _ТРАНСЛІТ:
            літери.append(_ТРАНСЛІТ[ч])
        elif ч.isascii() and ч.isalnum():
            літери.append(ч)
        else:
            літери.append("_")
    с = re.sub(r"_+", "_", "".join(літери)).strip("_")
    if not с or not с[0].isalpha():
        с = "mova_" + (с or "app")
    return с[:40]


# ---- іконка ---------------------------------------------------------------------

def _png(ширина, висота, рядки):
    """PNG (RGB, 8 біт) із готових рядків байтів — лише stdlib."""
    def шматок(тег, дані):
        return (struct.pack(">I", len(дані)) + тег + дані
                + struct.pack(">I", zlib.crc32(тег + дані) & 0xFFFFFFFF))
    сирі = b"".join(b"\x00" + р for р in рядки)
    return (b"\x89PNG\r\n\x1a\n"
            + шматок(b"IHDR", struct.pack(">IIBBBBB", ширина, висота, 8, 2, 0, 0, 0))
            + шматок(b"IDAT", zlib.compress(сирі, 9))
            + шматок(b"IEND", b""))


def _колір_назви(назва):
    """Насичений колір, стабільний для назви (за хешем)."""
    h = zlib.crc32(назва.encode("utf-8")) % 360
    c, x = 1.0, 1 - abs((h / 60) % 2 - 1)
    r, g, b = [(c, x, 0), (x, c, 0), (0, c, x), (0, x, c), (x, 0, c), (c, 0, x)][int(h // 60) % 6]
    return tuple(int(40 + 160 * к) for к in (r, g, b))


def іконка_png(назва, розмір=192):
    """Квадрат із заокругленими кутами кольору назви і білим колом посередині."""
    ф = _колір_назви(назва)
    білий = (250, 250, 250)
    р = розмір / 2
    радіус_кута = розмір * 0.22
    радіус_кола = розмір * 0.28
    рядки = []
    for y in range(розмір):
        рядок = bytearray()
        for x in range(розмір):
            cx, cy = x + 0.5, y + 0.5
            # заокруглений квадрат: відстань до найближчого «внутрішнього» кута
            dx = max(abs(cx - р) - (р - радіус_кута), 0)
            dy = max(abs(cy - р) - (р - радіус_кута), 0)
            if dx * dx + dy * dy > радіус_кута * радіус_кута:
                колір = (255, 255, 255)
            elif (cx - р) ** 2 + (cy - р) ** 2 <= радіус_кола ** 2:
                колір = білий
            else:
                колір = ф
            рядок.extend(колір)
        рядки.append(bytes(рядок))
    return _png(розмір, розмір, рядки)


# ---- файли застосунку ---------------------------------------------------------------

СПЕЦИФІКАЦІЯ = """[app]
title = {назва}
package.name = {слаг}
package.domain = org.mova
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,мова
source.exclude_dirs = __pycache__,.buildozer,bin
source.exclude_patterns = *.pyc,*.байт
version = {версія}
requirements = python3,kivy==2.3.0
p4a.branch = v2024.01.21
orientation = portrait
fullscreen = 0
icon.filename = icon.png
android.archs = arm64-v8a
android.build_tools_version = 34.0.0
android.api = 34
android.ndk = 25b
log_level = 2
warn_on_root = 1

[buildozer]
log_level = 2
"""

ЗАПУСКАЧ = '''#!/usr/bin/env python3
"""Запускач застосунку «{назва}»: виконує програма.мова (мова «Мова») без
редактора. Згенеровано zastosunky.py; ядро (yadro/, zapusk.py, vidzhety.py)
докладає workflow під час збірки APK."""

import sys
import threading
import traceback
from pathlib import Path

сюди = Path(__file__).resolve().parent
if str(сюди) not in sys.path:
    sys.path.insert(0, str(сюди))

НАЗВА = {назва!r}
ФАЙЛ_ПРОГРАМИ = "програма.мова"

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

from vidzhety import ПолотноКреслення, прокручуваний_ряд, прокручуваний_текст

Window.softinput_mode = "resize"
МОНО = "RobotoMono-Regular"


class Застосунок(App):
    title = НАЗВА

    def build(self):
        try:
            return self._зібрати()
        except Exception:
            прокрутка, _ = прокручуваний_текст("ПОМИЛКА в build():\\n\\n" + traceback.format_exc())
            return прокрутка

    def _зібрати(self):
        self._потік = None
        self._вм = None
        self._стоп_запитано = False
        self._чекаю_відповідь = threading.Event()
        self._відповідь = None
        self._креслення = None
        self._показано_креслення = False
        корінь = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(4))

        self._кн_запуск = Button(text="Запустити знову", on_release=self._запустити)
        self._кн_стоп = Button(text="Стоп", on_release=self._стоп, disabled=True)
        self._кн_креслення = Button(text="Креслення", on_release=lambda *_: self._показати_креслення(not self._показано_креслення))
        for к in (self._кн_запуск, self._кн_стоп, self._кн_креслення):
            к.size_hint_x = None
            к.width = dp(11) * len(к.text) + dp(28)
        корінь.add_widget(прокручуваний_ряд([self._кн_запуск, self._кн_стоп, self._кн_креслення], висота=dp(44)))

        self._прокрутка_виводу, self.вивід = прокручуваний_текст("", шрифт=МОНО, розмір=sp(14))
        self._низ = BoxLayout(orientation="vertical")
        self._низ.add_widget(self._прокрутка_виводу)
        self._полотно = ПолотноКреслення()
        self._панель_креслення = BoxLayout(orientation="vertical")
        ряд = BoxLayout(size_hint_y=None, height=dp(36), spacing=dp(4))
        ряд.add_widget(Button(text="Вмістити все", on_release=lambda *_: self._полотно.вмістити()))
        ряд.add_widget(Button(text="До виводу", on_release=lambda *_: self._показати_креслення(False)))
        self._панель_креслення.add_widget(ряд)
        self._панель_креслення.add_widget(self._полотно)
        корінь.add_widget(self._низ)

        # рядок вводу для «питай»
        self._ряд_вводу = BoxLayout(orientation="vertical", size_hint_y=None, height=0, opacity=0, spacing=dp(2))
        self._запит = Label(text="", size_hint_y=None, height=dp(22), halign="left", font_size=sp(14), color=(0.2, 0.45, 0.2, 1))
        self._запит.bind(width=lambda і, ш: setattr(і, "text_size", (ш - dp(8), None)))
        ряд2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(4))
        self._поле = TextInput(multiline=False, font_name=МОНО, font_size=sp(15))
        self._поле.bind(on_text_validate=self._надіслати)
        ряд2.add_widget(self._поле)
        ряд2.add_widget(Button(text="Надіслати", size_hint_x=None, width=dp(120), on_release=self._надіслати))
        self._ряд_вводу.add_widget(self._запит)
        self._ряд_вводу.add_widget(ряд2)
        корінь.add_widget(self._ряд_вводу)

        # кнопки програми
        self._кнопки = BoxLayout(size_hint=(None, 1), spacing=dp(4))
        self._кнопки.bind(minimum_width=self._кнопки.setter("width"))
        self._прокрутка_кнопок = прокручуваний_ряд([], висота=0)
        self._прокрутка_кнопок.clear_widgets()
        self._прокрутка_кнопок.add_widget(self._кнопки)
        self._прокрутка_кнопок.opacity = 0
        корінь.add_widget(self._прокрутка_кнопок)

        Clock.schedule_once(lambda dt: self._запустити(), 0.2)
        return корінь

    # ---- виконання ---------------------------------------------------------

    def _запустити(self, *_):
        if self._потік is not None and self._потік.is_alive():
            return
        self._стоп_запитано = False
        self._прибрати_кнопки()
        self._кн_запуск.disabled = True
        self._кн_стоп.disabled = False
        self.вивід.text = "Виконується…"
        self._потік = threading.Thread(target=self._у_потоці, daemon=True)
        self._потік.start()

    def _у_потоці(self):
        try:
            from zapusk import виконати_код
            код = (сюди / ФАЙЛ_ПРОГРАМИ).read_text(encoding="utf-8")
            текст, успіх = виконати_код(
                код, при_старті=self._запамʼятати_вм, тека=self.user_data_dir,
                питай=self._питай, кнопка=self._додати_кнопку,
                оновити_вивід=self._оновити_вивід, при_кресленні=self._при_кресленні,
            )
        except Exception:
            текст = "Внутрішня помилка:\\n" + traceback.format_exc()
        if not текст.strip():
            текст = "(програма нічого не надрукувала)"
        Clock.schedule_once(lambda dt: self._готово(текст), 0)

    def _запамʼятати_вм(self, вм):
        self._вм = вм
        if self._стоп_запитано:
            вм.зупинено = True

    def _готово(self, текст):
        self._сховати_ввід()
        self._прибрати_кнопки()
        self.вивід.text = текст
        self._вм = None
        self._потік = None
        self._кн_запуск.disabled = False
        self._кн_стоп.disabled = True

    def _стоп(self, *_):
        self._стоп_запитано = True
        if self._вм is not None:
            self._вм.зупинено = True

    def _оновити_вивід(self, текст):
        Clock.schedule_once(lambda dt: setattr(self.вивід, "text", текст), 0)

    # ---- питай -------------------------------------------------------------

    def _питай(self, запит):
        from yadro.vm import ВиконанняЗупинено
        self._відповідь = None
        self._чекаю_відповідь.clear()
        Clock.schedule_once(lambda dt: self._показати_ввід(запит), 0)
        while not self._чекаю_відповідь.wait(0.1):
            if self._стоп_запитано:
                Clock.schedule_once(lambda dt: self._сховати_ввід(), 0)
                raise ВиконанняЗупинено()
        return self._відповідь or ""

    def _показати_ввід(self, запит):
        self._запит.text = запит.strip() or "Введи значення:"
        self._поле.text = ""
        self._ряд_вводу.height = dp(68)
        self._ряд_вводу.opacity = 1
        self._поле.focus = True

    def _сховати_ввід(self):
        self._ряд_вводу.height = 0
        self._ряд_вводу.opacity = 0

    def _надіслати(self, *_):
        if self._чекаю_відповідь.is_set():
            return
        self._відповідь = self._поле.text
        self._сховати_ввід()
        self._чекаю_відповідь.set()

    # ---- кнопки програми ----------------------------------------------------

    def _додати_кнопку(self, напис, натиснути):
        def створити(dt):
            к = Button(text=напис, size_hint_x=None, width=max(dp(60), dp(11) * len(напис) + dp(24)), font_size=sp(15))
            к.bind(on_release=lambda *_: натиснути())
            self._кнопки.add_widget(к)
            self._прокрутка_кнопок.height = dp(44)
            self._прокрутка_кнопок.opacity = 1
        Clock.schedule_once(створити, 0)

    def _прибрати_кнопки(self):
        self._кнопки.clear_widgets()
        self._прокрутка_кнопок.height = 0
        self._прокрутка_кнопок.opacity = 0

    # ---- креслення ----------------------------------------------------------

    def _при_кресленні(self, креслення):
        def показати(dt):
            self._креслення = креслення
            self._полотно.показати(креслення)
            self._показати_креслення(True)
        Clock.schedule_once(показати, 0)

    def _показати_креслення(self, так):
        if так and self._креслення is None:
            return
        if так == self._показано_креслення:
            return
        self._показано_креслення = так
        self._низ.clear_widgets()
        self._низ.add_widget(self._панель_креслення if так else self._прокрутка_виводу)
        if так:
            Clock.schedule_once(lambda dt: self._полотно.вмістити(), 0)


if __name__ == "__main__":
    Застосунок().run()
'''


def файли_застосунку(назва, код, версія="1.0"):
    """{ім'я_файлу: вміст (str або bytes)} — усе, що лягає в теку застосунку."""
    ім_я = безпечна_назва(назва)
    if ім_я is None:
        raise ПомилкаЗастосунку("Назва застосунку порожня або складається лише зі службових символів.")
    if not (код or "").strip():
        raise ПомилкаЗастосунку("Програма порожня — спершу напиши код.")
    if not код.endswith("\n"):
        код += "\n"
    return {
        ФАЙЛ_ПРОГРАМИ: код,
        "main.py": ЗАПУСКАЧ.format(назва=ім_я),
        "buildozer.spec": СПЕЦИФІКАЦІЯ.format(назва=ім_я, слаг=слаг(ім_я), версія=версія),
        "icon.png": іконка_png(ім_я),
    }


def створити_застосунок(корінь, назва, код, версія="1.0"):
    """Записати файли в корінь/застосунки/назва/. Повертає (тека, [імена файлів])."""
    файли = файли_застосунку(назва, код, версія)
    тека = Path(корінь) / ТЕКА / безпечна_назва(назва)
    тека.mkdir(parents=True, exist_ok=True)
    for ім_я, вміст in файли.items():
        if isinstance(вміст, bytes):
            (тека / ім_я).write_bytes(вміст)
        else:
            (тека / ім_я).write_text(вміст, encoding="utf-8")
    return тека, list(файли)


def список_застосунків(корінь):
    тека = Path(корінь) / ТЕКА
    if not тека.is_dir():
        return []
    return sorted(п.name for п in тека.iterdir() if п.is_dir() and (п / ФАЙЛ_ПРОГРАМИ).is_file())


def шляхи_для_публікації(назва, файли):
    """Шляхи файлів відносно кореня репозиторію — для github.опублікувати."""
    ім_я = безпечна_назва(назва)
    return {f"{ТЕКА}/{ім_я}/{ф}": в for ф, в in файли.items()}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Використання: python3 zastosunky.py Назва програма.мова [корінь_репо]")
        sys.exit(2)
    _назва, _файл = sys.argv[1], sys.argv[2]
    _корінь = sys.argv[3] if len(sys.argv) > 3 else str(Path(__file__).resolve().parent)
    _тека, _файли = створити_застосунок(_корінь, _назва, Path(_файл).read_text(encoding="utf-8"))
    print(f"Створено {_тека}: {', '.join(_файли)}")
