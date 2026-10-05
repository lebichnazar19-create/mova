"""Проєкти застосунку: proekty.py (файли, список, пошук, відкритий
проєкт) і вікно vikno_proektiv.py. Kivy на комп'ютері немає — вікно
ганяється на підставних віджетах (лише логіка екранів), а main.py
звіряється текстом."""

import json
import sys
import types
from pathlib import Path

import pytest

КОРІНЬ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(КОРІНЬ))

import proekty
from proekty import ПомилкаПроєкту, Проєкти


def файл(тека, назва):
    return Path(тека) / "програми" / f"{назва}.вуж"


# ---- назви, список, пошук -------------------------------------------------------

def test_безпечна_назва():
    assert proekty.безпечна_назва("  Моя гра ") == "Моя гра"
    assert proekty.безпечна_назва("../../etc/passwd") == "etcpasswd"
    assert proekty.безпечна_назва("гра.вуж") == "гра"
    assert proekty.безпечна_назва("а" * 100) == "а" * 60
    for погана in ("", "   ", "...", "///", None):
        assert proekty.безпечна_назва(погана) is None


def test_файли_лежать_у_теці_програми(tmp_path):
    assert proekty.зберегти(tmp_path, "Привіт", 'друкуй("а")\n') == "Привіт"
    assert файл(tmp_path, "Привіт").read_text(encoding="utf-8") == 'друкуй("а")\n'
    assert proekty.прочитати(tmp_path, "Привіт") == 'друкуй("а")\n'
    assert proekty.прочитати(tmp_path, "нема") is None
    assert [ф.name for ф in (tmp_path / "програми").iterdir()] == ["Привіт.вуж"]


def test_список_за_абеткою_без_огляду_на_регістр(tmp_path):
    assert proekty.список(tmp_path) == []
    for назва in ("ялинка", "Борщ", "абетка", "Яблуко"):
        proekty.зберегти(tmp_path, назва, "")
    (tmp_path / "програми" / "нотатки.txt").write_text("не проєкт", encoding="utf-8")
    assert proekty.список(tmp_path) == ["абетка", "Борщ", "Яблуко", "ялинка"]


def test_список_за_українською_абеткою(tmp_path):
    """У Юнікоді ґ, є, і, ї стоять після я — список має йти за абеткою."""
    for назва in ("Яблуко", "Їжак", "Ігри", "Зима", "Єнот", "Ґанок", "Гра", "2048", "Zebra"):
        proekty.зберегти(tmp_path, назва, "")
    assert proekty.список(tmp_path) == [
        "2048", "Zebra", "Гра", "Ґанок", "Єнот", "Зима", "Ігри", "Їжак", "Яблуко"]


def test_пошук_за_назвою():
    назви = ["Гра в слова", "Калькулятор", "Моя гра", "Таблиця"]
    assert proekty.шукати(назви, "") == назви
    assert proekty.шукати(назви, "  ") == назви
    assert proekty.шукати(назви, "ГРА") == ["Гра в слова", "Моя гра"]
    assert proekty.шукати(назви, "ка") == ["Калькулятор"]
    assert proekty.шукати(назви, "а") == назви
    assert proekty.шукати(назви, "немає такого") == []


def test_пошук_потрібен_коли_проєктів_більше_десяти():
    assert not proekty.потрібен_пошук([str(i) for i in range(10)])
    assert proekty.потрібен_пошук([str(i) for i in range(11)])


def test_створити_відмовляє_якщо_назва_зайнята_або_порожня(tmp_path):
    assert proekty.створити(tmp_path, "Гра") == "Гра"
    assert proekty.прочитати(tmp_path, "Гра") == ""
    with pytest.raises(ПомилкаПроєкту, match="уже є"):
        proekty.створити(tmp_path, "гра")
    with pytest.raises(ПомилкаПроєкту, match="порожня"):
        proekty.створити(tmp_path, "  ")
    assert proekty.список(tmp_path) == ["Гра"]


def test_перейменувати(tmp_path):
    proekty.зберегти(tmp_path, "Стара", "код")
    proekty.зберегти(tmp_path, "Інша", "інше")
    assert proekty.перейменувати(tmp_path, "Стара", "Нова") == "Нова"
    assert proekty.список(tmp_path) == ["Інша", "Нова"]
    assert proekty.прочитати(tmp_path, "Нова") == "код"
    with pytest.raises(ПомилкаПроєкту, match="уже є"):
        proekty.перейменувати(tmp_path, "Нова", "інша")
    with pytest.raises(ПомилкаПроєкту, match="немає"):
        proekty.перейменувати(tmp_path, "Привид", "Щось")
    with pytest.raises(ПомилкаПроєкту, match="порожня"):
        proekty.перейменувати(tmp_path, "Нова", "")
    # лише регістр — можна, вміст на місці
    assert proekty.перейменувати(tmp_path, "Нова", "НОВА") == "НОВА"
    assert proekty.прочитати(tmp_path, "НОВА") == "код"
    assert proekty.прочитати(tmp_path, "Інша") == "інше"


def test_копія_має_нову_назву_і_той_самий_текст(tmp_path):
    proekty.зберегти(tmp_path, "Гра", "код гри")
    assert proekty.копія(tmp_path, "Гра") == "Гра (копія)"
    assert proekty.копія(tmp_path, "Гра") == "Гра (копія 2)"
    assert proekty.копія(tmp_path, "Гра") == "Гра (копія 3)"
    assert proekty.прочитати(tmp_path, "Гра (копія 2)") == "код гри"
    assert proekty.прочитати(tmp_path, "Гра") == "код гри"
    with pytest.raises(ПомилкаПроєкту):
        proekty.копія(tmp_path, "Привид")
    довга = "д" * 60
    proekty.зберегти(tmp_path, довга, "х")
    копія = proekty.копія(tmp_path, довга)
    assert len(копія) <= 60 and копія.endswith("(копія)")
    assert proekty.прочитати(tmp_path, копія) == "х"


def test_видалити(tmp_path):
    proekty.зберегти(tmp_path, "Гра", "код")
    proekty.видалити(tmp_path, "Гра")
    assert proekty.список(tmp_path) == []
    with pytest.raises(ПомилкаПроєкту, match="немає"):
        proekty.видалити(tmp_path, "Гра")


def test_вільна_назва(tmp_path):
    assert proekty.вільна_назва(tmp_path) == "Моя програма"
    proekty.зберегти(tmp_path, "Моя програма", "")
    assert proekty.вільна_назва(tmp_path) == "Моя програма 2"
    proekty.зберегти(tmp_path, "моя програма 2", "")
    assert proekty.вільна_назва(tmp_path) == "Моя програма 3"


# ---- відкритий проєкт: запуск застосунку -------------------------------------------

def test_перший_запуск_створює_проєкт_з_початковим_кодом(tmp_path):
    п = Проєкти(tmp_path, "початок\n")
    assert п.почати() == "початок\n"
    assert п.поточний == "Моя програма"
    assert proekty.прочитати(tmp_path, "Моя програма") == "початок\n"
    assert json.loads((tmp_path / "проєкт.json").read_text(encoding="utf-8")) == {"поточний": "Моя програма"}


def test_після_оновлення_стара_чернетка_стає_проєктом(tmp_path):
    """Стара версія тримала код у код.вуж без назви, а «Зберегти» клало
    програми в програми/ — нічого з цього не губиться."""
    (tmp_path / "код.вуж").write_text("незбережений код", encoding="utf-8")
    proekty.зберегти(tmp_path, "Моя програма", "давня програма")
    п = Проєкти(tmp_path, "початок")
    assert п.почати() == "незбережений код"
    assert п.поточний == "Моя програма 2"
    assert proekty.прочитати(tmp_path, "Моя програма 2") == "незбережений код"
    assert proekty.прочитати(tmp_path, "Моя програма") == "давня програма"


def test_після_оновлення_чернетка_що_збігається_з_проєктом_відкриває_його(tmp_path):
    proekty.зберегти(tmp_path, "Абетка", "інше")
    proekty.зберегти(tmp_path, "Гра", "код гри")
    (tmp_path / "код.вуж").write_text("код гри", encoding="utf-8")
    п = Проєкти(tmp_path)
    assert п.почати() == "код гри"
    assert п.поточний == "Гра"
    assert proekty.список(tmp_path) == ["Абетка", "Гра"]


def test_без_чернетки_відкривається_перший_проєкт(tmp_path):
    proekty.зберегти(tmp_path, "Борщ", "б")
    proekty.зберегти(tmp_path, "Абетка", "а")
    п = Проєкти(tmp_path, "початок")
    assert п.почати() == "а" and п.поточний == "Абетка"


def test_перезапуск_відкриває_той_самий_проєкт(tmp_path):
    proekty.зберегти(tmp_path, "Абетка", "а")
    proekty.зберегти(tmp_path, "Гра", "г")
    п = Проєкти(tmp_path)
    п.почати()
    assert п.відкрити("Гра") == "г"
    п.зберегти("г2")
    друга = Проєкти(tmp_path)
    assert друга.почати() == "г2" and друга.поточний == "Гра"


def test_чернетка_рятує_текст_якщо_застосунок_закрили_без_збереження(tmp_path):
    п = Проєкти(tmp_path, "початок")
    п.почати()
    п.чернетка("набрано, але не збережено")      # і тут застосунок убили
    assert proekty.прочитати(tmp_path, "Моя програма") == "початок"
    друга = Проєкти(tmp_path, "початок")
    assert друга.почати() == "набрано, але не збережено"
    assert друга.поточний == "Моя програма"
    assert proekty.прочитати(tmp_path, "Моя програма") == "набрано, але не збережено"


def test_запамʼятований_проєкт_зник_але_текст_лишився(tmp_path):
    п = Проєкти(tmp_path, "початок")
    п.почати()
    п.чернетка("мій код")
    файл(tmp_path, "Моя програма").unlink()
    друга = Проєкти(tmp_path)
    assert друга.почати() == "мій код"
    assert proekty.прочитати(tmp_path, друга.поточний) == "мій код"


def test_зіпсований_файл_стану_не_заважає_запуску(tmp_path):
    (tmp_path / "проєкт.json").write_text("{не json", encoding="utf-8")
    п = Проєкти(tmp_path, "початок")
    assert п.почати() == "початок"


# ---- відкритий проєкт: дії редактора ------------------------------------------------

@pytest.fixture
def п(tmp_path):
    proekty.зберегти(tmp_path, "Абетка", "а")
    proekty.зберегти(tmp_path, "Гра", "г")
    п = Проєкти(tmp_path, "початок")
    п.почати()                   # відкрито «Абетка»
    return п


def test_зберегти_пише_у_відкритий_проєкт(п):
    assert п.зберегти("а — нове")
    assert proekty.прочитати(п.тека, "Абетка") == "а — нове"
    assert proekty.прочитати(п.тека, "Гра") == "г"
    assert not Проєкти(п.тека).зберегти("нікуди")     # почати() ще не кликали


def test_відкрити_інший_проєкт(п):
    assert п.відкрити("Гра") == "г"
    assert п.поточний == "Гра"
    п.зберегти("г+")
    assert proekty.прочитати(п.тека, "Абетка") == "а"
    assert proekty.прочитати(п.тека, "Гра") == "г+"
    with pytest.raises(ПомилкаПроєкту, match="немає"):
        п.відкрити("Привид")
    assert п.поточний == "Гра"


def test_новий_порожній_проєкт_із_назвою(п):
    assert п.новий(" Калькулятор ") == "Калькулятор"
    assert п.поточний == "Калькулятор"
    assert proekty.прочитати(п.тека, "Калькулятор") == ""
    assert (п.тека / "код.вуж").read_text(encoding="utf-8") == ""
    with pytest.raises(ПомилкаПроєкту, match="уже є"):
        п.новий("гра")
    with pytest.raises(ПомилкаПроєкту, match="порожня"):
        п.новий("")
    assert п.поточний == "Калькулятор"
    assert proekty.прочитати(п.тека, "Гра") == "г"


def test_перейменувати_відкритий_проєкт_лишає_його_відкритим(п):
    assert п.перейменувати("Абетка", "Букви") == "Букви"
    assert п.поточний == "Букви"
    п.зберегти("а!")
    assert п.список() == ["Букви", "Гра"]
    assert Проєкти(п.тека).почати() == "а!"
    assert п.перейменувати("Гра", "Забава") == "Забава"
    assert п.поточний == "Букви"


def test_копія_не_міняє_відкритого(п):
    assert п.копія("Абетка") == "Абетка (копія)"
    assert п.поточний == "Абетка"
    assert п.список() == ["Абетка", "Абетка (копія)", "Гра"]


def test_видалити_інший_проєкт_не_чіпає_відкритого(п):
    assert п.видалити("Гра") is None
    assert п.поточний == "Абетка" and п.список() == ["Абетка"]


def test_видалити_відкритий_відкриває_наступний(п):
    assert п.видалити("Абетка") == "г"
    assert п.поточний == "Гра" and п.список() == ["Гра"]


def test_видалити_останній_лишає_порожній_новий(п):
    п.видалити("Гра")
    assert п.видалити("Абетка") == ""
    assert п.поточний == "Моя програма"
    assert п.список() == ["Моя програма"]
    assert Проєкти(п.тека, "початок").почати() == ""


def test_пошук_у_списку_проєктів(п):
    assert not п.потрібен_пошук()
    for i in range(9):
        п.новий(f"Проба {i}")
    assert len(п.список()) == 11 and п.потрібен_пошук()
    assert п.список("гр") == ["Гра"]
    assert len(п.список("проба")) == 9


# ---- вікно проєктів на підставних віджетах ----------------------------------------------

class _Подія:
    def __init__(self, дія):
        self.дія, self.скасовано = дія, False

    def cancel(self):
        self.скасовано = True


class _Годинник:
    def __init__(self):
        self.події = []

    def schedule_once(self, дія, затримка=0):
        подія = _Подія(дія)
        self.події.append(подія)
        return подія

    def минув_час(self):
        події, self.події = self.події, []
        for подія in події:
            if not подія.скасовано:
                подія.дія(0)


class _Віджет:
    def __init__(self, **kw):
        self.children, self.обробники, self.text = [], {}, ""
        self.__dict__.update(kw)

    def add_widget(self, віджет):
        self.children.append(віджет)

    def clear_widgets(self):
        self.children = []

    def bind(self, **kw):
        for назва, дія in kw.items():
            self.обробники.setdefault(назва, []).append(дія)

    def setter(self, назва):
        return lambda і, значення: setattr(self, назва, значення)

    def подія(self, назва, *аргументи):
        for дія in self.обробники.get(назва, []):
            дія(self, *аргументи)

    def collide_point(self, x, y):
        return True

    def on_touch_down(self, touch):
        return False

    on_touch_move = on_touch_up = on_touch_down


class _Кнопка(_Віджет):
    def on_release(self):
        self.подія("on_release")


class _Вікно(_Віджет):
    відкрите = True

    def open(self):
        self.відкрите = True

    def dismiss(self):
        self.відкрите = False


@pytest.fixture
def kivy(monkeypatch):
    """Підставний Kivy — рівно те, що імпортує vikno_proektiv.py."""
    годинник = _Годинник()

    def модуль(назва, **вміст):
        м = types.ModuleType(назва)
        м.__dict__.update(вміст)
        monkeypatch.setitem(sys.modules, назва, м)

    for назва in ("kivy", "kivy.uix"):
        модуль(назва)
    модуль("kivy.clock", Clock=годинник)
    модуль("kivy.metrics", dp=lambda x: x, sp=lambda x: x)
    модуль("kivy.uix.boxlayout", BoxLayout=type("BoxLayout", (_Віджет,), {}))
    модуль("kivy.uix.button", Button=_Кнопка)
    модуль("kivy.uix.label", Label=type("Label", (_Віджет,), {}))
    модуль("kivy.uix.modalview", ModalView=_Вікно)
    модуль("kivy.uix.scrollview", ScrollView=type("ScrollView", (_Віджет,), {}))
    модуль("kivy.uix.textinput", TextInput=type("TextInput", (_Віджет,), {}))
    monkeypatch.delitem(sys.modules, "vikno_proektiv", raising=False)
    yield годинник
    sys.modules.pop("vikno_proektiv", None)


def усі(віджет, тип=None):
    знайдені = [] if тип and type(віджет).__name__ != тип else [віджет]
    for дитина in віджет.children:
        знайдені += усі(дитина, тип)
    return знайдені


def тексти(вікно):
    return [в.text for в in усі(вікно) if в.text]


def кнопка(вікно, напис):
    for в in усі(вікно):
        if isinstance(в, _Кнопка) and в.text == напис:
            return в
    raise AssertionError(f"немає кнопки «{напис}»: {тексти(вікно)}")


def поле(вікно):
    (п,) = усі(вікно, "TextInput")
    return п


class Дотик:
    def __init__(self, x=5, y=5):
        self.x, self.y, self.pos = x, y, (x, y)


@pytest.fixture
def вікно(kivy, п):
    import vikno_proektiv

    відкрито, змінено = [], []
    в = vikno_proektiv.ВікноПроєктів(
        п, при_відкритті=відкрито.append, при_зміні=lambda: змінено.append(п.поточний))
    в.годинник, в.відкрито, в.змінено = kivy, відкрито, змінено
    в.показати_список()
    return в


def test_вікно_показує_проєкти_і_позначає_відкритий(вікно):
    assert [к.text for к in усі(вікно, "КнопкаПроєкту")] == ["Абетка  (відкрито)", "Гра"]
    assert усі(вікно, "TextInput") == []          # проєктів мало — пошуку немає
    кнопка(вікно, "Новий"), кнопка(вікно, "Закрити")


def test_дотик_відкриває_проєкт_у_редакторі(вікно):
    кнопка(вікно, "Гра").on_release()
    assert вікно.відкрито == ["г"]
    assert вікно.проєкти.поточний == "Гра"
    assert not вікно.відкрите


def test_довгий_дотик_показує_дії_а_не_відкриває(вікно):
    рядок = кнопка(вікно, "Гра")
    рядок.on_touch_down(Дотик())
    вікно.годинник.минув_час()                 # палець тримали пів секунди
    рядок.on_touch_up(Дотик())
    рядок.on_release()                         # Kivy шле on_release і після довгого дотику
    assert вікно.відкрито == [] and вікно.відкрите
    assert вікно.проєкти.поточний == "Абетка"
    for напис in ("Відкрити", "Перейменувати", "Зробити копію", "Видалити", "Назад"):
        кнопка(вікно, напис)


def test_короткий_дотик_і_гортання_не_вважаються_довгим(вікно):
    рядок = кнопка(вікно, "Гра")
    рядок.on_touch_down(Дотик())
    рядок.on_touch_up(Дотик())                 # відпустили одразу
    вікно.годинник.минув_час()
    assert "Перейменувати" not in тексти(вікно)
    рядок.on_touch_down(Дотик(5, 5))
    рядок.on_touch_move(Дотик(5, 80))          # палець поїхав — це гортання
    вікно.годинник.минув_час()
    assert "Перейменувати" not in тексти(вікно)


def test_перейменування_з_вікна(вікно):
    вікно.показати_дії("Абетка")
    кнопка(вікно, "Перейменувати").on_release()
    assert поле(вікно).text == "Абетка"
    поле(вікно).text = "Гра"
    кнопка(вікно, "Перейменувати").on_release()
    assert any("уже є" in т for т in тексти(вікно))      # помилка тут же, поле на місці
    поле(вікно).text = "Букви"
    поле(вікно).подія("on_text_validate")                  # Enter на клавіатурі
    assert вікно.проєкти.список() == ["Букви", "Гра"]
    assert вікно.змінено == ["Букви"]                      # назва вгорі редактора оновилась
    assert [к.text for к in усі(вікно, "КнопкаПроєкту")] == ["Букви  (відкрито)", "Гра"]


def test_копія_з_вікна(вікно):
    вікно.показати_дії("Гра")
    кнопка(вікно, "Зробити копію").on_release()
    assert [к.text for к in усі(вікно, "КнопкаПроєкту")] == ["Абетка  (відкрито)", "Гра", "Гра (копія)"]
    assert вікно.відкрито == []


def test_видалення_питає_підтвердження(вікно):
    вікно.показати_дії("Гра")
    кнопка(вікно, "Видалити").on_release()
    assert вікно.проєкти.список() == ["Абетка", "Гра"]     # ще нічого не стерто
    assert any("Видалити проєкт «Гра»?" in т for т in тексти(вікно))
    кнопка(вікно, "Ні").on_release()
    assert вікно.проєкти.список() == ["Абетка", "Гра"]
    вікно.показати_дії("Гра")
    кнопка(вікно, "Видалити").on_release()
    кнопка(вікно, "Так, видалити").on_release()
    assert вікно.проєкти.список() == ["Абетка"]
    assert вікно.відкрито == []                            # відкритий проєкт не чіпали


def test_видалення_відкритого_показує_в_редакторі_наступний(вікно):
    вікно.показати_підтвердження("Абетка")
    кнопка(вікно, "Так, видалити").on_release()
    assert вікно.відкрито == ["г"] and вікно.проєкти.поточний == "Гра"


def test_новий_проєкт_з_вікна(вікно):
    кнопка(вікно, "Новий").on_release()
    кнопка(вікно, "Створити").on_release()                 # порожня назва
    assert any("порожня" in т for т in тексти(вікно))
    assert вікно.відкрите and вікно.відкрито == []
    поле(вікно).text = "Калькулятор"
    кнопка(вікно, "Створити").on_release()
    assert вікно.проєкти.поточний == "Калькулятор"
    assert вікно.відкрито == [""] and not вікно.відкрите
    assert proekty.прочитати(вікно.проєкти.тека, "Калькулятор") == ""


def test_пошук_зʼявляється_коли_проєктів_більше_десяти(вікно):
    for i in range(9):
        proekty.зберегти(вікно.проєкти.тека, f"Проба {i}", "")
    вікно.показати_список()
    пошук = поле(вікно)
    assert len(усі(вікно, "КнопкаПроєкту")) == 11
    пошук.подія("text", "гр")
    assert [к.text for к in усі(вікно, "КнопкаПроєкту")] == ["Гра"]
    пошук.подія("text", "щось інше")
    assert усі(вікно, "КнопкаПроєкту") == [] and "Нічого не знайдено." in тексти(вікно)
    пошук.подія("text", "")
    assert len(усі(вікно, "КнопкаПроєкту")) == 11


# ---- main.py: прив'язка до редактора (текстом) -----------------------------------------

def test_редактор_має_проєкти_замість_зберегти_відкрити():
    текст = (КОРІНЬ / "main.py").read_text(encoding="utf-8")
    assert 'Button(text="Проєкти", on_release=self._показати_проєкти)' in текст
    assert 'Button(text="Новий", on_release=self._новий_проєкт)' in текст
    assert 'Button(text="Зберегти"' not in текст and 'Button(text="Відкрити"' not in текст
    assert "proekty.Проєкти(self.user_data_dir, ПОЧАТКОВИЙ_КОД)" in текст
    assert 'f"Проєкт: {назва}"' in текст


def test_редактор_зберігає_проєкт_при_запуску_і_виході():
    текст = (КОРІНЬ / "main.py").read_text(encoding="utf-8")
    for дія in ("_виконати", "on_pause", "on_stop", "_вікно_проєктів"):
        початок = текст.index(f"    def {дія}(self")
        тіло = текст[початок:текст.index("\n    def ", початок + 1)]
        assert "self._зберегти_проєкт()" in тіло, дія
    assert "self._проєкти.чернетка(текст)" in текст


def test_файли_проєктів_потрапляють_в_apk():
    spec = (КОРІНЬ / "buildozer.spec").read_text(encoding="utf-8")
    assert "source.include_exts = py," in spec
    for ім_я in ("proekty.py", "vikno_proektiv.py"):
        assert (КОРІНЬ / ім_я).is_file()


# ---- старе розширення .мова (до перейменування мови на «Вуж») -----------------

def _старий_проєкт(тека, назва, текст):
    (тека / "програми").mkdir(parents=True, exist_ok=True)
    ф = тека / "програми" / f"{назва}.мова"
    ф.write_text(текст, encoding="utf-8")
    return ф


def test_старі_файли_мова_видно_у_списку_і_вони_відкриваються(tmp_path):
    _старий_проєкт(tmp_path, "Гра", "стара гра")
    proekty.зберегти(tmp_path, "Абетка", "а")
    assert proekty.список(tmp_path) == ["Абетка", "Гра"]
    assert proekty.існує(tmp_path, "Гра")
    assert proekty.прочитати(tmp_path, "Гра") == "стара гра"
    assert proekty.безпечна_назва("Гра.мова") == "Гра" and proekty.безпечна_назва("Гра.вуж") == "Гра"
    п = Проєкти(tmp_path)
    assert п.відкрити("Гра") == "стара гра" and п.поточний == "Гра"


def test_збереження_старого_проєкту_переносить_його_у_вуж(tmp_path):
    старий = _старий_проєкт(tmp_path, "Гра", "стара гра")
    proekty.зберегти(tmp_path, "Гра", "нова гра")
    assert not старий.exists() and (tmp_path / "програми" / "Гра.вуж").is_file()
    assert proekty.список(tmp_path) == ["Гра"]
    assert proekty.прочитати(tmp_path, "Гра") == "нова гра"


def test_новий_файл_вуж_має_перевагу_над_старим_і_назва_у_списку_одна(tmp_path):
    _старий_проєкт(tmp_path, "Гра", "стара")
    (tmp_path / "програми" / "Гра.вуж").write_text("нова", encoding="utf-8")
    assert proekty.список(tmp_path) == ["Гра"]
    assert proekty.прочитати(tmp_path, "Гра") == "нова"


def test_старий_проєкт_перейменовується_копіюється_і_видаляється(tmp_path):
    старий = _старий_проєкт(tmp_path, "Гра", "г")
    with pytest.raises(ПомилкаПроєкту):
        proekty.створити(tmp_path, "гра")                 # назва зайнята старим файлом
    assert proekty.копія(tmp_path, "Гра") == "Гра (копія)"
    assert proekty.перейменувати(tmp_path, "Гра", "Забава") == "Забава"
    assert not старий.exists() and (tmp_path / "програми" / "Забава.вуж").is_file()
    assert proekty.список(tmp_path) == ["Гра (копія)", "Забава"]
    _старий_проєкт(tmp_path, "Давнє", "д")
    proekty.видалити(tmp_path, "Давнє")
    assert proekty.список(tmp_path) == ["Гра (копія)", "Забава"]


def test_стара_чернетка_код_мова_не_губиться(tmp_path):
    (tmp_path / "код.мова").write_text("незбережене зі старої версії", encoding="utf-8")
    п = Проєкти(tmp_path, "початок")
    assert п.почати() == "незбережене зі старої версії"
    assert (tmp_path / "код.вуж").read_text(encoding="utf-8") == "незбережене зі старої версії"
    assert not (tmp_path / "код.мова").exists()
