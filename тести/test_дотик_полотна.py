"""Дотик до полотна бібліотеки «екран» по всій площі — включно з нижнім
краєм — і збіг координат дотику з координатами малювання.

Kivy на комп'ютері немає, тож vidzhety.py імпортується з мінімальною
підробкою, яка повторює саме ті правила Kivy, через які нижня смуга
полотна була «мертва»:
  * дотик іде дітям від найновішого до найстарішого (children[0] — останній
    доданий), перший, хто повернув True, забирає його;
  * вимкнений (disabled) віджет ковтає дотик у своїх межах, а disabled
    батька переходить на дітей;
  * вертикальний BoxLayout ставить дітей зі сталою висотою знизу вгору від
    свого y — навіть коли сам має висоту 0 (тоді вони стирчать угору,
    поверх сусіда).
"""

import sys
import types
from pathlib import Path

import pytest

КОРІНЬ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(КОРІНЬ))

import polotno
from biblioteky import ekran as е
from zapusk import виконати_код

ПІДКЛЮЧИ = 'підключи("екран")\n'


class _Дотик:
    def __init__(self, x, y, uid=1):
        self.x, self.y, self.uid = x, y, uid
        self.dx = self.dy = 0
        self.grab_current = None
        self.захопили = []

    pos = property(lambda s: (s.x, s.y))

    def grab(self, віджет):
        self.захопили.append(віджет)

    def ungrab(self, віджет):
        self.захопили.remove(віджет)


class _Полотнище:
    """canvas: with self.canvas: … і clear()."""

    def clear(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _Віджет:
    def __init__(self, **kw):
        self.x = self.y = 0
        self.width = self.height = 100
        self.size_hint_y = 1
        self.children, self.parent = [], None
        self._вимкнено = False
        self.canvas = _Полотнище()
        for к, з in kw.items():
            setattr(self, к, з)

    def bind(self, **kw):
        pass

    @property
    def disabled(self):
        return self._вимкнено or (self.parent is not None and self.parent.disabled)

    @disabled.setter
    def disabled(self, значення):
        self._вимкнено = значення

    pos = property(lambda s: (s.x, s.y))
    size = property(lambda s: (s.width, s.height))
    top = property(lambda s: s.y + s.height)
    right = property(lambda s: s.x + s.width)

    def add_widget(self, в):
        в.parent = self
        self.children.insert(0, в)

    def collide_point(self, x, y):
        return self.x <= x <= self.right and self.y <= y <= self.top

    def dispatch(self, подія, touch):
        return getattr(self, подія)(touch)

    def on_touch_down(self, touch):
        if self.disabled and self.collide_point(*touch.pos):
            return True
        for дитина in self.children[:]:
            if дитина.dispatch("on_touch_down", touch):
                return True
        return False

    def on_touch_move(self, touch):
        if self.disabled:
            return False
        return any(д.dispatch("on_touch_move", touch) for д in self.children[:])

    def on_touch_up(self, touch):
        if self.disabled:
            return False
        return any(д.dispatch("on_touch_up", touch) for д in self.children[:])


class _BoxLayout(_Віджет):
    """Вертикальний розклад Kivy: стала висота (size_hint_y=None) береться
    як є, решта ділить залишок; діти йдуть знизу вгору від self.y."""

    spacing = 0

    def розкласти(self):
        сталі = sum(д.height for д in self.children if д.size_hint_y is None)
        гнучких = sum(1 for д in self.children if д.size_hint_y is not None)
        залишок = max(0, self.height - сталі - self.spacing * (len(self.children) - 1))
        y = self.y
        for д in self.children:             # children[0] — останній доданий, він унизу
            if д.size_hint_y is not None:
                д.height = залишок / гнучких
            д.x, д.y, д.width = self.x, y, self.width
            y += д.height + self.spacing
            if isinstance(д, _BoxLayout):
                д.розкласти()


class _Поле(_Віджет):
    """TextInput/Button: увімкнений бере дотик у своїх межах собі."""

    def on_touch_down(self, touch):
        if self.disabled and self.collide_point(*touch.pos):
            return True
        if self.collide_point(*touch.pos):
            self.торкнуто = True
            return True
        return False


@pytest.fixture
def vidzhety(monkeypatch):
    def модуль(назва, **вміст):
        м = types.ModuleType(назва)
        м.__dict__.update(вміст)
        monkeypatch.setitem(sys.modules, назва, м)

    for назва in ("kivy", "kivy.core", "kivy.uix"):
        модуль(назва)
    модуль("kivy.core.text", Label=lambda **kw: types.SimpleNamespace(get_extents=lambda т: (8, 16)))
    модуль("kivy.graphics", **{н: (lambda *a, **kw: None) for н in (
        "Color", "Ellipse", "Line", "PopMatrix", "PushMatrix", "Rectangle", "Rotate", "Triangle")})
    модуль("kivy.metrics", dp=lambda x: x)
    модуль("kivy.properties", NumericProperty=lambda *a: 0, StringProperty=lambda *a: "")
    модуль("kivy.uix.boxlayout", BoxLayout=_BoxLayout)
    модуль("kivy.uix.label", Label=_Віджет)
    модуль("kivy.uix.scrollview", ScrollView=_Віджет)
    модуль("kivy.uix.stencilview", StencilView=type("StencilView", (_Віджет,), {}))
    модуль("kivy.uix.widget", Widget=_Віджет)
    monkeypatch.delitem(sys.modules, "vidzhety", raising=False)
    import vidzhety
    yield vidzhety
    sys.modules.pop("vidzhety", None)


ШИРИНА, ВИСОТА = 400, 800      # вікно застосунку
ВИСОТА_ПОЛЯ, ВИСОТА_НАПИСУ = 88, 44   # dp(44) і dp(22) на телефоні з густиною 2


def кадр_екрана(код="онови()", розмір=(ШИРИНА, ВИСОТА)):
    кадри = []
    вивід, успіх = виконати_код(ПІДКЛЮЧИ + код, при_кресленні=кадри.append,
                                розмір_екрана=lambda: розмір, показувати_креслення=False)
    assert успіх, вивід
    return кадри[-1]


def вікно(vidzhety, клас_ряду, вимкнений=True, показаний=False):
    """Низ вікна редактора/застосунку: полотно, під ним рядок вводу (напис
    + поле; схований — висота 0) і порожній ряд кнопок програми."""
    дотики = []
    корінь = _BoxLayout(width=ШИРИНА, height=ВИСОТА)
    полотно = vidzhety.ПолотноКреслення(при_дотику=lambda x, y, н: дотики.append((x, y, н)))
    ряд = клас_ряду(size_hint_y=None, height=0)
    напис = _Віджет(size_hint_y=None, height=ВИСОТА_НАПИСУ)
    поле = _Поле(size_hint_y=None, height=ВИСОТА_ПОЛЯ)
    ряд.add_widget(напис)
    ряд.add_widget(поле)
    ряд.disabled = вимкнений
    if показаний:
        ряд.height = ВИСОТА_НАПИСУ + ВИСОТА_ПОЛЯ
        ряд.disabled = False
    корінь.add_widget(полотно)
    корінь.add_widget(ряд)
    корінь.add_widget(_Віджет(size_hint_y=None, height=0))    # ряд кнопок програми
    корінь.розкласти()
    полотно.показати(кадр_екрана(розмір=(int(полотно.width), int(полотно.height))))
    return корінь, полотно, поле, дотики


# ---- причина: схований рядок вводу стирчить поверх низу полотна ---------------------

def test_діти_схованого_ряду_лежать_поверх_низу_полотна(vidzhety):
    """Сама розкладка, з якої виріс баг: ряд має висоту 0, а його поле й
    напис — свою, і займають нижні ~130 px полотна."""
    корінь, полотно, поле, _ = вікно(vidzhety, vidzhety.РядЩоХовається)
    assert полотно.y == 0 and полотно.height == ВИСОТА
    assert поле.y == 0 and поле.top == ВИСОТА_ПОЛЯ
    assert полотно.collide_point(200, 50) and поле.collide_point(200, 50)


@pytest.mark.parametrize("вимкнений", [True, False])
def test_звичайний_ряд_ковтав_дотик_унизу_полотна(vidzhety, вимкнений):
    """Як було: BoxLayout висотою 0 — вимкнений (редактор) ковтає дотик,
    увімкнений (застосунок) віддає його невидимому полю вводу."""
    корінь, полотно, поле, дотики = вікно(vidzhety, _BoxLayout, вимкнений=вимкнений)
    assert корінь.on_touch_down(_Дотик(200, 50))
    assert дотики == []
    assert корінь.on_touch_down(_Дотик(200, 400, uid=2))     # вище — працювало
    assert len(дотики) == 1


# ---- виправлення: дотик по всій площі полотна -----------------------------------------

@pytest.mark.parametrize("вимкнений", [True, False])
@pytest.mark.parametrize("py", [0, 1, 20, 50, 87, 88, 100, 131, 132, 133, 400, 799, 800])
def test_полотно_ловить_дотик_на_будь_якій_висоті(vidzhety, вимкнений, py):
    корінь, полотно, поле, дотики = вікно(vidzhety, vidzhety.РядЩоХовається, вимкнений=вимкнений)
    дотик = _Дотик(200, py)
    assert корінь.on_touch_down(дотик)
    assert дотик.захопили == [полотно]
    assert not getattr(поле, "торкнуто", False)
    (x, y, натиснуто), = дотики
    assert натиснуто is True
    очікуване = polotno.точка_екрана(полотно.креслення, полотно.масштаб, полотно.зсув, 200, py)
    assert (x, y) == очікуване
    assert 0 <= y <= полотно.креслення["висота"]


def test_дотик_біля_нижнього_краю_дає_y_біля_висоти_кадру(vidzhety):
    корінь, полотно, _, дотики = вікно(vidzhety, vidzhety.РядЩоХовається)
    в = полотно.креслення["висота"]
    корінь.on_touch_down(_Дотик(200, 0))                # самий нижній піксель вікна
    assert дотики[-1] == (pytest.approx(200, abs=1), в, True)
    полотно.on_touch_up(_ж(_Дотик(200, 0), полотно))
    корінь.on_touch_down(_Дотик(200, 30, uid=2))        # 30 px від низу вікна
    assert в - 31 < дотики[-1][1] < в - 10             # кадр вміщено з полем, тож трохи менше 30


def _ж(дотик, полотно):
    дотик.grab_current = полотно
    дотик.захопили = [полотно]
    return дотик


def test_палець_що_сповз_униз_і_відпустив_унизу(vidzhety):
    """Рух і відпускання в нижній смузі теж доходять до програми."""
    корінь, полотно, _, дотики = вікно(vidzhety, vidzhety.РядЩоХовається)
    дотик = _Дотик(100, 400)
    корінь.on_touch_down(дотик)
    дотик.grab_current = полотно
    дотик.x, дотик.y = 120, 10
    assert полотно.on_touch_move(дотик)
    assert полотно.on_touch_up(дотик)
    assert [н for _, _, н in дотики] == [True, True, False]
    assert дотики[1][:2] == дотики[2][:2] == polotno.точка_екрана(
        полотно.креслення, полотно.масштаб, полотно.зсув, 120, 10)


def test_схований_ряд_не_бачить_і_руху_та_відпускання(vidzhety):
    ряд = vidzhety.РядЩоХовається(size_hint_y=None, height=0)
    поле = _Поле(size_hint_y=None, height=ВИСОТА_ПОЛЯ)
    поле.on_touch_move = поле.on_touch_up = lambda touch: True
    ряд.add_widget(поле)
    assert not ряд.on_touch_move(_Дотик(10, 10)) and not ряд.on_touch_up(_Дотик(10, 10))
    ряд.height = ВИСОТА_ПОЛЯ
    assert ряд.on_touch_move(_Дотик(10, 10)) and ряд.on_touch_up(_Дотик(10, 10))


def test_показаний_рядок_вводу_працює_а_полотно_над_ним_теж(vidzhety):
    """«запитай» при показаному полотні: поле вводу ловить свої дотики,
    полотно (тепер нижче на висоту ряду) — свої, аж до свого нижнього краю."""
    корінь, полотно, поле, дотики = вікно(vidzhety, vidzhety.РядЩоХовається, показаний=True)
    assert полотно.y == ВИСОТА_НАПИСУ + ВИСОТА_ПОЛЯ
    assert корінь.on_touch_down(_Дотик(200, 40))
    assert поле.торкнуто and дотики == []
    assert корінь.on_touch_down(_Дотик(200, полотно.y + 1, uid=2))
    assert len(дотики) == 1 and дотики[0][1] == pytest.approx(полотно.креслення["висота"], abs=2)


@pytest.mark.parametrize("файл", ["main.py", "zastosunky.py", "застосунки/кабель/main.py"])
def test_рядок_вводу_під_полотном_це_ряд_що_ховається(файл):
    текст = (КОРІНЬ / файл).read_text(encoding="utf-8")
    assert "self._ряд_вводу = РядЩоХовається(" in текст
    assert "self._ряд_вводу = BoxLayout(" not in текст


# ---- координати малювання == координати дотику ------------------------------------------

КНОПКА = (40, 500, 120, 60)     # x, y, ширина, висота — у пікселях полотна, y вниз

РОЗКЛАДКИ = [
    # (ширина, висота віджета, x0, y0) — полотно того ж розміру, що кадр; зсунуте; іншого розміру
    (400, 800, 0, 0),
    (400, 800, 6, 150),
    (720, 1100, 12, 96),
    (300, 300, 0, 40),
    (1080, 500, 0, 0),
]


def _прямокутник_на_екрані(кадр, масштаб, зсув):
    к, = [к for к in polotno.команди(кадр, масштаб, зсув) if к["тип"] == "прямокутник"]
    return к["x"], к["y"], к["ш"], к["в"]


@pytest.mark.parametrize("ш, в, x0, y0", РОЗКЛАДКИ)
def test_кнопка_ловить_палець_саме_там_де_намальована(ш, в, x0, y0):
    """Кути й середина намальованого прямокутника (пікселі вікна) через
    точка_екрана() повертаються в ті самі координати, якими його малювали."""
    bx, by, bш, bв = КНОПКА
    кадр = кадр_екрана(f"заливка({bx}, {by}, {bш}, {bв})\nонови()")
    масштаб, зсув = polotno.вмістити(кадр, ш, в, x0, y0)
    px, py, pш, pв = _прямокутник_на_екрані(кадр, масштаб, зсув)
    т = lambda x, y: polotno.точка_екрана(кадр, масштаб, зсув, x, y)
    # на екрані Kivy y росте вгору: верх кнопки — py + pв, низ — py
    assert т(px, py + pв) == pytest.approx((bx, by))                        # лівий верхній кут
    assert т(px + pш, py) == pytest.approx((bx + bш, by + bв))              # правий нижній
    assert т(px + pш / 2, py + pв / 2) == pytest.approx((bx + bш / 2, by + bв / 2))
    # піксель назовні від краю — вже не в кнопці, усередину — в кнопці
    def у_кнопці(точка):
        return bx <= точка[0] <= bx + bш and by <= точка[1] <= by + bв
    assert у_кнопці(т(px + 1, py + 1)) and у_кнопці(т(px + pш - 1, py + pв - 1))
    assert not у_кнопці(т(px - 2, py + 5)) and not у_кнопці(т(px + 5, py - 2))
    assert not у_кнопці(т(px + pш + 2, py + 5)) and not у_кнопці(т(px + 5, py + pв + 2))


@pytest.mark.parametrize("ш, в, x0, y0", РОЗКЛАДКИ)
@pytest.mark.parametrize("фігура, центр", [
    ("круг(350, 790, 8)", (350, 790)),          # біля самого нижнього краю
    ("круг(5, 5, 4)", (5, 5)),                  # біля верхнього лівого кута
    ("коло(200, 400, 30)", (200, 400)),
])
def test_круг_під_пальцем(ш, в, x0, y0, фігура, центр):
    """Програма «круг у місці пальця»: дотик у центр намальованого круга
    дає саме ті координати, в яких його намальовано — і біля нижнього краю."""
    кадр = кадр_екрана(фігура + "\nонови()")
    масштаб, зсув = polotno.вмістити(кадр, ш, в, x0, y0)
    к, = [к for к in polotno.команди(кадр, масштаб, зсув) if к["тип"] in ("круг", "дуга")]
    assert polotno.точка_екрана(кадр, масштаб, зсув, к["cx"], к["cy"]) == pytest.approx(центр)


def test_лінія_і_напис_у_тих_самих_координатах():
    кадр = кадр_екрана('лінія(10, 780, 390, 795)\nнапис(30, 700, "Тисни")\nонови()')
    масштаб, зсув = polotno.вмістити(кадр, 400, 800, 6, 150)
    т = lambda x, y: polotno.точка_екрана(кадр, масштаб, зсув, x, y)
    лінія, = [к for к in polotno.команди(кадр, масштаб, зсув) if к["тип"] == "лінія"]
    assert т(*лінія["точки"][:2]) == pytest.approx((10, 780))
    assert т(*лінія["точки"][2:]) == pytest.approx((390, 795))
    текст, = [к for к in polotno.команди(кадр, масштаб, зсув) if к["тип"] == "текст"]
    assert текст["опора"] == "верх" and т(текст["x"], текст["y"]) == pytest.approx((30, 700))


def test_кути_кадру_і_нижній_край():
    кадр = кадр_екрана()
    масштаб, зсув = polotno.вмістити(кадр, 400, 800, 6, 150)
    фон = polotno.команди(кадр, масштаб, зсув)[0]
    т = lambda x, y: polotno.точка_екрана(кадр, масштаб, зсув, x, y)
    assert т(фон["x"], фон["y"] + фон["в"]) == pytest.approx((0, 0))
    assert т(фон["x"] + фон["ш"], фон["y"]) == pytest.approx((ШИРИНА, ВИСОТА))
    assert т(фон["x"] + фон["ш"] / 2, фон["y"]) == pytest.approx((ШИРИНА / 2, ВИСОТА))
    # нижче кадру (поле навколо нього, сам край віджета) — притискається до низу
    assert т(фон["x"] + 100, 150) == (pytest.approx(100 / масштаб), ВИСОТА)


def test_програма_бачить_дотик_до_намальованої_кнопки_через_полотно(vidzhety):
    """Наскрізно: програма малює кнопку внизу полотна, палець тисне в її
    середину на екрані — палець_х()/палець_у() потрапляють у кнопку."""
    корінь, полотно, _, _ = вікно(vidzhety, vidzhety.РядЩоХовається)
    ш, в = int(полотно.width), int(полотно.height)
    bx, by, bш, bв = 40, в - 70, 120, 60                   # кнопка за 10 px від низу
    полотно.показати(кадр_екрана(f"заливка({bx}, {by}, {bш}, {bв})\nонови()", розмір=(ш, в)))
    px, py, pш, pв = _прямокутник_на_екрані(полотно.креслення, полотно.масштаб, полотно.зсув)
    assert py < ВИСОТА_ПОЛЯ                                # кнопка — у колишній «мертвій» смузі
    полотно.при_дотику = е.задати_дотик
    assert корінь.on_touch_down(_Дотик(px + pш / 2, py + pв / 2))
    assert е._натиснуто is True
    x, y = е._палець
    assert (x, y) == pytest.approx((bx + bш / 2, by + bв / 2))
    assert bx <= x <= bx + bш and by <= y <= by + bв
    е.задати_дотик(0, 0, False)
