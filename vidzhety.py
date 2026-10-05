"""Спільні Kivy-віджети редактора (main.py) і згенерованих запускачів
застосунків (zastosunky.py): прокручуваний текст (вікно виводу, логіка —
vyvid.py) і ряд кнопок, полотно креслення. Kivy-only, на комп'ютері без
дисплея не імпортується."""

from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Ellipse, Line, PopMatrix, PushMatrix, Rectangle, Rotate, Triangle
from kivy.metrics import dp
from kivy.properties import NumericProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.stencilview import StencilView
from kivy.uix.widget import Widget

import vyvid

МОНО = "RobotoMono-Regular"  # входить у Kivy, підтримує кирилицю


class ТекстВиводу(Widget):
    """Довгий текст у ScrollView без однієї величезної текстури: текст
    поділено на шматки (vyvid.Розкладка), і Label існує лише для тих, що
    зараз у вікні прокрутки (плюс пів екрана запасу з кожного боку).
    Зовні — як Label: властивість text (можна bind і +=); «межа» — скільки
    останніх рядків показувати."""

    text = StringProperty("")
    межа = NumericProperty(vyvid.МЕЖА_ТИПОВА)

    def __init__(self, шрифт=None, розмір="15sp", **kw):
        self._шрифт = {"font_name": шрифт} if шрифт else {}
        self._розмір = розмір
        self._прокрутка = None
        self._розкладка = vyvid.Розкладка()
        self._показані = {}        # номер шматка -> Label
        self._вільні = []          # Label-и, що вийшли з вікна, — на повторне використання
        self._стовпців = 0
        self._оновлюю = False
        self._розмір_знака = None  # (ширина, висота) одного знака шрифту
        kw.setdefault("size_hint_y", None)
        super().__init__(**kw)
        self.bind(text=self._перебудувати, межа=self._перебудувати,
                  width=self._при_ширині, pos=self._оновити_видиме)
        self._перебудувати()

    def привʼязати(self, прокрутка):
        """ScrollView, у якому лежить текст: видимі шматки рахуються за
        його scroll_y і висотою."""
        self._прокрутка = прокрутка
        прокрутка.bind(scroll_y=self._оновити_видиме, height=self._оновити_видиме)
        self._оновити_видиме()

    # ---- розкладка ----------------------------------------------------------

    def _нова_мітка(self):
        return Label(
            size_hint=(None, None), halign="left", valign="top",
            font_size=self._розмір, **self._шрифт,
        )

    def _знак(self):
        if self._розмір_знака is None:
            мітка = self._нова_мітка()
            ш, в = CoreLabel(font_size=мітка.font_size, font_name=мітка.font_name).get_extents("0")
            self._розмір_знака = (max(ш, 1), max(в, 1))
            self._вільні.append(мітка)
        return self._розмір_знака

    def _порахувати_стовпці(self):
        return max(1, int((self.width - dp(8)) / self._знак()[0]))

    def _перебудувати(self, *_):
        self._стовпців = self._порахувати_стовпці()
        for і in list(self._показані):
            self._сховати(і)
        self._розкладка = vyvid.Розкладка(self.text, int(self.межа), self._стовпців, self._знак()[1])
        self._оновити_видиме()

    def _при_ширині(self, *_):
        # інша ширина — інші переноси: шматки рахуємо наново лише коли
        # змінилась кількість знаків у ряду
        if self._порахувати_стовпці() != self._стовпців:
            self._перебудувати()
        else:
            self._оновити_видиме()

    # ---- видимі шматки ---------------------------------------------------------

    def _вікно(self):
        """(верх, низ) видимої смуги — відстані від верху тексту, із запасом."""
        всього = self._розкладка.всього + dp(8)
        п = self._прокрутка
        if п is None or всього <= п.height:
            return 0, всього
        y = min(max(п.scroll_y, 0), 1)
        верх = (1 - y) * (всього - п.height)
        запас = п.height / 2
        return верх - запас, верх + п.height + запас

    def _показати(self, і):
        """Намалювати шматок і. True — якщо справжня висота не та, що в оцінці."""
        мітка = self._вільні.pop() if self._вільні else self._нова_мітка()
        мітка.text_size = (self.width - dp(8), None)
        мітка.text = self._розкладка.тексти[і]
        мітка.texture_update()
        # text/text_size уже запланували це саме оновлення на наступний
        # кадр — удруге малювати той самий текст не треба
        відкладене = getattr(мітка, "_trigger_texture", None)
        if відкладене is not None:
            відкладене.cancel()
        self._показані[і] = мітка
        self.add_widget(мітка)
        висота = мітка.texture_size[1]
        return висота > 0 and self._розкладка.уточнити(і, висота)

    def _сховати(self, і):
        мітка = self._показані.pop(і)
        self.remove_widget(мітка)
        мітка.text = ""            # звільнити текстуру
        self._вільні.append(мітка)

    def _оновити_видиме(self, *_):
        if self._оновлюю:
            return
        self._оновлюю = True
        try:
            for _ in range(3):     # уточнена висота може зсунути вікно
                верх, низ = self._вікно()
                потрібні = self._розкладка.видимі(верх, низ)
                for і in [і for і in self._показані if і not in потрібні]:
                    self._сховати(і)
                зсунулось = False
                for і in потрібні:
                    if і not in self._показані:
                        зсунулось = self._показати(і) or зсунулось
                if not зсунулось:
                    break
            self.height = self._розкладка.всього + dp(8)
            for і, мітка in self._показані.items():
                висота = self._розкладка.висоти[і]
                мітка.size = (self.width, висота)
                # цілі пікселі: Label малює текстуру з int(), дробові
                # координати дали б щілини в піксель між шматками
                мітка.pos = (int(self.x), int(self.top - dp(4) - self._розкладка.верх(і) - висота))
        finally:
            self._оновлюю = False


def прокручуваний_текст(текст="", шрифт=None, розмір="15sp"):
    """ScrollView з текстом, що переносить рядки й росте у висоту; довгий
    текст малюється шматками (ТекстВиводу)."""
    вивід = ТекстВиводу(text=текст, шрифт=шрифт, розмір=розмір)
    прокрутка = ScrollView()
    прокрутка.add_widget(вивід)
    вивід.привʼязати(прокрутка)
    return прокрутка, вивід


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
    """Полотно креслення з drafting.для_екрана() — і екрана бібліотеки
    «екран» (biblioteky/ekran.py), той самий формат. Гортання одним пальцем,
    масштаб двома (щипок, ×1.1/÷1.1 за крок, з межами), «Вмістити все».
    Уся геометрія показу — в polotno.py (без Kivy): товщини ліній і
    шрифт сталі в пікселях, тому при масштабуванні лінії не стають
    брусками. Малює напряму на своєму canvas (без Scatter).

    Кадр бібліотеки «екран» (креслення["екран"]) пальцями не рухається:
    дотик іде програмі через при_дотику(x, y, натиснуто) — пікселі кадру,
    (0, 0) угорі ліворуч (polotno.точка_екрана)."""

    def __init__(self, при_дотику=None, **kw):
        super().__init__(**kw)
        self.при_дотику = при_дотику
        self._палець = None        # uid дотику, який бачить програма («екран»)
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
        лінії = self.креслення["лінії"]
        with self.canvas:
            for к in команди:
                тип = к["тип"]
                if тип == "фон":
                    Color(*self._колір(к["колір"]))
                    Rectangle(pos=(к["x"], к["y"]), size=(к["ш"], к["в"]))
                    continue
                Color(*self._колір(к.get("колір") or лінії))   # колір фігури («екран») або ліній креслення
                if тип == "лінія":
                    if к["штрих"]:
                        Line(points=к["точки"], width=1, dash_length=к["штрих"][0], dash_offset=к["штрих"][1])
                    else:
                        Line(points=к["точки"], width=к["ширина"], close=к["замкнена"], joint="miter")
                elif тип == "заливка":
                    Triangle(points=к["точки"])
                elif тип == "прямокутник":
                    Rectangle(pos=(к["x"], к["y"]), size=(к["ш"], к["в"]))
                elif тип == "круг":
                    Ellipse(pos=(к["cx"] - к["r"], к["cy"] - к["r"]), size=(2 * к["r"], 2 * к["r"]))
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

    def _це_екран(self):
        return bool(self.креслення and self.креслення.get("екран"))

    def _дотик_програмі(self, touch, натиснуто):
        if self.при_дотику is None:
            return
        x, y = polotno.точка_екрана(self.креслення, self.масштаб, self.зсув, touch.x, touch.y)
        self.при_дотику(x, y, натиснуто)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos) or self.креслення is None:
            return super().on_touch_down(touch)
        touch.grab(self)
        if self._це_екран():
            if self._палець is None:
                self._палець = touch.uid
                self._дотик_програмі(touch, True)
            return True
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
        if self._палець is not None or self._це_екран():
            if touch.uid == self._палець:
                self._дотик_програмі(touch, True)
            return True
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
        if touch.uid == self._палець:
            self._палець = None
            if self.креслення is not None:
                self._дотик_програмі(touch, False)
            return True
        self._дотики.pop(touch.uid, None)
        self._щипок = None
        if len(self._дотики) >= 2:
            self._почати_щипок()
        return True
