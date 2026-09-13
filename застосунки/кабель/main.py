#!/usr/bin/env python3
"""Запускач застосунку «кабель»: виконує програма.мова (мова «Мова») без
редактора. Згенеровано zastosunky.py; ядро (yadro/, zapusk.py, vidzhety.py)
докладає workflow під час збірки APK."""

import sys
import threading
import traceback
from pathlib import Path

сюди = Path(__file__).resolve().parent
if str(сюди) not in sys.path:
    sys.path.insert(0, str(сюди))

НАЗВА = 'кабель'
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
            прокрутка, _ = прокручуваний_текст("ПОМИЛКА в build():\n\n" + traceback.format_exc())
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
            текст = "Внутрішня помилка:\n" + traceback.format_exc()
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
