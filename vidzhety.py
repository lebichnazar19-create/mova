"""Спільні Kivy-віджети редактора (main.py) і згенерованих запускачів
застосунків (zastosunky.py): прокручуваний текст і ряд кнопок, полотно
креслення. Kivy-only, на комп'ютері без дисплея не імпортується."""

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Line, PopMatrix, PushMatrix, Rectangle, Rotate, Triangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scatter import Scatter
from kivy.uix.scrollview import ScrollView
from kivy.uix.stencilview import StencilView
from kivy.uix.widget import Widget

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


ПІКСЕЛІВ_НА_ММ = 3.0  # базовий масштаб полотна до зуму пальцями


class ПолотноКреслення(StencilView):
    """Полотно, на якому малюється креслення з drafting.для_екрана().
    Усередині — Scatter (гортання одним пальцем, масштаб двома) з
    віджетом-аркушем, координати якого — мм × ПІКСЕЛІВ_НА_ММ, Y вгору."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.креслення = None
        self.scatter = Scatter(do_rotation=False, do_translation=True, do_scale=True,
                               scale_min=0.05, scale_max=40, size_hint=(None, None))
        self.аркуш = Widget(size_hint=(None, None))
        self.scatter.add_widget(self.аркуш)
        self.add_widget(self.scatter)
        self.bind(size=lambda *_: self.вмістити())

    def показати(self, креслення):
        self.креслення = креслення
        self._перемалювати()
        self.вмістити()

    def вмістити(self):
        """«Вмістити все»: масштаб і положення, щоб аркуш ліг у полотно."""
        if self.креслення is None or self.width <= 0 or self.height <= 0:
            return
        ш = self.креслення["ширина"] * ПІКСЕЛІВ_НА_ММ
        в = self.креслення["висота"] * ПІКСЕЛІВ_НА_ММ
        масштаб = min((self.width - dp(12)) / ш, (self.height - dp(12)) / в)
        self.scatter.scale = max(0.05, масштаб)
        self.scatter.pos = (
            self.x + (self.width - ш * self.scatter.scale) / 2,
            self.y + (self.height - в * self.scatter.scale) / 2,
        )

    def _колір(self, hex_):
        hex_ = hex_.lstrip("#")
        return tuple(int(hex_[i:i + 2], 16) / 255 for i in (0, 2, 4)) + (1,)

    def _перемалювати(self):
        к = self.креслення
        м = ПІКСЕЛІВ_НА_ММ
        полотно = self.аркуш.canvas
        полотно.clear()
        if к is None:
            return
        ш, в = к["ширина"] * м, к["висота"] * м
        self.аркуш.size = (ш, в)
        self.scatter.size = (ш, в)
        with полотно:
            Color(*self._колір(к["фон"]))
            Rectangle(pos=(0, 0), size=(ш, в))
            Color(*self._колір(к["лінії"]))
            for ф in к["фігури"]:
                тип = ф["тип"]
                if тип == "лінія":
                    товщина = max(1.0, ф["товщина"] * м)
                    if ф.get("штрих"):
                        Line(points=[к_ * м for к_ in ф["точки"]], width=1,
                             dash_length=max(2.0, ф["штрих"][0] * м), dash_offset=max(2.0, ф["штрих"][1] * м))
                    else:
                        Line(points=[к_ * м for к_ in ф["точки"]], width=товщина)
                elif тип == "ламана":
                    Line(points=[к_ * м for к_ in ф["точки"]], width=max(1.0, ф["товщина"] * м),
                         close=ф.get("замкнена", False), joint="miter")
                elif тип == "прямокутник":
                    Line(rectangle=(ф["x"] * м, ф["y"] * м, ф["ш"] * м, ф["в"] * м),
                         width=max(1.0, ф["товщина"] * м))
                elif тип == "трикутник":
                    Triangle(points=[к_ * м for к_ in ф["точки"]])
                elif тип == "дуга":
                    # Kivy: кут 0 — угорі, за годинниковою; у фігурі — від осі x проти годинникової
                    a, b = 90 - max(ф["від"], ф["до"]), 90 - min(ф["від"], ф["до"])
                    Line(circle=(ф["cx"] * м, ф["cy"] * м, ф["r"] * м, a, b),
                         width=max(1.0, ф["товщина"] * м))
                elif тип == "текст":
                    мітка = CoreLabel(text=ф["текст"], font_size=max(6, ф["розмір"] * м), font_name=МОНО)
                    мітка.refresh()
                    т = мітка.texture
                    x, y = ф["x"] * м, ф["y"] * м
                    зсув_x = -т.width / 2 if ф.get("вирівнювання") == "середина" else 0
                    PushMatrix()
                    Rotate(angle=ф.get("кут", 0), origin=(x, y))
                    Rectangle(texture=т, pos=(x + зсув_x, y - т.height / 2), size=т.size)
                    PopMatrix()


