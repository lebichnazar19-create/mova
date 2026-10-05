"""Вікно «Проєкти» редактора (main.py): список збережених програм поверх
редактора. Kivy-only, на комп'ютері без дисплея не імпортується; уся
робота з файлами — в proekty.py (без Kivy, з тестами).

Екрани вікна (вміст перебудовується на місці, вікно те саме):
- список: дотик до назви відкриває проєкт, довгий дотик — дії з ним;
  поле пошуку з'являється, коли проєктів більше десяти; знизу «Новий» і
  «Закрити»;
- дії: «Відкрити», «Перейменувати», «Зробити копію», «Видалити», «Назад»;
- назва: поле вводу для нового проєкту чи перейменування — помилка
  (порожня назва, така вже є) показується тут же, поле лишається;
- підтвердження видалення: «Так, видалити» / «Ні».
"""

from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from proekty import ПомилкаПроєкту

ДОВГИЙ_ДОТИК = 0.5      # с — скільки тримати палець на назві
ЗСУВ_ПАЛЬЦЯ = dp(12)    # далі — це вже гортання списку, не довгий дотик
ВИСОТА_КНОПКИ = dp(46)

КОЛІР_ПОТОЧНОГО = (0.25, 0.55, 0.3, 1)
КОЛІР_НЕБЕЗПЕЧНОЇ = (0.75, 0.2, 0.2, 1)
КОЛІР_ПОМИЛКИ = (1, 0.55, 0.5, 1)
КОЛІР_ПІДКАЗКИ = (0.75, 0.75, 0.8, 1)


class КнопкаПроєкту(Button):
    """Рядок списку: короткий дотик — при_дотику(), утриманий палець —
    при_довгому() (тоді відпускання вже нічого не робить)."""

    def __init__(self, при_дотику, при_довгому, **kw):
        super().__init__(**kw)
        self._при_дотику = при_дотику
        self._при_довгому = при_довгому
        self._таймер = None
        self._початок = None
        self._довгий_спрацював = False

    def _скасувати_таймер(self):
        if self._таймер is not None:
            self._таймер.cancel()
            self._таймер = None

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self._довгий_спрацював = False
            self._початок = touch.pos
            self._скасувати_таймер()
            self._таймер = Clock.schedule_once(self._довгий_дотик, ДОВГИЙ_ДОТИК)
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._таймер is not None and self._початок is not None:
            if abs(touch.x - self._початок[0]) > ЗСУВ_ПАЛЬЦЯ or abs(touch.y - self._початок[1]) > ЗСУВ_ПАЛЬЦЯ:
                self._скасувати_таймер()
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        self._скасувати_таймер()
        return super().on_touch_up(touch)

    def _довгий_дотик(self, dt):
        self._таймер = None
        self._довгий_спрацював = True
        self._при_довгому()

    def on_release(self):
        if not self._довгий_спрацював:
            self._при_дотику()


def _напис(текст, розмір=15, колір=(1, 1, 1, 1), висота=None):
    """Label, що переносить рядки по ширині й сам росте у висоту (або
    має сталу висоту)."""
    мітка = Label(
        text=текст, size_hint_y=None, halign="left", valign="middle",
        font_size=sp(розмір), color=колір,
    )
    мітка.bind(width=lambda і, ш: setattr(і, "text_size", (ш - dp(8), None)))
    if висота is None:
        мітка.height = dp(8)   # порожній напис місця не займає
        мітка.bind(texture_size=lambda і, р: setattr(і, "height", р[1] + dp(8)))
    else:
        мітка.height = висота
    return мітка


def _кнопка(текст, натиснути, **kw):
    кнопка = Button(text=текст, size_hint_y=None, height=ВИСОТА_КНОПКИ, font_size=sp(15), **kw)
    кнопка.bind(on_release=lambda к: натиснути())
    return кнопка


class ВікноПроєктів(ModalView):
    """проєкти — proekty.Проєкти; при_відкритті(текст) — редактор має
    показати текст відкритого проєкту (проєкти.поточний уже новий);
    при_зміні() — назва відкритого проєкту могла змінитись (перейменування)."""

    def __init__(self, проєкти, при_відкритті, при_зміні, **kw):
        super().__init__(size_hint=(0.94, 0.94), **kw)
        self.проєкти = проєкти
        self._при_відкритті = при_відкритті
        self._при_зміні = при_зміні
        self._тіло = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6))
        self.add_widget(self._тіло)
        self._ряди = None        # BoxLayout з кнопками проєктів (екран списку)

    def _новий_екран(self, заголовок):
        self._тіло.clear_widgets()
        self._ряди = None
        self._тіло.add_widget(_напис(заголовок, розмір=18))

    # ---- список ---------------------------------------------------------------

    def показати_список(self, повідомлення=""):
        self._новий_екран("Проєкти")
        self._тіло.add_widget(_напис(
            "Дотик — відкрити. Довгий дотик — перейменувати, зробити копію або видалити.",
            розмір=13, колір=КОЛІР_ПІДКАЗКИ,
        ))
        if self.проєкти.потрібен_пошук():
            пошук = TextInput(
                multiline=False, hint_text="Пошук за назвою", size_hint_y=None,
                height=dp(44), font_size=sp(15),
            )
            пошук.bind(text=lambda і, текст: self._заповнити(текст))
            self._тіло.add_widget(пошук)
        self._ряди = BoxLayout(orientation="vertical", size_hint_y=None, spacing=dp(4))
        self._ряди.bind(minimum_height=self._ряди.setter("height"))
        прокрутка = ScrollView(do_scroll_x=False, bar_width=dp(4))
        прокрутка.add_widget(self._ряди)
        self._тіло.add_widget(прокрутка)
        if повідомлення:
            self._тіло.add_widget(_напис(повідомлення, розмір=13, колір=КОЛІР_ПІДКАЗКИ))
        низ = BoxLayout(orientation="horizontal", size_hint_y=None, height=ВИСОТА_КНОПКИ, spacing=dp(6))
        низ.add_widget(_кнопка("Новий", self.показати_новий))
        низ.add_widget(_кнопка("Закрити", self.dismiss))
        self._тіло.add_widget(низ)
        self._заповнити("")

    def _заповнити(self, запит):
        if self._ряди is None:
            return
        self._ряди.clear_widgets()
        назви = self.проєкти.список(запит)
        if not назви:
            self._ряди.add_widget(_напис(
                "Нічого не знайдено." if запит.strip() else "Проєктів ще немає — натисни «Новий».",
                колір=КОЛІР_ПІДКАЗКИ,
            ))
            return
        for назва in назви:
            поточний = назва == self.проєкти.поточний
            кнопка = КнопкаПроєкту(
                при_дотику=lambda н=назва: self._відкрити(н),
                при_довгому=lambda н=назва: self.показати_дії(н),
                text=f"{назва}  (відкрито)" if поточний else назва,
                size_hint_y=None, height=ВИСОТА_КНОПКИ, font_size=sp(15),
                halign="left", valign="middle", shorten=True, shorten_from="right",
                padding=(dp(12), 0),
            )
            кнопка.bind(size=lambda і, р: setattr(і, "text_size", р))
            if поточний:
                кнопка.background_color = КОЛІР_ПОТОЧНОГО
            self._ряди.add_widget(кнопка)

    def _відкрити(self, назва):
        try:
            текст = self.проєкти.відкрити(назва)
        except (ПомилкаПроєкту, OSError) as e:
            self.показати_список(str(e))
            return
        self.dismiss()
        self._при_відкритті(текст)

    # ---- дії з проєктом -----------------------------------------------------------

    def показати_дії(self, назва):
        self._новий_екран(f"Проєкт «{назва}»")
        self._тіло.add_widget(_кнопка("Відкрити", lambda: self._відкрити(назва)))
        self._тіло.add_widget(_кнопка("Перейменувати", lambda: self.показати_перейменування(назва)))
        self._тіло.add_widget(_кнопка("Зробити копію", lambda: self._копія(назва)))
        self._тіло.add_widget(_кнопка(
            "Видалити", lambda: self.показати_підтвердження(назва), background_color=КОЛІР_НЕБЕЗПЕЧНОЇ))
        self._тіло.add_widget(BoxLayout())   # розпірка: кнопки вгорі, «Назад» унизу
        self._тіло.add_widget(_кнопка("Назад", self.показати_список))

    def _копія(self, назва):
        try:
            нова = self.проєкти.копія(назва)
        except (ПомилкаПроєкту, OSError) as e:
            self.показати_список(str(e))
            return
        self.показати_список(f"Зроблено копію: «{нова}».")

    # ---- назва: новий проєкт і перейменування ---------------------------------------

    def показати_новий(self):
        def створити(назва):
            self.проєкти.новий(назва)
            self.dismiss()
            self._при_відкритті("")

        self._показати_назву("Новий проєкт", "Назва нового проєкту:", "", "Створити", створити)

    def показати_перейменування(self, стара):
        def перейменувати(нова):
            нова_назва = self.проєкти.перейменувати(стара, нова)
            self._при_зміні()
            self.показати_список(f"«{стара}» тепер «{нова_назва}».")

        self._показати_назву(f"Проєкт «{стара}»", "Нова назва:", стара, "Перейменувати", перейменувати)

    def _показати_назву(self, заголовок, запит, початкова, напис_кнопки, виконати):
        self._новий_екран(заголовок)
        self._тіло.add_widget(_напис(запит, колір=КОЛІР_ПІДКАЗКИ))
        поле = TextInput(
            text=початкова, multiline=False, size_hint_y=None, height=dp(44), font_size=sp(16),
        )
        помилка = _напис("", розмір=13, колір=КОЛІР_ПОМИЛКИ)

        def готово(*_):
            try:
                виконати(поле.text)
            except ПомилкаПроєкту as e:
                помилка.text = str(e)
                Clock.schedule_once(lambda dt: setattr(поле, "focus", True), 0)
            except OSError as e:
                помилка.text = f"Не вдалося записати: {e}"

        поле.bind(on_text_validate=готово)
        self._тіло.add_widget(поле)
        self._тіло.add_widget(помилка)
        ряд = BoxLayout(orientation="horizontal", size_hint_y=None, height=ВИСОТА_КНОПКИ, spacing=dp(6))
        ряд.add_widget(_кнопка(напис_кнопки, готово))
        ряд.add_widget(_кнопка("Скасувати", self.показати_список))
        self._тіло.add_widget(ряд)
        self._тіло.add_widget(BoxLayout())   # розпірка: поле вгорі, над клавіатурою
        Clock.schedule_once(lambda dt: setattr(поле, "focus", True), 0.1)

    # ---- видалення з підтвердженням ---------------------------------------------------

    def показати_підтвердження(self, назва):
        self._новий_екран(f"Видалити проєкт «{назва}»?")
        self._тіло.add_widget(_напис(
            "Програму буде стерто з телефона назавжди — повернути її не вийде.",
            колір=КОЛІР_ПІДКАЗКИ,
        ))
        self._тіло.add_widget(_кнопка(
            "Так, видалити", lambda: self._видалити(назва), background_color=КОЛІР_НЕБЕЗПЕЧНОЇ))
        self._тіло.add_widget(_кнопка("Ні", self.показати_список))
        self._тіло.add_widget(BoxLayout())

    def _видалити(self, назва):
        try:
            текст = self.проєкти.видалити(назва)
        except (ПомилкаПроєкту, OSError) as e:
            self.показати_список(str(e))
            return
        if текст is not None:
            # видалили відкритий проєкт — редактор показує той, що став відкритим
            self._при_відкритті(текст)
        self.показати_список(f"Проєкт «{назва}» видалено.")
