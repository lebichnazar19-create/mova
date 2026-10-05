"""Панель пошуку, заміни й переходу до рядка в редакторі (main.py) —
смужка над полем коду, схована, доки не натиснуто «Знайти» чи «До рядка».
Kivy-only, на комп'ютері без дисплея не імпортується; уся робота з
текстом — у redaktor.py (без Kivy, з тестами).

Режими (вміст перебудовується на місці, панель та сама):
- пошук: поле «Знайти», лічильник («2 з 7», «немає»), «<» і «>» —
  попередній і наступний збіг по колу, «Аа» — розрізняти великі й малі
  літери, «×» — закрити; нижче — поле «Замінити на», «Замінити»
  (поточний збіг, далі — до наступного) і «Замінити всі»;
- рядок: поле номера, «Перейти», «×».

Від поля коду панелі потрібно: text, cursor_index(), focus,
показати_збіги(збіги, довжина, поточний) — підсвітити,
перейти(початок, кінець) — поставити курсор і прокрутити.
"""

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput

import redaktor

ВИСОТА_РЯДУ = dp(40)
ПРОМІЖОК = dp(2)
КОЛІР_УВІМКНЕНОЇ = (0.25, 0.55, 0.3, 1)
КОЛІР_ЗВИЧАЙНОЇ = (1, 1, 1, 1)


class ПанельПошуку(BoxLayout):
    def __init__(self, поле, шрифт=None, **kw):
        kw.setdefault("orientation", "vertical")
        kw.setdefault("size_hint_y", None)
        kw.setdefault("spacing", ПРОМІЖОК)
        super().__init__(**kw)
        self.поле = поле
        self.режим = None        # None (сховано), "пошук" або "рядок"
        self._збіги = []         # індекси початків збігів у тексті коду
        self._збіг = -1          # номер поточного збігу (з 0) або -1
        self._регістр = False
        self._заміняю = False    # панель сама міняє текст коду
        шрифт = {"font_name": шрифт} if шрифт else {}

        self._поле_пошуку = TextInput(
            multiline=False, hint_text="Знайти", font_size=sp(15),
            write_tab=False, text_validate_unfocus=False, **шрифт,
        )
        self._поле_пошуку.bind(text=self._шукати, on_text_validate=lambda *_: self._крок(1))
        self._лічильник = Label(text="", size_hint_x=None, width=dp(80), font_size=sp(12))
        self._кн_регістр = self._кнопка("Аа", self._перемкнути_регістр, dp(38))
        self._ряд_пошуку = self._ряд(
            self._поле_пошуку, self._лічильник,
            self._кнопка("<", lambda *_: self._крок(-1), dp(36)),
            self._кнопка(">", lambda *_: self._крок(1), dp(36)),
            self._кн_регістр,
            self._кнопка("×", self.сховати, dp(36)),
        )

        self._поле_заміни = TextInput(
            multiline=False, hint_text="Замінити на", font_size=sp(15),
            write_tab=False, text_validate_unfocus=False, **шрифт,
        )
        self._поле_заміни.bind(on_text_validate=self._замінити)
        self._ряд_заміни = self._ряд(
            self._поле_заміни,
            self._кнопка("Замінити", self._замінити),
            self._кнопка("Замінити всі", self._замінити_всі),
        )

        self._поле_рядка = TextInput(
            multiline=False, hint_text="Номер рядка", font_size=sp(15),
            write_tab=False, input_filter="int", input_type="number", **шрифт,
        )
        self._поле_рядка.bind(on_text_validate=self._перейти_до_рядка)
        self._напис_рядка = Label(text="", size_hint_x=None, width=dp(96), font_size=sp(12))
        self._ряд_рядка = self._ряд(
            self._поле_рядка, self._напис_рядка,
            self._кнопка("Перейти", self._перейти_до_рядка),
            self._кнопка("×", self.сховати, dp(36)),
        )
        self._показати_ряди()

    # ---- складання ---------------------------------------------------------

    def _кнопка(self, напис, дія, ширина=None):
        кнопка = Button(
            text=напис, size_hint_x=None, font_size=sp(14),
            width=ширина or dp(9) * len(напис) + dp(22),
        )
        кнопка.bind(on_release=дія)
        return кнопка

    def _ряд(self, *віджети):
        ряд = BoxLayout(orientation="horizontal", size_hint_y=None, height=ВИСОТА_РЯДУ, spacing=dp(4))
        for в in віджети:
            ряд.add_widget(в)
        return ряд

    def _показати_ряди(self, *ряди):
        """Вміст панелі; без рядів — панель схована (висота 0, дотиків не ловить)."""
        self.clear_widgets()
        for ряд in ряди:
            self.add_widget(ряд)
        self.height = len(ряди) * ВИСОТА_РЯДУ + max(len(ряди) - 1, 0) * ПРОМІЖОК
        self.opacity = 1 if ряди else 0
        self.disabled = not ряди

    def _фокус(self, віджет):
        # дотик до кнопки знімає фокус із поля, і клавіатура ховається —
        # повертаємо його вже після дотику
        Clock.schedule_once(lambda dt: setattr(віджет, "focus", True), 0)

    # ---- режими ------------------------------------------------------------

    def показати_пошук(self, *_):
        self.режим = "пошук"
        self._показати_ряди(self._ряд_пошуку, self._ряд_заміни)
        self._шукати()
        self._фокус(self._поле_пошуку)

    def показати_рядок(self, *_):
        self.режим = "рядок"
        self.поле.показати_збіги([], 0, -1)
        рядків = self.поле.text.count("\n") + 1
        self._поле_рядка.text = ""
        self._напис_рядка.text = f"від 1 до {рядків}"
        self._показати_ряди(self._ряд_рядка)
        self._фокус(self._поле_рядка)

    def сховати(self, *_):
        """Закрити панель: підсвітка зникає, курсор лишається там, де був
        (на поточному збігу), клавіатура переходить до поля коду."""
        if self.режим is None:
            return
        self.режим = None
        self._збіги, self._збіг = [], -1
        self.поле.показати_збіги([], 0, -1)
        self._показати_ряди()
        self._фокус(self.поле)

    # ---- пошук -------------------------------------------------------------

    def _знайти(self, від):
        """Перерахувати збіги; поточним стає перший від індексу «від»."""
        self._збіги = redaktor.знайти_збіги(self.поле.text, self._поле_пошуку.text, self._регістр)
        self._збіг = redaktor.найближчий_збіг(self._збіги, від)

    def _оновити(self, прокрутити):
        шукане = self._поле_пошуку.text
        self._лічильник.text = redaktor.напис_збігів(шукане, self._збіг, len(self._збіги))
        self.поле.показати_збіги(self._збіги, len(шукане), self._збіг)
        if прокрутити and self._збіг >= 0:
            початок = self._збіги[self._збіг]
            self.поле.перейти(початок, початок + len(шукане))

    def _шукати(self, *_):
        self._знайти(self.поле.cursor_index())
        self._оновити(True)

    def при_зміні_коду(self):
        """Текст у полі коду змінився (набір, інший проєкт): збіги
        рахуються наново, але поле нікуди не прокручується."""
        if self.режим != "пошук" or self._заміняю:
            return
        self._знайти(self.поле.cursor_index())
        self._оновити(False)

    def _крок(self, крок):
        self._збіг = redaktor.сусідній_збіг(self._збіг, len(self._збіги), крок)
        self._оновити(True)
        self._фокус(self._поле_пошуку)

    def _перемкнути_регістр(self, *_):
        self._регістр = not self._регістр
        self._кн_регістр.background_color = КОЛІР_УВІМКНЕНОЇ if self._регістр else КОЛІР_ЗВИЧАЙНОЇ
        self._шукати()
        self._фокус(self._поле_пошуку)

    # ---- заміна ------------------------------------------------------------

    def _поставити_текст(self, текст):
        self._заміняю = True
        try:
            self.поле.text = текст
        finally:
            self._заміняю = False

    def _замінити(self, *_):
        """Замінити поточний збіг і перейти до наступного."""
        if self._збіг < 0:
            return
        шукане = self._поле_пошуку.text
        текст, далі = redaktor.замінити_збіг(
            self.поле.text, self._збіги[self._збіг], len(шукане), self._поле_заміни.text)
        self._поставити_текст(текст)
        self._знайти(далі)
        if self._збіг < 0:
            self.поле.перейти(далі)   # новий текст поставив курсор у кінець
        self._оновити(True)
        self._фокус(self._поле_заміни)

    def _замінити_всі(self, *_):
        шукане = self._поле_пошуку.text
        текст, кількість = redaktor.замінити_всі(
            self.поле.text, шукане, self._поле_заміни.text, self._регістр)
        if кількість:
            початок = self._збіги[0] if self._збіги else 0
            self._поставити_текст(текст)
            self.поле.перейти(початок)   # до першої заміни
            self._знайти(початок)
            self._оновити(False)
        if шукане:
            self._лічильник.text = f"замінено {кількість}"
        self._фокус(self._поле_заміни)

    # ---- перехід до рядка --------------------------------------------------

    def _перейти_до_рядка(self, *_):
        текст = self.поле.text
        номер = redaktor.номер_рядка(self._поле_рядка.text, текст.count("\n") + 1)
        if номер is None:
            self._напис_рядка.text = "введи число"
            self._фокус(self._поле_рядка)
            return
        self.поле.перейти(redaktor.початок_рядка(текст, номер))
        self.сховати()
