#!/usr/bin/env python3
"""Точка входу Kivy-застосунку «Вуж» для Android: редактор коду з запуском.

Екран: прокручувана панель кнопок («Виконати», «Стоп», «Очистити вивід»,
«Очистити код»), поле коду з номерами рядків і підсвіткою (CodeInput +
лексер pygments з redaktor.py), рядок пояснення помилки, панель швидкого
вводу (каркаси конструкцій), знизу прокручуваний вивід. Над кнопками —
назва відкритого проєкту. Програма виконується в окремому
потоці, «Стоп» виставляє ВМ.зупинено — див. zapusk.виконати_код.

«запитай("…")» (і старе «питай("…")») друкує запитання у вивід і показує
під виводом рядок вводу з кнопкою «Далі» — лише поки програма чекає на
відповідь; потік виконання чекає на неї (або на «Стоп»). «кнопка("Напис", дія)» додає кнопку під виводом; програма з
кнопками після основного коду чекає натискань (zapusk._чекати_кнопок),
доки «Стоп» або «Очистити вивід». «Довідка» друкує у вивід перелік слів
і дій мови (yadro/dovidka.py). Полотно в редакторі — лише для бібліотеки
«екран» (підключи("екран")): перший онови() показує його на місці
виводу, дотики до нього йдуть програмі (торкнувся(), палець_х/у), кнопка
«Полотно»/«Вивід» над ним перемикає назад. Аркуш креслення в редакторі
не показується (з 1.5 CAD виноситься в бібліотеки; програма з
аркуш()/контур() пише креслення.html через покажи(), а полотно креслення
лишається в застосунках з програм — zastosunky.py). «Проєкти» — список
збережених програм (тека застосунку/програми): дотик відкриває, довгий
дотик — перейменувати, зробити копію, видалити; «Новий» — порожній
проєкт із назвою (вікно — vikno_proektiv.py, логіка без Kivy —
proekty.py). Відкритий проєкт зберігається сам: при «Виконати», коли
застосунок згортають чи закривають, перед показом списку; текст після
кожної зміни ще й лягає в чернетку user_data_dir/код.вуж. «Зробити застосунок»
— поточна програма стає окремим застосунком (zastosunky.py: тека
застосунки/назва/ з програма.вуж, main.py-запускачем, buildozer.spec,
icon.png) і, якщо в «Налаштування» задано токен GitHub, публікується в
репозиторій одним комітом через API (github.py) — далі workflow
zastosunky.yml збирає APK. Токен зберігається у теці застосунку
(налаштування.json) і ніколи не друкується. Поле коду гортається пальцем в обидва
боки (scroll_from_swipe), номери рядків лишаються на місці. Редакторська логіка (каркаси, автовідступ, автозакриття, перевірка
помилок) живе в redaktor.py без Kivy і тестується на комп'ютері; тут —
лише прив'язка до віджетів. Рядок з помилкою підкреслюється червоним;
пояснення з'являється після дотику до цього рядка і зникає при наборі.
«Знайти» відкриває над полем коду панель пошуку й заміни, «До рядка» —
перехід до рядка за номером (panel_poshuku.py; збіги підсвічує ПолеКоду).

Уся робота з yadro/* іде через zapusk.виконати_код і redaktor.перевірити.
Імпорти yadro/* не відбуваються на верхньому рівні: якщо щось не
імпортується саме в Android-збірці, застосунок усе одно підніме вікно й
покаже traceback разом із діагностикою — і продублює її у
user_data_dir/crash.txt.
"""

import os
import sys
import threading
import traceback
from pathlib import Path

сюди = Path(__file__).resolve().parent
if str(сюди) not in sys.path:
    sys.path.insert(0, str(сюди))

# Версія — лише в yadro/versiya.py (buildozer.spec бере її звідти через
# version.regex, тож назва APK і напис в інтерфейсі завжди збігаються).
try:
    from yadro.versiya import ВЕРСІЯ
except Exception:  # крах-екран усе одно має піднятись
    ВЕРСІЯ = "?"

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.graphics import Color, InstructionGroup, Line, Rectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.codeinput import CodeInput
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.stacklayout import StackLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.textinput import TextInput

import github
import proekty
import redaktor
import vyvid
import zastosunky
from panel_poshuku import ПанельПошуку
from vidzhety import ПолотноКреслення, РядЩоХовається, прокручуваний_ряд, прокручуваний_текст
from vikno_proektiv import ВікноПроєктів
from yadro import dovidka

# Вікно стискається над екранною клавіатурою, тож панель швидких кнопок
# (одразу під полем коду) лишається видимою над клавіатурою.
Window.softinput_mode = "resize"

МОНО = "RobotoMono-Regular"  # входить у Kivy, підтримує кирилицю
ЗАТРИМКА_ПЕРЕВІРКИ = 0.7  # с після останнього набору — перевірити код
КОЛІР_ЗБІГУ = (1, 0.85, 0.2, 0.4)        # підсвітка знайденого (пошук)
КОЛІР_ПОТОЧНОГО_ЗБІГУ = (1, 0.5, 0.1, 0.6)

ПОЧАТКОВИЙ_КОД = (
    'друкуй("Привіт з Android!")\n'
    "хай а = [1, 2, 3]\n"
    "додай(а, 4)\n"
    'друкуй("Список:", а)\n'
    "дія у_квадраті(х)\n"
    "    поверни х * х\n"
    'друкуй("5 у квадраті =", у_квадраті(5))\n'
)


def _шапка_діагностики():
    """Версія, вміст теки з main.py, sys.path — лише для крах-екрана."""
    рядки = [f"Вуж, версія {ВЕРСІЯ}"]
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


class ПолеКоду(CodeInput):
    """CodeInput з автовідступом, автозакриттям дужок/лапок і червоним
    підкресленням рядка з помилкою (рядок_помилки, з 1; 0 — немає).
    Дотик до рядка повідомляє при_дотику(номер_рядка_з_1). Для пошуку
    (panel_poshuku.py): показати_збіги() підсвічує знайдене, перейти()
    ставить курсор і прокручує поле так, щоб місце було видно."""

    рядок_помилки = NumericProperty(0)

    def __init__(self, при_дотику=None, **kw):
        super().__init__(**kw)
        self.при_дотику = при_дотику
        self._збіги = []            # індекси початків збігів пошуку
        self._довжина_збігу = 0
        self._поточний_збіг = -1
        self._група_збігів = InstructionGroup()
        self.canvas.after.add(self._група_збігів)
        with self.canvas.after:
            self._колір_підкр = Color(0.9, 0.15, 0.15, 0)
            self._лінія_підкр = Line(points=[0, 0, 0, 0], width=dp(1.2))
        self.bind(
            scroll_y=self._оновити_підкреслення, scroll_x=self._оновити_підкреслення,
            pos=self._оновити_підкреслення, size=self._оновити_підкреслення,
            text=self._оновити_підкреслення, line_height=self._оновити_підкреслення,
            рядок_помилки=self._оновити_підкреслення,
        )
        self.bind(
            scroll_y=self._оновити_підсвітку, scroll_x=self._оновити_підсвітку,
            pos=self._оновити_підсвітку, size=self._оновити_підсвітку,
            text=self._оновити_підсвітку, line_height=self._оновити_підсвітку,
        )

    # ---- набір ----------------------------------------------------------

    def insert_text(self, substring, from_undo=False):
        if not from_undo and len(substring) == 1:
            курсор = self.cursor_index()
            if substring == "\n":
                substring = redaktor.автовідступ(self.text, курсор)
            else:
                результат = redaktor.автозакриття(self.text, курсор, substring)
                if результат is not None:
                    вставка, новий_курсор = результат
                    if вставка:
                        super().insert_text(вставка, from_undo)
                    self.cursor = self.get_cursor_from_index(новий_курсор)
                    return
        return super().insert_text(substring, from_undo)

    # ---- гортання пальцем ----------------------------------------------------
    # Kivy 2.3.0: у багаторядковому полі свайп рухає лише scroll_y, а
    # get_max_scroll_x рахує ширину лише першого рядка. Тому вбік поле
    # «гортав» тільки курсор, що виходив за край, а назад ліворуч —
    # ніяк. Тут: свайп рухає і scroll_x, межа — за найдовшим рядком.

    def _макс_scroll_x(self):
        текст = self.text
        if getattr(self, "_кеш_ширини_текст", None) != текст:
            try:
                ширина = max((self._get_row_width(i) for i in range(len(self._lines))), default=0)
            except Exception:
                ширина = 0
            self._кеш_ширини_текст = текст
            self._кеш_ширини = ширина
        return max(0, self._кеш_ширини + self.padding[0] + self.padding[2] - self.width)

    def get_max_scroll_x(self):
        return self._макс_scroll_x()

    def scroll_text_from_swipe(self, touch):
        результат = super().scroll_text_from_swipe(touch)
        if self.multiline and getattr(self, "_have_scrolled", False):
            self.scroll_x = min(max(0, self.scroll_x - touch.dx), self._макс_scroll_x())
            self._trigger_update_graphics()
        return результат

    # ---- дотик ----------------------------------------------------------

    def on_touch_down(self, touch):
        результат = super().on_touch_down(touch)
        if self.collide_point(*touch.pos) and self.при_дотику is not None:
            Clock.schedule_once(lambda dt: self.при_дотику(self.cursor_row + 1), 0)
        return результат

    # ---- підкреслення ---------------------------------------------------

    def _y_низ_рядка(self, номер):
        """y нижнього краю рядка (з 1) у координатах вікна."""
        return self.top - self.padding[1] + self.scroll_y - номер * self.line_height

    def _оновити_підкреслення(self, *_):
        номер = int(self.рядок_помилки)
        if номер <= 0 or номер > self.text.count("\n") + 1:
            self._колір_підкр.a = 0
            return
        y = self._y_низ_рядка(номер) + dp(2)
        if y < self.y or y > self.top:
            self._колір_підкр.a = 0
            return
        self._колір_підкр.a = 1
        self._лінія_підкр.points = [
            self.x + self.padding[0], y, self.right - self.padding[2], y,
        ]

    # ---- пошук: підсвітка збігів і перехід ---------------------------------
    # Підсвітка — свої прямокутники поверх тексту, а не виділення поля:
    # виділення зникає, щойно поле втрачає фокус, а під час пошуку фокус —
    # у полі «Знайти».

    def _початки_рядків(self):
        текст = self.text
        if getattr(self, "_кеш_початків_текст", None) != текст:
            self._кеш_початків_текст = текст
            self._кеш_початків = redaktor.початки_рядків(текст)
        return self._кеш_початків

    def _ширина_тексту(self, текст):
        if not текст:
            return 0
        try:
            return self._get_text_width(текст, self.tab_width, self._label_cached)
        except Exception:
            return len(текст) * self.font_size * 0.6

    def показати_збіги(self, збіги, довжина, поточний):
        """Підсвітити збіги (індекси початків у тексті, усі однієї
        довжини); поточний (номер з 0 або -1) — яскравіше."""
        self._збіги, self._довжина_збігу, self._поточний_збіг = збіги, довжина, поточний
        self._оновити_підсвітку()

    def _оновити_підсвітку(self, *_):
        група = self._група_збігів
        група.clear()
        висота = self.line_height
        if not self._збіги or self._довжина_збігу <= 0 or висота <= 0:
            return
        текст = self.text
        початки = self._початки_рядків()
        перший = int(self.scroll_y // висота)
        останній = перший + int(self.height // висота) + 1
        ліво, право = self.x + self.padding[0], self.right - self.padding[2]
        for рядок, стовпчик, номер in redaktor.видимі_збіги(self._збіги, початки, перший, останній):
            початок = початки[рядок] + стовпчик
            x0 = ліво - self.scroll_x + self._ширина_тексту(текст[початки[рядок]:початок])
            x1 = x0 + self._ширина_тексту(текст[початок:початок + self._довжина_збігу])
            низ = self._y_низ_рядка(рядок + 1)
            # текст поля обрізається його межами, прямокутники — вручну
            x0, x1 = max(x0, ліво), min(x1, право)
            низ, верх = max(низ, self.y), min(низ + висота, self.top)
            if x1 <= x0 or верх <= низ:
                continue
            група.add(Color(*(КОЛІР_ПОТОЧНОГО_ЗБІГУ if номер == self._поточний_збіг else КОЛІР_ЗБІГУ)))
            група.add(Rectangle(pos=(x0, низ), size=(x1 - x0, верх - низ)))

    def перейти(self, початок, кінець=None):
        """Курсор на індекс «початок» і прокрутка: рядок — посередині
        поля, проміжок початок..кінець видно й по ширині. Kivy сам лише
        дотягує курсор до краю поля — знайдене лишалося б за краєм."""
        текст = self.text
        початки = self._початки_рядків()
        рядок, стовпчик = redaktor.рядок_і_стовпчик(текст, початок, початки)
        кінець = початок if кінець is None else кінець
        self.cursor = (стовпчик, рядок)
        відступи = self.padding
        self.scroll_y = redaktor.прокрутка_до_рядка(
            рядок, self.line_height, self.height - відступи[1] - відступи[3], len(початки))
        ліво = self._ширина_тексту(текст[початки[рядок]:початок])
        право = ліво + self._ширина_тексту(текст[початок:кінець])
        self.scroll_x = min(
            redaktor.прокрутка_вбік(ліво, право, self.scroll_x, self.width - відступи[0] - відступи[2]),
            max(self._макс_scroll_x(), 0),
        )
        self._trigger_update_graphics()


class НомериРядків(StencilView):
    """Колонка номерів рядків, вирівняна з рядками поля коду і синхронно
    з ним прокручувана."""

    def __init__(self, поле, **kw):
        super().__init__(size_hint_x=None, width=dp(36), **kw)
        self.поле = поле
        self.мітка = Label(
            font_name=поле.font_name, font_size=поле.font_size,
            halign="right", valign="top", color=(0.5, 0.5, 0.56, 1),
            size_hint=(None, None),
        )
        self.add_widget(self.мітка)
        поле.bind(
            text=self._оновити, scroll_y=self._оновити, size=self._оновити,
            pos=self._оновити, line_height=self._оновити, font_size=self._оновити,
        )
        self.bind(size=self._оновити, pos=self._оновити)
        Clock.schedule_once(self._оновити, 0)

    def _оновити(self, *_):
        поле = self.поле
        n = поле.text.count("\n") + 1
        self.мітка.text = "\n".join(str(i) for i in range(1, n + 1))
        # Висота рядка Label — множник від висоти рядка шрифту; підганяємо
        # під фактичну висоту рядка поля коду, щоб номери не «пливли».
        рядок_шрифту = CoreLabel(font_name=поле.font_name, font_size=поле.font_size).get_extents("0")[1]
        if рядок_шрифту:
            self.мітка.line_height = поле.line_height / рядок_шрифту
        self.мітка.font_size = поле.font_size
        self.мітка.size = (self.width - dp(6), n * поле.line_height + dp(4))
        self.мітка.text_size = self.мітка.size
        self.мітка.x = self.x
        self.мітка.top = поле.top - поле.padding[1] + поле.scroll_y


def plata_підключено_по_wifi():
    from yadro import plata
    назва = plata.підключено()
    return bool(назва) and назва.startswith("Wi-Fi")


class ВужApp(App):
    title = "Вуж"

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
            прокрутка, _ = прокручуваний_текст(тіло + "\n" + "-" * 40 + "\n" + шапка)
            return прокрутка

    # ---- екран редактора ------------------------------------------------

    def _зібрати_редактор(self):
        self._проєкти = proekty.Проєкти(self.user_data_dir, ПОЧАТКОВИЙ_КОД)
        self._потік = None          # потік виконання (threading.Thread) або None
        self._вм = None             # ВМ поточного запуску — для «Стоп»
        self._стоп_запитано = False
        self._помилка = None        # (рядок, пояснення) або None
        self._перевірка = None      # запланована перевірка коду (Clock event)
        self._відповідь = None      # відповідь на «питай» з поля вводу
        self._чекаю_відповідь = threading.Event()
        self._вивід_очищено = False # «Очистити вивід» під час очікування кнопок
        корінь = BoxLayout(orientation="vertical", padding=dp(6), spacing=dp(4))

        # Назва відкритого проєкту — над кнопками, на всю ширину
        self._назва_проєкту = Label(
            text="", size_hint_y=None, height=dp(24), halign="left", valign="middle",
            font_size=sp(15), bold=True, shorten=True, shorten_from="right",
        )
        self._назва_проєкту.bind(size=lambda і, р: setattr(і, "text_size", (р[0] - dp(8), р[1])))
        корінь.add_widget(self._назва_проєкту)

        корінь.add_widget(self._панель_кнопок())

        self.код = ПолеКоду(
            при_дотику=self._при_дотику_до_рядка,
            text=self._почати_проєкт(), font_name=МОНО, font_size=sp(15),
            multiline=True, auto_indent=False, do_wrap=False,
            scroll_from_swipe=True, style_name="default",
        )
        if redaktor.ВужLexer is not None:
            self.код.lexer = redaktor.ВужLexer()
        self.код.bind(text=self._при_зміні_тексту)

        # Пошук, заміна, перехід до рядка — смужка над полем коду (висота
        # 0, доки не натиснуто «Знайти» чи «До рядка»)
        self._пошук = ПанельПошуку(self.код, шрифт=МОНО)
        корінь.add_widget(self._пошук)

        редактор = BoxLayout(orientation="horizontal", size_hint_y=0.55, spacing=dp(2))
        редактор.add_widget(НомериРядків(self.код))
        редактор.add_widget(self.код)
        корінь.add_widget(редактор)

        # Пояснення помилки — звичайний рядок під полем коду (не вікно);
        # висота 0 = сховано.
        self.пояснення = Label(
            text="", size_hint_y=None, height=0, halign="left", valign="top",
            color=(0.85, 0.15, 0.15, 1), font_size=sp(13),
        )
        self.пояснення.bind(width=lambda і, ш: setattr(і, "text_size", (ш - dp(8), None)))
        корінь.add_widget(self.пояснення)

        корінь.add_widget(self._панель_вставок())

        self._прокрутка_виводу, self.вивід = прокручуваний_текст(
            "Натисни «Виконати».", шрифт=МОНО, розмір=sp(14)
        )
        self.вивід.межа = vyvid.прочитати_межу(self.user_data_dir)
        self._низ = BoxLayout(orientation="vertical")
        self._низ.add_widget(self._прокрутка_виводу)
        корінь.add_widget(self._низ)
        self._зібрати_полотно()

        корінь.add_widget(self._рядок_вводу())
        корінь.add_widget(self._ряд_кнопок_програми())

        self._запланувати_перевірку()
        return корінь

    # ---- полотно бібліотеки «екран» ----------------------------------------

    def _зібрати_полотно(self):
        """Полотно для підключи("екран"): займає місце виводу, коли
        програма вперше кличе онови(). Над ним — вузька кнопка, що
        перемикає полотно й вивід (вона ж лишається над виводом, поки є
        що показати)."""
        self._кадр = None             # останній кадр від онови()
        self._кадр_заплановано = False
        self._показано_полотно = False
        self._полотно_було = False    # у цьому запуску полотно вже показувалось
        self._стоп_був = False        # останній запуск закінчився кнопкою «Стоп»
        self.вивід.bind(text=self._при_зміні_виводу)
        self._полотно = ПолотноКреслення(при_дотику=self._дотик_полотна)
        self._кн_полотно = Button(
            text="Вивід", size_hint_y=None, height=0, opacity=0, disabled=True, font_size=sp(13),
        )
        self._кн_полотно.bind(on_release=lambda *_: self._показати_полотно(not self._показано_полотно))
        self._низ.add_widget(self._кн_полотно, index=len(self._низ.children))

    def _при_зміні_виводу(self, *_):
        # «Довідка», «Проєкти», «Плата»… пишуть у вивід — його має бути
        # видно, а не полотно від попереднього запуску
        if self._показано_полотно and self._потік is None:
            self._показати_полотно(False)

    def _дотик_полотна(self, x, y, натиснуто):
        from zapusk import дотик_екрана
        дотик_екрана(x, y, натиснуто)

    def _розмір_екрана(self):
        """Розмір полотна в пікселях для ширина()/висота(): місце виводу
        без кнопки перемикання (полотно ще може бути не показане)."""
        return int(self._низ.width), int(max(self._низ.height - dp(32), 1))

    def _при_кадрі(self, кадр):
        """З потоку виконання (онови()): показати кадр у головному потоці.
        Якщо програма малює швидше за екран — показується лише найновіший."""
        self._кадр = кадр
        if not self._кадр_заплановано:
            self._кадр_заплановано = True
            Clock.schedule_once(self._намалювати_кадр, 0)

    def _намалювати_кадр(self, dt):
        self._кадр_заплановано = False
        if self._кадр is None:
            return
        if not self._показано_полотно and not self._полотно_було:
            self._показати_полотно(True)
        self._полотно_було = True
        self._полотно.показати(self._кадр)

    def _показати_полотно(self, так):
        if так and self._кадр is None:
            return
        self._показано_полотно = так
        self._кн_полотно.text = "Вивід" if так else "Полотно"
        self._кн_полотно.height = dp(32)
        self._кн_полотно.opacity = 1
        self._кн_полотно.disabled = False
        старий, новий = (self._прокрутка_виводу, self._полотно) if так else (self._полотно, self._прокрутка_виводу)
        if старий.parent is self._низ:
            self._низ.remove_widget(старий)
        if новий.parent is None:
            self._низ.add_widget(новий)
        if так:
            Clock.schedule_once(lambda dt: self._полотно.вмістити(), 0)

    def _прибрати_полотно(self):
        """Новий запуск: знову вивід, кнопки перемикання немає, доки
        програма не намалює кадр."""
        self._показати_полотно(False)
        self._кадр = None
        self._полотно_було = False
        self._кн_полотно.height = 0
        self._кн_полотно.opacity = 0
        self._кн_полотно.disabled = True

    def _ряд_кнопок_програми(self):
        """Кнопки, оголошені програмою через кнопка("Напис", дія). Ряд
        горизонтально прокручуваний; висота 0, поки кнопок немає."""
        self._кнопки_програми = BoxLayout(size_hint=(None, 1), spacing=dp(4))
        self._кнопки_програми.bind(minimum_width=self._кнопки_програми.setter("width"))
        self._прокрутка_кнопок = ScrollView(
            size_hint_y=None, height=0, do_scroll_y=False, bar_width=0, opacity=0,
        )
        self._прокрутка_кнопок.add_widget(self._кнопки_програми)
        return self._прокрутка_кнопок

    def _додати_кнопку_програми(self, напис, натиснути):
        """Викликається з потоку виконання — віджет створюємо в головному."""
        def створити(dt):
            кнопка = Button(
                text=напис, size_hint_x=None, font_size=sp(15),
                width=max(dp(60), dp(11) * len(напис) + dp(24)),
            )
            кнопка.bind(on_release=lambda к: натиснути())
            self._кнопки_програми.add_widget(кнопка)
            self._прокрутка_кнопок.height = dp(44)
            self._прокрутка_кнопок.opacity = 1

        Clock.schedule_once(створити, 0)

    def _прибрати_кнопки_програми(self):
        self._кнопки_програми.clear_widgets()
        self._прокрутка_кнопок.height = 0
        self._прокрутка_кнопок.opacity = 0

    def _оновити_вивід(self, текст):
        """З потоку виконання: показати накопичений вивід, поки програма
        ще чекає натискань кнопок."""
        Clock.schedule_once(lambda dt: setattr(self.вивід, "text", текст), 0)

    def _рядок_вводу(self):
        """Поле вводу + «Далі» (для запитай) з необов'язковим написом над
        ним (назва застосунку, токен тощо). Висота 0 = сховано; з'являється
        лише поки програма чекає на відповідь. РядЩоХовається — щоб схований
        ряд не перехоплював дотики до низу полотна над ним."""
        self._ряд_вводу = РядЩоХовається(orientation="vertical", size_hint_y=None, height=0, spacing=dp(2))
        self._запит = Label(
            text="", size_hint_y=None, height=dp(22), halign="left", valign="middle",
            font_size=sp(14), color=(0.2, 0.45, 0.2, 1),
        )
        self._запит.bind(width=lambda і, ш: setattr(і, "text_size", (ш - dp(8), None)))
        ряд = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(44), spacing=dp(4))
        self._поле_вводу = TextInput(multiline=False, font_name=МОНО, font_size=sp(15))
        self._поле_вводу.bind(on_text_validate=self._надіслати)
        кнопка = Button(text="Далі", size_hint_x=None, width=dp(11) * 4 + dp(28))
        кнопка.bind(on_release=self._надіслати)
        ряд.add_widget(self._поле_вводу)
        ряд.add_widget(кнопка)
        self._ряд_вводу.add_widget(self._запит)
        self._ряд_вводу.add_widget(ряд)
        self._ряд_вводу.opacity = 0
        self._ряд_вводу.disabled = True
        return self._ряд_вводу

    # ---- ввід для «запитай» -------------------------------------------------

    def _питай(self, запит):
        """Викликається з потоку виконання: показати рядок вводу, дочекатись
        відповіді. Саме запитання вже у виводі (zapusk показує його через
        оновити_вивід), тож напису над полем немає. «Стоп» під час
        очікування перериває програму."""
        from yadro.vm import ВиконанняЗупинено

        self._відповідь = None
        self._чекаю_відповідь.clear()

        def відповісти(текст):
            self._відповідь = текст
            self._чекаю_відповідь.set()

        # коли на місці виводу полотно, запитання видно лише в написі над полем
        Clock.schedule_once(
            lambda dt: self._показати_ввід(запит, відповісти, напис=self._показано_полотно), 0)
        while not self._чекаю_відповідь.wait(0.1):
            if self._стоп_запитано:
                Clock.schedule_once(lambda dt: self._сховати_ввід(), 0)
                raise ВиконанняЗупинено()
        return self._відповідь if self._відповідь is not None else ""

    def _показати_ввід(self, запит, при_відповіді=None, напис=True):
        self._при_відповіді = при_відповіді
        self._запит.text = (запит.strip() or "Введи значення:") if напис else ""
        self._запит.height = dp(22) if напис else 0
        self._запит.opacity = 1 if напис else 0
        self._поле_вводу.text = ""
        self._ряд_вводу.height = self._запит.height + dp(44) + dp(2)
        self._ряд_вводу.opacity = 1
        self._ряд_вводу.disabled = False
        self._поле_вводу.focus = True
        if not напис:
            # запитання — останній рядок виводу: прокрутити до нього
            Clock.schedule_once(lambda dt: setattr(self._прокрутка_виводу, "scroll_y", 0), 0.1)

    def _сховати_ввід(self):
        self._ряд_вводу.height = 0
        self._ряд_вводу.opacity = 0
        self._ряд_вводу.disabled = True   # схований ряд не ловить дотиків
        self._поле_вводу.focus = False

    def _надіслати(self, *_):
        обробник = getattr(self, "_при_відповіді", None)
        if обробник is None:
            return
        текст = self._поле_вводу.text
        self._при_відповіді = None
        self._сховати_ввід()
        обробник(текст)

    def _панель_кнопок(self):
        """Верхні кнопки дій. Не один прокручуваний ряд (на телефоні в
        нього влазило лише 4 перші кнопки, решта ховалась за правим
        краєм), а StackLayout, що переносить кнопки на наступні рядки —
        усі видно одразу. Ліворуч — версія, щоб було зрозуміло, яка збірка."""
        self._кн_виконати = Button(text="Виконати", on_release=self._виконати)
        self._кн_стоп = Button(text="Стоп", on_release=self._стоп, disabled=True)
        кнопки = [
            self._кн_виконати,
            self._кн_стоп,
            Button(text="Очистити вивід", on_release=self._очистити),
            Button(text="Очистити код", on_release=self._очистити_код),
            Button(text="Знайти", on_release=self._знайти),
            Button(text="До рядка", on_release=self._до_рядка),
            Button(text="Проєкти", on_release=self._показати_проєкти),
            Button(text="Новий", on_release=self._новий_проєкт),
            Button(text="Зробити застосунок", on_release=self._зробити_застосунок),
            Button(text="Налаштування", on_release=self._налаштування),
            Button(text="Плата", on_release=self._плата),
            Button(text="Прошити агента", on_release=self._прошити_агента),
            Button(text="Довідка", on_release=self._довідка),
        ]
        панель = StackLayout(orientation="lr-tb", size_hint_y=None, spacing=(dp(4), dp(4)))
        панель.bind(minimum_height=панель.setter("height"))
        версія = Label(
            text=f"Вуж {ВЕРСІЯ}", size_hint=(None, None), height=dp(38), width=dp(74),
            font_size=sp(13), color=(0.45, 0.45, 0.5, 1),
        )
        панель.add_widget(версія)
        for к in кнопки:
            к.size_hint = (None, None)
            к.height = dp(38)
            к.width = dp(9) * len(к.text) + dp(22)
            к.font_size = sp(14)
            панель.add_widget(к)
        return панель

    def _панель_вставок(self):
        """Кнопки швидкого вводу — два горизонтально прокручувані ряди
        (один ряд ховав половину кнопок за правим краєм): зверху дужки й
        базові слова, знизу — блоки (поки/для/дія/тип/спробуй…)."""
        половина = (len(redaktor.КНОПКИ) + 1) // 2
        ряди = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(84), spacing=dp(2))
        for частина in (redaktor.КНОПКИ[:половина], redaktor.КНОПКИ[половина:]):
            кнопки = []
            for ключ in частина:
                кнопка = Button(
                    text=ключ, size_hint_x=None, font_size=sp(15),
                    width=max(dp(40), dp(11) * len(ключ) + dp(16)),
                )
                кнопка.bind(on_release=lambda к, кл=ключ: self._вставити(кл))
                кнопки.append(кнопка)
            ряди.add_widget(прокручуваний_ряд(кнопки, висота=dp(41)))
        return ряди

    # ---- редагування -------------------------------------------------------

    def _вставити(self, ключ):
        поле = self.код
        if поле.selection_text:
            поле.delete_selection()
        if ключ in redaktor.КАРКАСИ:
            вставка, поч, кін = redaktor.каркас(ключ, поле.text, поле.cursor_index())
            поле.insert_text(вставка)
        else:
            поле.insert_text(redaktor.ПРОСТІ_ВСТАВКИ[ключ])
            поч = кін = None
        # Дотик до кнопки знімає фокус із поля — повертаємо, щоб клавіатура
        # не ховалась; курсор/виділення ставимо вже після повернення фокусу.
        Clock.schedule_once(lambda dt: self._повернути_фокус(поч, кін), 0)

    def _повернути_фокус(self, поч=None, кін=None):
        поле = self.код
        поле.focus = True
        if поч is None:
            return

        def поставити(dt):
            поле.cursor = поле.get_cursor_from_index(кін)
            if поч != кін:
                поле.select_text(поч, кін)

        Clock.schedule_once(поставити, 0)

    def _при_зміні_тексту(self, _інст, текст):
        self._проєкти.чернетка(текст)
        self._сховати_пояснення()
        self._запланувати_перевірку()
        self._пошук.при_зміні_коду()

    # ---- пошук, заміна, перехід до рядка (panel_poshuku.py) ------------------

    def _знайти(self, *_):
        self._пошук.показати_пошук()

    def _до_рядка(self, *_):
        self._пошук.показати_рядок()

    # ---- помилки -----------------------------------------------------------

    def _запланувати_перевірку(self):
        if self._перевірка is not None:
            self._перевірка.cancel()
        self._перевірка = Clock.schedule_once(self._перевірити, ЗАТРИМКА_ПЕРЕВІРКИ)

    def _перевірити(self, *_):
        self._перевірка = None
        try:
            результат = redaktor.перевірити(self.код.text)
        except Exception:
            результат = None
        self._показати_помилку(результат)

    def _показати_помилку(self, помилка):
        """помилка — (рядок, пояснення) або None. Лише підкреслення;
        пояснення чекає на дотик до рядка."""
        self._помилка = помилка
        self.код.рядок_помилки = помилка[0] if помилка else 0

    def _при_дотику_до_рядка(self, номер):
        if self._помилка is not None and номер == self._помилка[0]:
            self.пояснення.text = f"Рядок {номер}. {self._помилка[1]}"
            self.пояснення.texture_update()
            self.пояснення.height = self.пояснення.texture_size[1] + dp(6)
        else:
            self._сховати_пояснення()

    def _сховати_пояснення(self):
        if self.пояснення.height:
            self.пояснення.text = ""
            self.пояснення.height = 0

    # ---- виконання ----------------------------------------------------------

    def _виконати(self, *_):
        """Запускає програму в окремому потоці, щоб інтерфейс не завмирав
        на довгих циклах і «спи», а кнопка «Стоп» лишалась живою."""
        if self._потік is not None and self._потік.is_alive():
            return
        self._зберегти_проєкт()
        self._вм = None
        self._вивід_очищено = False
        self._прибрати_кнопки_програми()
        self._прибрати_полотно()
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
            текст, успіх = виконати_код(
                код, при_старті=self._запамʼятати_вм, тека=self.user_data_dir,
                питай=self._питай, кнопка=self._додати_кнопку_програми,
                оновити_вивід=self._оновити_вивід,
                при_кресленні=self._при_кадрі, розмір_екрана=self._розмір_екрана,
                показувати_креслення=False,
            )
        except Exception:
            текст, успіх = "Внутрішня помилка:\n" + traceback.format_exc(), False
        if not текст.strip():
            текст = "(програма нічого не надрукувала)"
        # Kivy-віджети можна чіпати лише з головного потоку.
        Clock.schedule_once(lambda dt: self._показати_результат(текст, успіх), 0)

    def _запамʼятати_вм(self, вм):
        self._вм = вм
        # Якщо «Стоп» натиснули ще до того, як ВМ створилась, — не губимо.
        if self._стоп_запитано:
            вм.зупинено = True

    def _показати_результат(self, текст, успіх=True):
        self._сховати_ввід()
        self._прибрати_кнопки_програми()
        # «Очистити вивід» під час очікування кнопок завершує програму —
        # її прощальне «Виконання зупинено.» уже нікому не потрібне
        self.вивід.text = "" if self._вивід_очищено else текст
        self._вм = None
        self._потік = None
        self._стоп_був = self._стоп_запитано
        self._стоп_запитано = False
        self._кн_виконати.disabled = False
        self._кн_стоп.disabled = True
        if not успіх:
            # помилку треба побачити, а вона у виводі, не на полотні
            # («Стоп» — не помилка: полотно лишається)
            if self._показано_полотно and not self._стоп_був:
                self._показати_полотно(False)
            помилка = redaktor.помилка_з_виводу(текст)
            if помилка is not None:
                self._показати_помилку(помилка)
        Clock.schedule_once(lambda dt: setattr(self._прокрутка_виводу, "scroll_y", 1), 0)

    # ---- проєкти (proekty.py, vikno_proektiv.py) ---------------------------------

    def _почати_проєкт(self):
        """Текст для редактора при запуску застосунку: відкритий минулого
        разу проєкт (з чернеткою, якщо вона свіжіша). Якщо тека проєктів
        недоступна — редактор усе одно підніметься, з чернеткою."""
        try:
            текст = self._проєкти.почати()
        except Exception:
            текст = self._проєкти._прочитати_чернетку() or ПОЧАТКОВИЙ_КОД
        self._показати_назву_проєкту()
        return текст

    def _показати_назву_проєкту(self):
        назва = self._проєкти.поточний
        self._назва_проєкту.text = f"Проєкт: {назва}" if назва else "Проєкт не збережено"
        self.title = f"Вуж — {назва}" if назва else "Вуж"

    def _зберегти_проєкт(self):
        """Автозбереження відкритого проєкту: при «Виконати», при згортанні
        й закритті застосунку, перед показом списку проєктів."""
        код = getattr(self, "код", None)   # на крах-екрані редактора немає
        if код is not None:
            self._проєкти.зберегти(код.text)

    def on_pause(self):
        self._зберегти_проєкт()
        return True

    def on_stop(self):
        self._зберегти_проєкт()

    def _вікно_проєктів(self):
        self._зберегти_проєкт()
        return ВікноПроєктів(
            self._проєкти, при_відкритті=self._проєкт_відкрито,
            при_зміні=self._показати_назву_проєкту,
        )

    def _показати_проєкти(self, *_):
        вікно = self._вікно_проєктів()
        вікно.показати_список()
        вікно.open()

    def _новий_проєкт(self, *_):
        вікно = self._вікно_проєктів()
        вікно.показати_новий()
        вікно.open()

    def _проєкт_відкрито(self, текст):
        """Вікно проєктів змінило відкритий проєкт (відкрили інший,
        створили новий або видалили поточний) — показати його в редакторі."""
        self._прибрати_кнопки_програми()
        self.код.text = текст
        self.код.cursor = (0, 0)
        self._показати_назву_проєкту()
        self.вивід.text = f"Відкрито проєкт «{self._проєкти.поточний}»."

    # ---- «Зробити застосунок» і публікація ----------------------------------------

    def _корінь_репо(self):
        """Де лежить тека застосунки/: у репозиторії, якщо main.py запущено з
        нього (є .git), інакше — у теці застосунку на телефоні."""
        if (сюди / ".git").is_dir():
            return сюди
        return Path(self.user_data_dir)

    def _зробити_застосунок(self, *_):
        self._показати_ввід("Назва застосунку:", self._створити_застосунок)

    def _створити_застосунок(self, назва):
        try:
            файли = zastosunky.файли_застосунку(назва, self.код.text, ВЕРСІЯ)
            тека, імена = zastosunky.створити_застосунок(self._корінь_репо(), назва, self.код.text, ВЕРСІЯ)
        except zastosunky.ПомилкаЗастосунку as e:
            self.вивід.text = f"Не вийшло: {e}"
            return
        except Exception as e:
            self.вивід.text = f"Не вдалося записати застосунок: {e}"
            return
        текст = f"Застосунок «{zastosunky.безпечна_назва(назва)}» створено:\n{тека}\n  " + "\n  ".join(імена)
        налашт = github.прочитати_налаштування(self.user_data_dir)
        if not налашт["токен"]:
            self.вивід.text = текст + (
                "\n\nЩоб надіслати його в GitHub на збірку APK, задай токен у «Налаштування»."
            )
            return
        self.вивід.text = текст + f"\n\nНадсилаю в {налашт['репо']}…"
        шляхи = zastosunky.шляхи_для_публікації(назва, файли)
        повідомлення = f"Застосунок «{zastosunky.безпечна_назва(назва)}» (з редактора Вужа {ВЕРСІЯ})"
        threading.Thread(
            target=self._опублікувати_у_потоці, args=(налашт, шляхи, повідомлення, текст), daemon=True
        ).start()

    def _опублікувати_у_потоці(self, налашт, шляхи, повідомлення, текст):
        try:
            sha = github.опублікувати(налашт["токен"], налашт["репо"], шляхи, повідомлення, налашт["гілка"])
            результат = (
                f"{текст}\n\nОпубліковано в {налашт['репо']}: коміт {sha[:7]}. "
                "GitHub Actions збере APK — забери його в Artifacts запуску «Застосунки з програм»."
            )
        except github.ПомилкаПублікації as e:
            результат = f"{текст}\n\nНе опубліковано: {e}"
        except Exception as e:
            результат = f"{текст}\n\nНе опубліковано: {type(e).__name__}: {e}"
        Clock.schedule_once(lambda dt: setattr(self.вивід, "text", результат), 0)

    def _налаштування(self, *_):
        налашт = github.прочитати_налаштування(self.user_data_dir)
        self.вивід.text = (
            f"Вікно виводу: останні {int(self.вивід.межа)} рядків "
            f"(можна від {vyvid.МЕЖА_МІН} до {vyvid.МЕЖА_МАКС}).\n\n"
            "Налаштування публікації в GitHub:\n"
            f"  репозиторій: {налашт['репо']}\n"
            f"  гілка: {налашт['гілка']}\n"
            f"  токен: {github.замаскувати(налашт['токен'])}\n\n"
            "Введи новий токен (Personal Access Token з правом repo). "
            "Порожньо — лишити як є."
        )
        self._поле_вводу.password = True
        self._показати_ввід("Токен GitHub:", self._зберегти_токен)

    def _зберегти_токен(self, токен):
        self._поле_вводу.password = False
        if токен.strip():
            github.зберегти_налаштування(self.user_data_dir, токен=токен)
            self.вивід.text = "Токен збережено (у теці застосунку, не друкується)."
        else:
            self.вивід.text = "Токен не змінено."
        налашт = github.прочитати_налаштування(self.user_data_dir)
        self._показати_ввід(f"Репозиторій (зараз {налашт['репо']}), порожньо — лишити:", self._зберегти_репо)

    def _зберегти_репо(self, репо):
        if репо.strip():
            github.зберегти_налаштування(self.user_data_dir, репо=репо)
            self.вивід.text += f"\nРепозиторій: {репо.strip()}."
        self._показати_ввід(
            f"Рядків у вікні виводу (зараз {int(self.вивід.межа)}), порожньо — лишити:", self._зберегти_межу)

    def _зберегти_межу(self, текст):
        if текст.strip():
            межа = vyvid.межа_з_тексту(текст)
            if межа is None:
                self.вивід.text += f"\nРядків виводу: «{текст.strip()}» — не число, лишаю {int(self.вивід.межа)}."
            else:
                try:
                    vyvid.зберегти_межу(self.user_data_dir, межа)
                except Exception as e:
                    self.вивід.text += f"\nМежу не вдалося зберегти у файл: {e}"
                self.вивід.межа = межа
                self.вивід.text += f"\nРядків у вікні виводу: {межа}."
        self.вивід.text += "\nГотово. «Зробити застосунок» тепер надсилатиме програму в GitHub."

    # ---- плата (yadro/plata.py) ---------------------------------------------------

    def _плата(self, *_):
        """«Плата»: список знайдених плат (кнопки — підключитись), стан
        підключення, «Перевірити» (блимає вбудованим світлодіодом)."""
        from yadro import plata

        self._прибрати_кнопки_програми()
        self.вивід.text = "Шукаю плати…"

        def шукати():
            try:
                назви = plata.плати()
                стан = plata.підключено()
                помилка = None
            except Exception as e:
                назви, стан, помилка = [], None, str(e)
            Clock.schedule_once(lambda dt: показати(назви, стан, помилка), 0)

        def показати(назви, стан, помилка):
            рядки = ["Плати:"] + [f"  • {н}" for н in назви] if назви else ["Плат не знайдено."]
            if помилка:
                рядки.append(f"Помилка пошуку: {помилка}")
            рядки.append(f"Підключено: {стан or 'нічого'}")
            рядки.append("Торкнись назви внизу, щоб підключитись; «Перевірити» блимає світлодіодом.")
            self.вивід.text = "\n".join(рядки)
            for н in назви:
                self._додати_кнопку_програми(н, lambda н=н: threading.Thread(target=self._підключити_плату, args=(н,), daemon=True).start())
            self._додати_кнопку_програми("Перевірити", lambda: threading.Thread(target=self._перевірити_плату, daemon=True).start())
            self._додати_кнопку_програми("Відключитись", lambda: threading.Thread(target=self._відключити_плату, daemon=True).start())

        threading.Thread(target=шукати, daemon=True).start()

    def _повідомити(self, текст):
        Clock.schedule_once(lambda dt: setattr(self.вивід, "text", текст), 0)

    # ---- прошивання агента (yadro/proshyvka.py) -------------------------------------

    def _прошити_агента(self, *_):
        """«Прошити агента»: залити готовий agent_esp32.bin на ESP32 по USB
        без Arduino IDE. Файл — agent/agent_esp32/agent_esp32.bin у теці
        застосунку (репозиторії) або agent_esp32.bin у теці даних."""
        from yadro import proshyvka

        self._прибрати_кнопки_програми()
        файл = proshyvka.знайти_агента(сюди, self.user_data_dir)
        if файл is None:
            self.вивід.text = (
                "Готового agent_esp32.bin немає.\n"
                f"Поклади його як {proshyvka.ФАЙЛ_АГЕНТА} у репозиторій (потрапить у наступний APK)\n"
                f"або як agent_esp32.bin у теку застосунку: {self.user_data_dir}\n"
                "Як зібрати — README, розділ «Агент для ESP32: як зібрати .bin»."
            )
            return
        if plata_підключено_по_wifi():
            self.вивід.text = "Прошивати можна лише по USB-кабелю. Підключи плату кабелем."
            return
        self.вивід.text = f"Прошиваю {файл.name} ({файл.stat().st_size} байт) на USB-плату…"

        def прогрес(відсоток, текст):
            self._повідомити(f"Прошивка агента: {відсоток}% — {текст}")

        def у_потоці():
            старий = proshyvka.при_прогресі
            proshyvka.при_прогресі = прогрес
            try:
                from yadro import plata
                plata.відключись()          # звільнити USB для завантажувача
                з = proshyvka._сеанс("USB")
                try:
                    інфо = f"чип {з.чип}, MAC {з.mac()}"
                    з.записати(файл.read_bytes(), 0x0)
                    з.перезавантажити()
                finally:
                    з.порт.close()
                self._повідомити(f"Агент прошито ({інфо}). Плата перезавантажена — тепер «Плата» → «Перевірити».")
            except Exception as e:
                self._повідомити(f"Прошивка не вдалась: {e}")
            finally:
                proshyvka.при_прогресі = старий

        threading.Thread(target=у_потоці, daemon=True).start()

    def _підключити_плату(self, назва):
        from yadro import plata
        try:
            self._повідомити(f"Підключено: {plata.підключись(назва)}")
        except Exception as e:
            self._повідомити(f"Не підключено: {e}")

    def _перевірити_плату(self):
        from yadro import plata
        try:
            if plata.підключено() is None:
                plata.підключись("USB")
            plata.перевірити(3)
            self._повідомити(f"Плата «{plata.підключено()}» відповідає — світлодіод блимнув 3 рази.")
        except Exception as e:
            self._повідомити(f"Перевірка не вдалась: {e}")

    def _відключити_плату(self):
        from yadro import plata
        plata.відключись()
        self._повідомити("Плату відключено.")

    def _стоп(self, *_):
        self._стоп_запитано = True
        if self._вм is not None:
            self._вм.зупинено = True

    def _очистити(self, *_):
        self.вивід.text = ""
        if self._кнопки_програми.children:
            # кнопки живуть до «Очистити вивід»: прибираємо їх і завершуємо
            # програму, що на них чекала
            self._вивід_очищено = True
            self._прибрати_кнопки_програми()
            self._стоп()

    def _довідка(self, *_):
        self.вивід.text = dovidka.текст_довідки()
        Clock.schedule_once(lambda dt: setattr(self._прокрутка_виводу, "scroll_y", 1), 0)

    def _очистити_код(self, *_):
        self.код.text = ""
        Clock.schedule_once(lambda dt: self._повернути_фокус(), 0)


if __name__ == "__main__":
    ВужApp().run()
