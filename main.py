#!/usr/bin/env python3
"""Точка входу Kivy-застосунку «Мова» для Android: редактор коду з запуском.

Екран: прокручувана панель кнопок («Виконати», «Стоп», «Очистити вивід»,
«Очистити код»), поле коду (моноширинний шрифт), панель швидких вставок
(дужки, лапки, ключові слова), знизу прокручуваний вивід. Код
автозберігається у user_data_dir/код.мова. Програма виконується в окремому
потоці, «Стоп» виставляє ВМ.зупинено — див. zapusk.виконати_код.

Уся робота з yadro/* іде через zapusk.виконати_код (без Kivy, тестується на
комп'ютері). Імпорти yadro/* не відбуваються на верхньому рівні: якщо щось
не імпортується саме в Android-збірці, застосунок усе одно підніме вікно й
покаже traceback разом із діагностикою (версія, listdir, sys.path) — і
продублює її у user_data_dir/crash.txt.
"""

import os
import sys
import threading
import traceback
from pathlib import Path

сюди = Path(__file__).resolve().parent
if str(сюди) not in sys.path:
    sys.path.insert(0, str(сюди))

# Тримати в синхроні з `version = ...` у buildozer.spec.
ВЕРСІЯ = "0.4"

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

# Вікно стискається над екранною клавіатурою, тож панель швидких кнопок
# (одразу під полем коду) лишається видимою над клавіатурою.
Window.softinput_mode = "resize"

МОНО = "RobotoMono-Regular"  # входить у Kivy, підтримує кирилицю
ФАЙЛ_КОДУ = "код.мова"

ПОЧАТКОВИЙ_КОД = (
    'друкуй("Привіт з Android!")\n'
    "хай а = [1, 2, 3]\n"
    "додай(а, 4)\n"
    'друкуй("Список:", а)\n'
    "дія у_квадраті(х)\n"
    "    поверни х * х\n"
    'друкуй("5 у квадраті =", у_квадраті(5))\n'
)

# (підпис, що вставити). Порожній підпис = взяти текст.
ШВИДКІ_ВСТАВКИ = [
    ("(", "("), (")", ")"), ("[", "["), ("]", "]"), ('"', '"'),
    ("=", " = "), (":", ":"), ("відступ", "    "),
    ("хай", "хай "), ("дія", "дія "), ("якщо", "якщо "),
    ("інакше", "інакше"), ("поки", "поки "), ("для", "для "),
    ("друкуй", "друкуй("), ("поверни", "поверни "),
]


def _шапка_діагностики():
    """Версія, вміст теки з main.py, sys.path — лише для крах-екрана."""
    рядки = [f"Мова, версія {ВЕРСІЯ}"]
    try:
        тека = os.path.dirname(os.path.abspath(__file__))
        рядки.append(f"os.listdir({тека!r}):")
        рядки.append(repr(sorted(os.listdir(тека))))
        шлях_yadro = os.path.join(тека, "yadro")
        рядки.append(f"os.listdir({шлях_yadro!r}):")
        try:
            рядки.append(repr(sorted(os.listdir(шлях_yadro))))
        except Exception as e:
            рядки.append(f"(не вдалося: {e!r})")
    except Exception as e:
        рядки.append(f"(діагностика теки не вдалася: {e!r})")
    рядки.append("sys.path:")
    рядки.extend(f"  {ш!r}" for ш in sys.path)
    return "\n".join(рядки)


def _записати_крешлог(текст, тека_даних):
    try:
        тека = Path(тека_даних)
        тека.mkdir(parents=True, exist_ok=True)
        (тека / "crash.txt").write_text(текст, encoding="utf-8")
    except Exception:
        pass


def _прокручуваний_текст(текст="", шрифт=None, розмір="15sp"):
    """ScrollView з Label, що переносить рядки й росте у висоту."""
    мітка = Label(
        text=текст, size_hint_y=None, halign="left", valign="top",
        font_size=розмір, **({"font_name": шрифт} if шрифт else {}),
    )
    мітка.bind(width=lambda і, ш: setattr(і, "text_size", (ш - dp(8), None)))
    мітка.bind(texture_size=lambda і, р: setattr(і, "height", р[1] + dp(8)))
    прокрутка = ScrollView()
    прокрутка.add_widget(мітка)
    return прокрутка, мітка


def _прокручуваний_ряд(кнопки, висота):
    """Горизонтально прокручуваний ряд віджетів фіксованої ширини."""
    ряд = BoxLayout(size_hint=(None, 1), spacing=dp(4))
    ряд.bind(minimum_width=ряд.setter("width"))
    for к in кнопки:
        ряд.add_widget(к)
    прокрутка = ScrollView(
        size_hint_y=None, height=висота, do_scroll_y=False, bar_width=0,
    )
    прокрутка.add_widget(ряд)
    return прокрутка


class МоваApp(App):
    title = "Мова"

    def build(self):
        try:
            return self._зібрати_редактор()
        except Exception:
            шапка = _шапка_діагностики()
            тіло = "ПОМИЛКА в build():\n\n" + traceback.format_exc()
            try:
                тека = self.user_data_dir
            except Exception:
                тека = str(Path.home())
            _записати_крешлог(шапка + "\n\n" + тіло, тека)
            прокрутка, _ = _прокручуваний_текст(тіло + "\n" + "-" * 40 + "\n" + шапка)
            return прокрутка

    # ---- екран редактора ------------------------------------------------

    def _зібрати_редактор(self):
        self._шлях_коду = Path(self.user_data_dir) / ФАЙЛ_КОДУ
        self._потік = None          # потік виконання (threading.Thread) або None
        self._вм = None             # ВМ поточного запуску — для «Стоп»
        self._стоп_запитано = False
        корінь = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(4))

        корінь.add_widget(self._панель_кнопок())

        self.код = TextInput(
            text=self._прочитати_код(), font_name=МОНО, font_size=sp(15),
            multiline=True, size_hint_y=0.55,
            auto_indent=True, do_wrap=False,
        )
        self.код.bind(text=self._зберегти_код)
        корінь.add_widget(self.код)

        корінь.add_widget(self._панель_вставок())

        self._прокрутка_виводу, self.вивід = _прокручуваний_текст(
            "Натисни «Виконати».", шрифт=МОНО, розмір=sp(14)
        )
        корінь.add_widget(self._прокрутка_виводу)
        return корінь

    def _панель_кнопок(self):
        """Верхній ряд дій. Горизонтально прокручуваний: на вузькому екрані
        чотири кнопки в один ряд не вміщаються."""
        self._кн_виконати = Button(text="Виконати", on_release=self._виконати)
        self._кн_стоп = Button(text="Стоп", on_release=self._стоп, disabled=True)
        кнопки = [
            self._кн_виконати,
            self._кн_стоп,
            Button(text="Очистити вивід", on_release=self._очистити),
            Button(text="Очистити код", on_release=self._очистити_код),
        ]
        for к in кнопки:
            к.size_hint_x = None
            к.width = dp(11) * len(к.text) + dp(28)
        return _прокручуваний_ряд(кнопки, висота=dp(44))

    def _панель_вставок(self):
        """Горизонтально прокручуваний ряд кнопок, що вставляють текст у
        позицію курсора поля коду."""
        кнопки = []
        for підпис, текст in ШВИДКІ_ВСТАВКИ:
            кнопка = Button(
                text=підпис, size_hint_x=None, font_size=sp(15),
                width=max(dp(40), dp(11) * len(підпис) + dp(16)),
            )
            кнопка.bind(on_release=lambda к, т=текст: self._вставити(т))
            кнопки.append(кнопка)
        return _прокручуваний_ряд(кнопки, висота=dp(44))

    # ---- дії --------------------------------------------------------------

    def _вставити(self, текст):
        self.код.insert_text(текст)
        # Дотик до кнопки знімає фокус із поля — повертаємо, щоб клавіатура
        # не ховалась і курсор лишався на місці.
        Clock.schedule_once(lambda dt: setattr(self.код, "focus", True), 0)

    def _виконати(self, *_):
        """Запускає програму в окремому потоці, щоб інтерфейс не завмирав
        на довгих циклах і «спи», а кнопка «Стоп» лишалась живою."""
        if self._потік is not None and self._потік.is_alive():
            return
        self._вм = None
        self._кн_виконати.disabled = True
        self._кн_стоп.disabled = False
        self.вивід.text = "Виконується…"
        код = self.код.text
        self._потік = threading.Thread(
            target=self._виконати_у_потоці, args=(код,), daemon=True
        )
        self._потік.start()

    def _виконати_у_потоці(self, код):
        try:
            from zapusk import виконати_код
            текст, успіх = виконати_код(код, при_старті=self._запамʼятати_вм)
        except Exception:
            текст, успіх = "Внутрішня помилка:\n" + traceback.format_exc(), False
        if not текст.strip():
            текст = "(програма нічого не надрукувала)"
        # Kivy-віджети можна чіпати лише з головного потоку.
        Clock.schedule_once(lambda dt: self._показати_результат(текст), 0)

    def _запамʼятати_вм(self, вм):
        self._вм = вм
        # Якщо «Стоп» натиснули ще до того, як ВМ створилась, — не губимо.
        if self._стоп_запитано:
            вм.зупинено = True

    def _показати_результат(self, текст):
        self.вивід.text = текст
        self._вм = None
        self._потік = None
        self._стоп_запитано = False
        self._кн_виконати.disabled = False
        self._кн_стоп.disabled = True
        Clock.schedule_once(lambda dt: setattr(self._прокрутка_виводу, "scroll_y", 1), 0)

    def _стоп(self, *_):
        self._стоп_запитано = True
        if self._вм is not None:
            self._вм.зупинено = True

    def _очистити(self, *_):
        self.вивід.text = ""

    def _очистити_код(self, *_):
        self.код.text = ""
        Clock.schedule_once(lambda dt: setattr(self.код, "focus", True), 0)

    # ---- автозбереження ----------------------------------------------------

    def _прочитати_код(self):
        try:
            if self._шлях_коду.exists():
                return self._шлях_коду.read_text(encoding="utf-8")
        except Exception:
            pass
        return ПОЧАТКОВИЙ_КОД

    def _зберегти_код(self, _інст, текст):
        try:
            self._шлях_коду.parent.mkdir(parents=True, exist_ok=True)
            self._шлях_коду.write_text(текст, encoding="utf-8")
        except Exception:
            pass


if __name__ == "__main__":
    МоваApp().run()
