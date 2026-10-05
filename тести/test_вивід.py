"""Вікно виводу: межа рядків (типово 10000, з «Налаштувань») і розкладка
довгого тексту шматками (vyvid.py, без Kivy). Віджет vidzhety.ТекстВиводу
ганяється на підставних Kivy-віджетах — лише логіка: які шматки
намальовано, де вони стоять, скільки тексту малюється за раз."""

import sys
import time
import types
from pathlib import Path

КОРІНЬ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(КОРІНЬ))

import pytest

import github
import vyvid


def рядки(n, від=1):
    return "".join(f"рядок {і}\n" for і in range(від, від + n))


# ---- межа -----------------------------------------------------------------------

def test_типова_межа_десять_тисяч():
    assert vyvid.МЕЖА_ТИПОВА == 10000
    assert vyvid.МЕЖА_МІН <= 300 < vyvid.МЕЖА_ТИПОВА <= vyvid.МЕЖА_МАКС


def test_короткий_вивід_не_змінюється():
    for текст in ("", "один", "а\nб\n", рядки(10000)):
        assert vyvid.обрізати(текст, 10000) == текст
    assert vyvid.кількість_рядків("") == 0
    assert vyvid.кількість_рядків("а") == vyvid.кількість_рядків("а\n") == 1
    assert vyvid.кількість_рядків("а\n\n") == 2


def test_довгий_вивід_лишає_останні_рядки_і_каже_скільки():
    текст = vyvid.обрізати(рядки(10001), 10000)
    частини = текст.split("\n")
    assert "10000" in частини[0] and "10001" in частини[0]
    assert частини[1] == "рядок 2" and частини[-2] == "рядок 10001"
    assert vyvid.кількість_рядків(текст) == 10001          # 10000 + рядок-повідомлення
    # без кінцевого переносу — так само
    без = vyvid.обрізати(рядки(500).rstrip("\n"), 100)
    assert без.split("\n")[1] == "рядок 401" and без.endswith("рядок 500")


def test_межа_з_тексту():
    assert vyvid.межа_з_тексту("5000") == 5000
    assert vyvid.межа_з_тексту(" 10 000 ") == 10000
    assert vyvid.межа_з_тексту("5") == vyvid.МЕЖА_МІН
    assert vyvid.межа_з_тексту("99999999") == vyvid.МЕЖА_МАКС
    for не_число in ("", "багато", "-5", "1.5", None):
        assert vyvid.межа_з_тексту(не_число) is None


def test_межа_зберігається_поруч_із_токеном(tmp_path):
    assert vyvid.ФАЙЛ_НАЛАШТУВАНЬ == github.ФАЙЛ_НАЛАШТУВАНЬ
    assert vyvid.прочитати_межу(tmp_path) == 10000
    github.зберегти_налаштування(tmp_path, токен="ghp_abcdef123")
    vyvid.зберегти_межу(tmp_path, 2500)
    assert vyvid.прочитати_межу(tmp_path) == 2500
    assert github.прочитати_налаштування(tmp_path)["токен"] == "ghp_abcdef123"
    github.зберегти_налаштування(tmp_path, репо="me/mova")   # не губить межу
    assert vyvid.прочитати_межу(tmp_path) == 2500
    (tmp_path / vyvid.ФАЙЛ_НАЛАШТУВАНЬ).write_text("не json", encoding="utf-8")
    assert vyvid.прочитати_межу(tmp_path) == 10000


# ---- шматки й розкладка ----------------------------------------------------------

def test_шматки_зберігають_увесь_текст():
    текст = рядки(1000)
    частини = vyvid.шматки(текст, стовпців=40)
    assert "\n".join(т for т, _ in частини) + "\n" == текст
    assert all(р <= vyvid.РЯДІВ_У_ШМАТКУ for _, р in частини)
    assert len(частини) == -(-1000 // vyvid.РЯДІВ_У_ШМАТКУ)
    assert vyvid.шматки("") == []
    assert vyvid.шматки("\n\nа") == [("\n\nа", 3)]


def test_довгі_рядки_рахуються_з_переносом_і_ріжуться():
    assert vyvid.шматки("х" * 95, стовпців=10) == [("х" * 95, 10)]
    # один рядок на мільйон знаків не стає однією текстурою
    частини = vyvid.шматки("х" * 1_000_000 + "\nкінець", стовпців=40)
    assert "".join(т for т, _ in частини[:-1]) == "х" * 1_000_000
    assert частини[-1] == ("кінець", 1)
    assert max(р for _, р in частини) <= vyvid.РЯДІВ_У_ШМАТКУ


def test_розкладка_видимі_шматки_і_уточнення_висоти():
    р = vyvid.Розкладка(рядки(300), стовпців=40, висота_ряду=20)
    assert len(р) == 10 and р.всього == 300 * 20
    assert р.верх(0) == 0 and р.верх(1) == 600
    assert list(р.видимі(0, 500)) == [0]
    assert list(р.видимі(500, 1300)) == [0, 1, 2]
    assert list(р.видимі(-100, -50)) == [0]                 # перетяг угору
    assert list(р.видимі(10 ** 9, 10 ** 9 + 5)) == [9]      # перетяг униз
    assert not р.уточнити(1, 600.2)
    assert р.уточнити(1, 660)
    assert р.верх(2) == 1260 and р.всього == 6060
    assert list(vyvid.Розкладка("").видимі(0, 100)) == []


def test_розкладка_великого_виводу_швидка():
    """10000 рядків (типова межа) і мільйон рядків із тією ж межею: час
    малий і не росте разом із відрізаною частиною."""
    мала, велика = рядки(10_000), рядки(1_000_000)
    початок = time.perf_counter()
    р = vyvid.Розкладка(мала, 10000, 40, 20)
    час_малої = time.perf_counter() - початок
    початок = time.perf_counter()
    р2 = vyvid.Розкладка(велика, 10000, 40, 20)
    час_великої = time.perf_counter() - початок
    assert len(р) == 334 and len(р2) == 334
    assert час_малої < 0.5 and час_великої < 0.5


# ---- віджет на підставному Kivy ---------------------------------------------------

ШИРИНА_ЗНАКА, ВИСОТА_РЯДУ = 10, 20


class _Власт:
    def __init__(self, типове=None):
        self.типове = типове

    def __set_name__(self, клас, імʼя):
        self.імʼя = імʼя

    def __get__(self, обʼєкт, клас=None):
        if обʼєкт is None:
            return self
        return обʼєкт.__dict__.get(self.імʼя, self.типове)

    def __set__(self, обʼєкт, значення):
        if обʼєкт.__dict__.get(self.імʼя, self.типове) != значення:
            обʼєкт.__dict__[self.імʼя] = значення
            обʼєкт._сповістити(self.імʼя)


class _Віджет:
    x, y, width, height = _Власт(0), _Власт(0), _Власт(100), _Власт(100)
    _СКЛАДЕНІ = {"x": "pos", "y": "pos", "width": "size", "height": "size"}

    def __init__(self, **kw):
        self.children, self.parent, self._слухачі = [], None, {}
        for к, з in kw.items():
            setattr(self, к, з)

    def bind(self, **kw):
        for к, дія in kw.items():
            self._слухачі.setdefault(к, []).append(дія)

    def _сповістити(self, імʼя):
        for к in (імʼя, self._СКЛАДЕНІ.get(імʼя)):
            for дія in getattr(self, "_слухачі", {}).get(к, []):
                дія(self, getattr(self, к))

    pos = property(lambda s: (s.x, s.y), lambda s, з: (setattr(s, "x", з[0]), setattr(s, "y", з[1])) and None)
    size = property(lambda s: (s.width, s.height),
                    lambda s, з: (setattr(s, "width", з[0]), setattr(s, "height", з[1])) and None)
    top = property(lambda s: s.y + s.height)

    def add_widget(self, в):
        assert в.parent is None
        в.parent = self
        self.children.append(в)

    def remove_widget(self, в):
        self.children.remove(в)
        в.parent = None


class _Мітка(_Віджет):
    """Label: висота текстури — за справжнім переносом тексту."""
    text = _Власт("")
    створено = 0
    намальовано_рядів = 0
    висота_ряду = ВИСОТА_РЯДУ

    def __init__(self, **kw):
        self.text_size, self.texture_size = (None, None), (0, 0)
        self.font_name = "Шрифт"
        super().__init__(**kw)
        if not isinstance(self.font_size, (int, float)):
            self.font_size = 14
        _Мітка.створено += 1

    font_size = 14

    def texture_update(self):
        if not self.text:
            self.texture_size = (0, 0)
            return
        стовпців = max(1, int(self.text_size[0] // ШИРИНА_ЗНАКА))
        рядів = sum(max(1, -(-len(р) // стовпців)) for р in self.text.split("\n"))
        _Мітка.намальовано_рядів += рядів
        self.texture_size = (self.text_size[0], рядів * _Мітка.висота_ряду)


class _Прокрутка(_Віджет):
    scroll_y = _Власт(1.0)


@pytest.fixture
def віджети(monkeypatch):
    def модуль(назва, **вміст):
        м = types.ModuleType(назва)
        м.__dict__.update(вміст)
        monkeypatch.setitem(sys.modules, назва, м)

    for назва in ("kivy", "kivy.core", "kivy.uix"):
        модуль(назва)
    модуль("kivy.core.text", Label=lambda **kw: types.SimpleNamespace(
        get_extents=lambda текст: (ШИРИНА_ЗНАКА * len(текст), ВИСОТА_РЯДУ)))
    модуль("kivy.graphics", **{н: object for н in (
        "Color", "Ellipse", "Line", "PopMatrix", "PushMatrix", "Rectangle", "Rotate", "Triangle")})
    модуль("kivy.metrics", dp=lambda x: x)
    модуль("kivy.properties", NumericProperty=_Власт, StringProperty=_Власт)
    модуль("kivy.uix.boxlayout", BoxLayout=type("BoxLayout", (_Віджет,), {}))
    модуль("kivy.uix.label", Label=_Мітка)
    модуль("kivy.uix.scrollview", ScrollView=_Прокрутка)
    модуль("kivy.uix.stencilview", StencilView=type("StencilView", (_Віджет,), {}))
    модуль("kivy.uix.widget", Widget=_Віджет)
    monkeypatch.delitem(sys.modules, "vidzhety", raising=False)
    monkeypatch.setattr(_Мітка, "створено", 0)
    monkeypatch.setattr(_Мітка, "намальовано_рядів", 0)
    monkeypatch.setattr(_Мітка, "висота_ряду", ВИСОТА_РЯДУ)
    import vidzhety
    yield vidzhety
    sys.modules.pop("vidzhety", None)


def вікно(vidzhety, текст="", ширина=408, висота=600):
    прокрутка, вивід = vidzhety.прокручуваний_текст(текст, шрифт="Моно", розмір=14)
    прокрутка.size = (ширина, висота)
    вивід.width = ширина          # як ScrollView розтягує вміст
    return прокрутка, вивід


def показано(вивід):
    """Тексти намальованих шматків згори вниз + перевірка, що вони стоять
    впритул одне під одним, там, де каже розкладка."""
    мітки = [вивід._показані[і] for і in sorted(вивід._показані)]
    assert sorted(map(id, мітки)) == sorted(map(id, вивід.children))
    for верхня, нижня in zip(мітки, мітки[1:]):
        assert верхня.y == pytest.approx(нижня.top)
    for і, мітка in вивід._показані.items():
        assert вивід.top - 4 - мітка.top == pytest.approx(вивід._розкладка.верх(і))
    return [м.text for м in мітки]


def test_короткий_текст_показано_цілком(віджети):
    прокрутка, вивід = вікно(віджети, "Натисни «Виконати».")
    assert показано(вивід) == ["Натисни «Виконати»."]
    assert вивід.height == ВИСОТА_РЯДУ + 8
    вивід.text = ""
    assert показано(вивід) == [] and вивід.height == 8
    вивід.text += "а"
    вивід.text += "\nб"
    assert показано(вивід) == ["а\nб"]


def test_зміну_тексту_чують_слухачі(віджети):
    прокрутка, вивід = вікно(віджети)
    почуто = []
    вивід.bind(text=lambda *_: почуто.append(вивід.text))
    вивід.text = "раз"
    assert почуто == ["раз"]


def test_десять_тисяч_рядків_малюється_лише_видиме(віджети):
    прокрутка, вивід = вікно(віджети)
    _Мітка.намальовано_рядів = 0
    вивід.text = рядки(10000)
    assert вивід.height == 10000 * ВИСОТА_РЯДУ + 8
    # вікно 600 px = 30 рядів, із запасом пів екрана — щонайбільше три шматки
    assert 1 <= len(вивід.children) <= 3
    assert _Мітка.намальовано_рядів <= 3 * vyvid.РЯДІВ_У_ШМАТКУ
    assert показано(вивід)[0].startswith("рядок 1\n")

    прокрутка.scroll_y = 0
    assert показано(вивід)[-1].endswith("рядок 10000")
    assert len(вивід.children) <= 3

    # гортання всім текстом: міток стільки, скільки влазить в екран
    for крок in range(0, 1001):
        прокрутка.scroll_y = крок / 1000
        assert len(вивід.children) <= 4
    показано(вивід)
    assert _Мітка.створено <= 6
    прокрутка.scroll_y = 0.5
    assert any("рядок 5000\n" in т for т in показано(вивід))


def test_оновлення_великого_виводу_швидке(віджети):
    """Сто замін тексту на 10000 рядків (як оновити_вивід під час запитань)
    і тисяча кроків гортання — частки секунди навіть на підставних віджетах."""
    прокрутка, вивід = вікно(віджети)
    текст = рядки(10000)
    початок = time.perf_counter()
    for і in range(100):
        вивід.text = текст + f"ще {і}\n"
    for крок in range(1000):
        прокрутка.scroll_y = крок / 1000
    assert time.perf_counter() - початок < 5
    assert _Мітка.створено <= 6


def test_межа_віджета_і_її_зміна(віджети):
    прокрутка, вивід = вікно(віджети, рядки(25000))
    assert int(вивід.межа) == 10000
    assert показано(вивід)[0].startswith("… показано останні 10000 рядків із 25000\nрядок 15001\n")
    вивід.межа = 200
    assert показано(вивід)[0].startswith("… показано останні 200 рядків із 25000\nрядок 24801\n")
    assert вивід.height == 201 * ВИСОТА_РЯДУ + 8
    вивід.межа = 100000
    assert показано(вивід)[0].startswith("рядок 1\n")


def test_справжня_висота_шматка_уточнює_розкладку(віджети):
    _Мітка.висота_ряду = 23       # шрифт на екрані вищий, ніж оцінка (20)
    прокрутка, вивід = вікно(віджети, рядки(3000))
    показано(вивід)
    намальовані = len(вивід._показані)
    assert вивід.height == pytest.approx(
        (3000 - намальовані * 30) * 20 + намальовані * 30 * 23 + 8)
    прокрутка.scroll_y = 0
    assert показано(вивід)[-1].endswith("рядок 3000")


def test_поворот_екрана_перекладає_переноси(віджети):
    прокрутка, вивід = вікно(віджети, ("х" * 80 + "\n") * 100)
    assert вивід._стовпців == 40 and вивід.height == 200 * ВИСОТА_РЯДУ + 8
    вивід.width = 808
    assert вивід._стовпців == 80 and вивід.height == 100 * ВИСОТА_РЯДУ + 8
    показано(вивід)


# ---- прив'язка в застосунку --------------------------------------------------------

def test_редактор_бере_межу_з_налаштувань_і_дає_її_змінити():
    текст = (КОРІНЬ / "main.py").read_text(encoding="utf-8")
    assert "self.вивід.межа = vyvid.прочитати_межу(self.user_data_dir)" in текст
    assert "vyvid.зберегти_межу(self.user_data_dir, межа)" in текст
    assert "Рядків у вікні виводу" in текст


def test_застосунки_з_програм_отримують_вікно_виводу():
    import zastosunky
    assert {"vidzhety.py", "polotno.py", "vyvid.py"} <= set(zastosunky.ФАЙЛИ_ЯДРА)
    workflow = (КОРІНЬ / ".github" / "workflows" / "zastosunky.yml").read_text(encoding="utf-8")
    assert "vidzhety.py polotno.py vyvid.py" in workflow
