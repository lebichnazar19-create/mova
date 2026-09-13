"""Спільні Kivy-віджети редактора (main.py) і згенерованих запускачів
застосунків (zastosunky.py): прокручуваний текст і ряд кнопок, полотно
креслення. Kivy-only, на комп'ютері без дисплея не імпортується."""

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, PopMatrix, PushMatrix, Rectangle, Rotate, Triangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.stencilview import StencilView

МОНО = "RobotoMono-Regular"  # входить у Kivy, підтримує кирилицю


def прокручуваний_текст(текст="", шрифт=None, розмір="15sp"):
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


def прокручуваний_ряд(кнопки, висота):
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


import math

import polotno


class ПолотноКреслення(StencilView):
    """Полотно креслення з drafting.для_екрана(). Гортання одним пальцем,
    масштаб двома (щипок, ×1.1/÷1.1 за крок, з межами), «Вмістити все».
    Уся геометрія показу — в polotno.py (без Kivy): товщини ліній і
    шрифт сталі в пікселях, тому при масштабуванні лінії не стають
    брусками. Малює напряму на своєму canvas (без Scatter)."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.креслення = None
        self.масштаб = 1.0
        self.зсув = (0.0, 0.0)
        self._дотики = {}          # uid -> (x, y)
        self._щипок = None         # (масштаб_старт, відстань_старт, зсув_старт, центр_старт)
        self._текстури = {}        # текст -> texture (шрифт сталий, тож кешується)
        self._вміщено = False
        self.bind(size=self._при_зміні_розміру, pos=self._при_зміні_розміру)

    # ---- показ ------------------------------------------------------------

    def показати(self, креслення):
        self.креслення = креслення
        self._вміщено = False
        self.вмістити()

    def вмістити(self, *_):
        """«Вмістити все» — і автоматично при відкритті креслення."""
        if self.креслення is None:
            return
        if self.width <= 1 or self.height <= 1:
            return  # ще не розкладено — спрацює з _при_зміні_розміру
        self.масштаб, self.зсув = polotno.вмістити(self.креслення, self.width, self.height, self.x, self.y)
        self._вміщено = True
        self._перемалювати()

    def _при_зміні_розміру(self, *_):
        # перший розклад або поворот екрана — вмістити наново
        self.вмістити()

    def _колір(self, hex_):
        hex_ = hex_.lstrip("#")
        return tuple(int(hex_[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)

    def _текстура(self, текст):
        т = self._текстури.get(текст)
        if т is None:
            мітка = CoreLabel(text=текст, font_size=polotno.ШРИФТ_PX, font_name=МОНО)
            мітка.refresh()
            т = self._текстури[текст] = мітка.texture
        return т

    def _перемалювати(self):
        self.canvas.clear()
        if self.креслення is None:
            return
        команди = polotno.команди(self.креслення, self.масштаб, self.зсув)
        with self.canvas:
            for к in команди:
                тип = к["тип"]
                if тип == "фон":
                    Color(*self._колір(к["колір"]))
                    Rectangle(pos=(к["x"], к["y"]), size=(к["ш"], к["в"]))
                    Color(*self._колір(self.креслення["лінії"]))
                elif тип == "лінія":
                    if к["штрих"]:
                        Line(points=к["точки"], width=1, dash_length=к["штрих"][0], dash_offset=к["штрих"][1])
                    else:
                        Line(points=к["точки"], width=к["ширина"], close=к["замкнена"], joint="miter")
                elif тип == "заливка":
                    Triangle(points=к["точки"])
                elif тип == "дуга":
                    a, b = 90 - max(к["від"], к["до"]), 90 - min(к["від"], к["до"])
                    Line(circle=(к["cx"], к["cy"], к["r"], a, b), width=к["ширина"])
                elif тип == "текст":
                    т = self._текстура(к["текст"])
                    x, y = к["x"], к["y"]
                    зсув_x = -т.width / 2 if к["вирівнювання"] == "середина" else 0
                    PushMatrix()
                    Rotate(angle=к["кут"], origin=(x, y))
                    Rectangle(texture=т, pos=(x + зсув_x, y - т.height / 2), size=т.size)
                    PopMatrix()

    # ---- дотики: один палець — гортання, два — масштаб ----------------------

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or self.креслення is None:
            return super().on_touch_down(touch)
        touch.grab(self)
        self._дотики[touch.uid] = touch.pos
        if len(self._дотики) == 2:
            self._почати_щипок()
        return True

    def _почати_щипок(self):
        (x1, y1), (x2, y2) = list(self._дотики.values())[:2]
        self._щипок = (self.масштаб, math.hypot(x2 - x1, y2 - y1), self.зсув, ((x1 + x2) / 2, (y1 + y2) / 2))

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_move(touch)
        if touch.uid not in self._дотики:
            return True
        self._дотики[touch.uid] = touch.pos
        if len(self._дотики) >= 2 and self._щипок is not None:
            масштаб_старт, відстань_старт, зсув_старт, центр_старт = self._щипок
            (x1, y1), (x2, y2) = list(self._дотики.values())[:2]
            відстань = math.hypot(x2 - x1, y2 - y1)
            центр = ((x1 + x2) / 2, (y1 + y2) / 2)
            новий = polotno.масштаб_щипка(масштаб_старт, відстань_старт, відстань)
            зсув = polotno.зум_навколо(масштаб_старт, новий, зсув_старт, центр_старт)
            self.масштаб = новий
            self.зсув = (зсув[0] + центр[0] - центр_старт[0], зсув[1] + центр[1] - центр_старт[1])
        else:
            self.зсув = (self.зсув[0] + touch.dx, self.зсув[1] + touch.dy)
        self._перемалювати()
        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return super().on_touch_up(touch)
        touch.ungrab(self)
        self._дотики.pop(touch.uid, None)
        self._щипок = None
        if len(self._дотики) >= 2:
            self._почати_щипок()
        return True
