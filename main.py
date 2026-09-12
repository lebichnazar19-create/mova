#!/usr/bin/env python3
"""Точка входу Kivy-застосунку «Мова» для Android (python-for-android/Buildozer
шукає саме файл main.py в source.dir — див. buildozer.spec).

Навмисно мінімальний: лише доводить, що інтерпретатор «Мова» (ядро/*)
пакується й виконується всередині APK. Реальна взаємодія з пристроєм
(вібрація тощо, ядро/пристрій.py) — окреме завдання, тут не чіпається.

Тому демо-програма нижче:
- НЕ викликає жодної функції з ядро/пристрій.py (вібруй/сповісти/...) —
  щоб не смикати неіснуючі на звичайному Android termux-* утиліти;
- НЕ викликає питай() — на Android немає консольного stdin, а перенесення
  REPL/питай() на чергу повідомлень з UI-потоком — окреме завдання;
- запускається через виконати_байткод(..., без_пристрою=True) — той самий
  симуляційний режим, що й `мова.py --без-пристрою` — тому навіть якщо
  колись до демо додадуть виклик пристрою, він не впаде на реальний
  subprocess, а лише надрукує, що б він зробив.
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

сюди = Path(__file__).resolve().parent
if str(сюди) not in sys.path:
    sys.path.insert(0, str(сюди))

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView

from ядро.вм import виконати_байткод
from ядро.компілятор import компілювати
from ядро.парсер import парсити_текст
from ядро.помилки import ПомилкаМови

ДЕМО = (
    'друкуй("Привіт з Android!")\n'
    "хай а = [1, 2, 3]\n"
    "додай(а, 4)\n"
    'друкуй("Список:", а)\n'
    "дія у_квадраті(х)\n"
    "    поверни х * х\n"
    'друкуй("5 у квадраті =", у_квадраті(5))\n'
)


def запустити_демо():
    """Скомпілювати й виконати ДЕМО, повернути весь друкуй()-вивід текстом
    (для показу в Label — на Android немає консолі, куди зазвичай іде print)."""
    буфер = io.StringIO()
    try:
        байткод = компілювати(парсити_текст(ДЕМО))
        with redirect_stdout(буфер):
            виконати_байткод(байткод, без_пристрою=True)
    except ПомилкаМови as e:
        буфер.write(f"{e}\n")
    return буфер.getvalue()


class МоваApp(App):
    title = "Мова"

    def build(self):
        корінь = BoxLayout(orientation="vertical", padding=16, spacing=8)

        вивід = Label(
            text=запустити_демо(),
            size_hint_y=None,
            halign="left",
            valign="top",
        )
        # авто-перенос по ширині й авто-висота під текст — стандартний
        # спосіб зробити Label, що прокручується, в Kivy
        вивід.bind(width=lambda інст, ш: setattr(інст, "text_size", (ш, None)))
        вивід.bind(texture_size=lambda інст, розмір: setattr(інст, "height", розмір[1]))

        прокрутка = ScrollView()
        прокрутка.add_widget(вивід)
        корінь.add_widget(прокрутка)
        return корінь


if __name__ == "__main__":
    МоваApp().run()
