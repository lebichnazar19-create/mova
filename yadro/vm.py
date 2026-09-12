"""Стекова віртуальна машина. Виконує байткод, нічого не знає про синтаксис
мови — лише про інструкції з розділу 5 ТЗ (плюс MAKE_FUNCTION/MAKE_LIST/
INDEX_GET/INDEX_SET, потрібні для дій і списків).

VM отримує вже готовий байткод (dict з ключами "константи", "код",
опційно "позиції") і виконує його. Про природу помилки (тип, повідомлення)
дбає сама VM; текст рядка джерела для гарного виводу з «^» додає викликач
(yadro/мова.py), бо лише він тримає оригінальний текст програми.
"""

import time

from . import ekran, sketch, drafting, drawing, prystriy, rozum
from .natives import (
    ПРИСТРІЙ as _ІМЕНА_ПРИСТРІЙ,
    РОЗУМ as _ІМЕНА_РОЗУМ,
    МАЛЮНОК as _ІМЕНА_МАЛЮНОК,
    ЕКРАН as _ІМЕНА_ЕКРАН,
    КРЕСЛЕННЯ as _ІМЕНА_КРЕСЛЕННЯ,
    ЕСКІЗ as _ІМЕНА_ЕСКІЗ,
)
from .errors import ПомилкаВиконання

ГЛИБИНА_ВИКЛИКІВ_МАКС = 500


def _є_число(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _є_список(x):
    return isinstance(x, list)


def до_рядка(x):
    """Як значення мови показуються текстом (друкуй, конкатенація рядків)."""
    if x is None:
        return "ніщо"
    if x is True:
        return "істина"
    if x is False:
        return "хиба"
    if isinstance(x, list):
        return "[" + ", ".join(до_рядка(е) for е in x) + "]"
    if isinstance(x, dict):
        return "{" + ", ".join(f"{до_рядка(к)}: {до_рядка(в)}" for к, в in x.items()) + "}"
    return str(x)


def _тип_укр(x):
    if x is None:
        return "ніщо"
    if isinstance(x, bool):
        return "логічне значення"
    if isinstance(x, (int, float)):
        return "число"
    if isinstance(x, str):
        return "рядок"
    if isinstance(x, list):
        return "список"
    if isinstance(x, dict):
        return "словник"
    return type(x).__name__


class ВМ:
    def __init__(self, без_пристрою=False):
        self.глобальні = {}
        self.функції = {}
        self.стек = []
        self.кадри = []            # стек словників локальних змінних
        self.стек_повернень = []   # адреси повернення, паралельно self.кадри
        self.pc = 0
        self.код = []
        self.константи = []
        self.позиції = []

        if без_пристрою:
            prystriy.увімкнути_симуляцію(True)
            rozum.увімкнути_симуляцію(True)

        self._native = {
            "друкуй": self._друкуй,
            "питай": self._питай,
            "спи": self._спи,
            "довжина": self._довжина,
            "рядок": до_рядка,
            "число": self._число,
            "цілий": self._цілий,
            "діапазон": self._діапазон,
            "додай": self._додай,
            "вилучи": self._вилучи,
            "сортуй": self._сортуй,
        }
        for ім_я in _ІМЕНА_ПРИСТРІЙ:
            self._native[ім_я] = getattr(prystriy, ім_я)
        for ім_я in _ІМЕНА_РОЗУМ:
            self._native[ім_я] = getattr(rozum, ім_я)
        for ім_я in _ІМЕНА_МАЛЮНОК:
            if ім_я == "покажи":
                continue  # об'єднується з drafting.покажи() нижче, за активним режимом
            self._native[ім_я] = getattr(drawing, ім_я)
        for ім_я in _ІМЕНА_ЕКРАН:
            self._native[ім_я] = getattr(ekran, ім_я)
        for ім_я in _ІМЕНА_КРЕСЛЕННЯ:
            if ім_я == "покажи":
                continue
            self._native[ім_я] = getattr(drafting, ім_я)
        for ім_я in _ІМЕНА_ЕСКІЗ:
            if ім_я == "довжина":
                continue  # об'єднується з мовним довжина() нижче, за арністю
            self._native[ім_я] = getattr(sketch, ім_я)

        # "покажи": drawing.py і drafting.py обидва описують «завершити й
        # показати малюнок» (див. докстрінг yadro/drafting.py) — реальний
        # режим визначається за тим, який з двох станів насправді
        # ініціалізований (полотно(...) чи аркуш(...)), а не порядком
        # реєстрації, інакше один із режимів був би назавжди недосяжним
        def _покажи_обʼєднане():
            if drafting._аркуш is not None:
                return drafting.покажи()
            if drawing._полотно is not None:
                return drawing.покажи()
            raise ПомилкаВиконання(
                "Спершу виклич полотно(ширина, висота) (малювання) або "
                "аркуш(ширина, висота, масштаб) (креслення) — перед покажи()."
            )

        self._native["покажи"] = _покажи_обʼєднане

        # "довжина": мовна версія (1 аргумент — список/рядок) і ескізна
        # (2 аргументи — сегмент, значення) мирно співіснують під одним
        # іменем, розрізняючись кількістю аргументів виклику
        _довжина_мовна = self._native["довжина"]
        _довжина_ескіз = sketch.довжина

        def _довжина_обʼєднана(*args):
            if len(args) == 1:
                return _довжина_мовна(*args)
            if len(args) == 2:
                return _довжина_ескіз(*args)
            raise ПомилкаВиконання("Функція «довжина» приймає 1 або 2 аргументи.")

        self._native["довжина"] = _довжина_обʼєднана

    # ---- вбудовані мовні функції ------------------------------------------

    def _друкуй(self, *args):
        print(" ".join(до_рядка(а) for а in args))
        return None

    def _питай(self, *args):
        if args:
            print(до_рядка(args[0]), end="", flush=True)
        try:
            return input()
        except EOFError:
            raise ПомилкаВиконання("«питай» не отримав вводу (немає доступного stdin).")

    def _спи(self, сек):
        if not _є_число(сек):
            raise ПомилкаВиконання("Функція «спи» очікує число секунд.")
        time.sleep(сек)
        return None

    def _довжина(self, x):
        if isinstance(x, (list, str, dict)):
            return len(x)
        raise ПомилкаВиконання(f"Функція «довжина» не працює для типу «{_тип_укр(x)}».")

    def _число(self, x):
        if _є_число(x):
            return x
        if isinstance(x, str):
            try:
                if "." in x:
                    return float(x)
                return int(x)
            except ValueError:
                raise ПомилкаВиконання(f"Не вдалося перетворити рядок «{x}» на число.")
        raise ПомилкаВиконання(f"Не вдалося перетворити {_тип_укр(x)} на число.")

    def _цілий(self, x):
        return int(self._число(x))

    def _діапазон(self, *args):
        if len(args) == 1:
            return list(range(int(args[0])))
        if len(args) == 2:
            return list(range(int(args[0]), int(args[1])))
        if len(args) == 3:
            return list(range(int(args[0]), int(args[1]), int(args[2])))
        raise ПомилкаВиконання("Функція «діапазон» приймає від 1 до 3 аргументів.")

    def _додай(self, список, значення):
        if not isinstance(список, list):
            raise ПомилкаВиконання(f"Функція «додай» очікує список, отримала {_тип_укр(список)}.")
        список.append(значення)
        return None

    def _вилучи(self, список, idx):
        if not isinstance(список, list):
            raise ПомилкаВиконання(f"Функція «вилучи» очікує список, отримала {_тип_укр(список)}.")
        if not isinstance(idx, int) or isinstance(idx, bool):
            raise ПомилкаВиконання("Індекс для «вилучи» має бути цілим числом.")
        i = self._норм_індекс(idx, len(список))
        if i is None:
            raise ПомилкаВиконання(f"Індекс {idx} поза межами (довжина {len(список)}).")
        return список.pop(i)

    def _сортуй(self, список):
        if not isinstance(список, list):
            raise ПомилкаВиконання(f"Функція «сортуй» очікує список, отримала {_тип_укр(список)}.")
        try:
            список.sort()
        except TypeError:
            raise ПомилкаВиконання(
                "Функцію «сортуй» можна застосувати лише до однорідного списку "
                "(усі елементи — числа, або усі — рядки)."
            )
        return None

    # ---- допоміжне -----------------------------------------------------------

    def _поточна_позиція(self):
        """(рядок, колонка, текст_рядка). Позиції старого формату (2 елементи,
        напр. з .байт-файлу, скомпільованого до підтримки «підключи») теж
        підтримуються — текст_рядка тоді просто порожній."""
        if 0 <= self.pc < len(self.позиції):
            поз = self.позиції[self.pc]
            рядок = поз[0] if len(поз) > 0 else 0
            кол = поз[1] if len(поз) > 1 else 0
            текст = поз[2] if len(поз) > 2 else ""
            return (рядок, кол, текст)
        return (0, 0, "")

    def _помилка(self, повідомлення):
        рядок, кол, текст = self._поточна_позиція()
        raise ПомилкаВиконання(повідомлення, рядок, кол, текст)

    def _push(self, значення):
        self.стек.append(значення)

    def _pop(self):
        if not self.стек:
            self._помилка("Внутрішня помилка VM: стек порожній.")
        return self.стек.pop()

    def _push_var(self, імя):
        if self.кадри:
            локальні = self.кадри[-1]
            if імя in локальні:
                return локальні[імя]
        if імя in self.глобальні:
            return self.глобальні[імя]
        self._помилка(f"Невідома змінна «{імя}».")

    def _store_var(self, імя, значення):
        if self.кадри:
            self.кадри[-1][імя] = значення
        else:
            self.глобальні[імя] = значення

    # ---- запуск --------------------------------------------------------------

    def виконати(self, байткод):
        """Виконати самостійну програму «з нуля» — скидає весь стан VM."""
        self.код = байткод["код"]
        self.константи = байткод.get("константи", [])
        self.позиції = байткод.get("позиції", [])
        self.pc = 0
        self.стек = []
        self.кадри = []
        self.стек_повернень = []
        self._цикл_виконання()

    def виконати_фрагмент(self, байткод):
        """Додати ще один шматок байткоду до вже наявного (з переадресацією
        стрибків/констант) і виконати лише його — не чіпаючи self.глобальні
        й self.функції. Потрібно для REPL: кожен введений рядок компілюється
        окремо, але змінні й дії мають жити між рядками сеансу."""
        зсув_коду = len(self.код)
        зсув_конст = len(self.константи)

        новий_код = []
        for опкод, аргумент in байткод["код"]:
            if опкод in ("JUMP", "JUMP_FALSE"):
                аргумент = аргумент + зсув_коду
            elif опкод == "MAKE_FUNCTION":
                імя, параметри, адреса = аргумент
                аргумент = [імя, параметри, адреса + зсув_коду]
            elif опкод == "PUSH_CONST":
                аргумент = аргумент + зсув_конст
            новий_код.append([опкод, аргумент])

        self.код.extend(новий_код)
        self.константи.extend(байткод.get("константи", []))
        позиції = байткод.get("позиції") or [[0, 0, ""]] * len(новий_код)
        self.позиції.extend(позиції)

        self.pc = зсув_коду
        self._цикл_виконання()

    def _цикл_виконання(self):
        довжина_коду = len(self.код)
        while self.pc < довжина_коду:
            опкод, аргумент = self.код[self.pc]
            if опкод == "HALT":
                return
            try:
                self._виконати_інструкцію(опкод, аргумент)
            except ПомилкаВиконання as e:
                if not e.рядок:
                    рядок, кол, текст = self._поточна_позиція()
                    e.рядок, e.позиція = рядок, кол
                    if not e.текст_рядка:
                        e.текст_рядка = текст
                raise
            except (ZeroDivisionError, IndexError, KeyError, ValueError, TypeError) as e:
                рядок, кол, текст = self._поточна_позиція()
                raise ПомилкаВиконання(f"Помилка під час виконання: {e}", рядок, кол, текст) from e

    def _виконати_інструкцію(self, опкод, аргумент):
        # більшість інструкцій просто переходять до наступної; переходи й
        # виклики самі виставляють self.pc і повертаються через return
        if опкод == "PUSH_CONST":
            self._push(self.константи[аргумент])
        elif опкод == "PUSH_VAR":
            self._push(self._push_var(аргумент))
        elif опкод == "STORE_VAR":
            self._store_var(аргумент, self._pop())
        elif опкод == "POP":
            self._pop()

        elif опкод == "ADD":
            self._push(self._додати(self._pop2()))
        elif опкод == "SUB":
            a, b = self._pop2()
            self._числа(a, b, "відняти")
            self._push(a - b)
        elif опкод == "MUL":
            a, b = self._pop2()
            self._числа(a, b, "помножити")
            self._push(a * b)
        elif опкод == "DIV":
            a, b = self._pop2()
            self._числа(a, b, "поділити")
            if b == 0:
                self._помилка("Ділення на нуль.")
            r = a / b
            if isinstance(a, int) and isinstance(b, int) and r == int(r):
                r = int(r)
            self._push(r)
        elif опкод == "MOD":
            a, b = self._pop2()
            self._числа(a, b, "знайти остачу від ділення")
            if b == 0:
                self._помилка("Ділення на нуль (остача).")
            self._push(a % b)
        elif опкод == "NEG":
            x = self._pop()
            if not _є_число(x):
                self._помилка(f"Не можна застосувати унарний мінус до {_тип_укр(x)}.")
            self._push(-x)

        elif опкод == "EQ":
            a, b = self._pop2()
            self._push(a == b)
        elif опкод == "NEQ":
            a, b = self._pop2()
            self._push(a != b)
        elif опкод in ("LT", "GT", "LTE", "GTE"):
            a, b = self._pop2()
            self._push(self._порівняти(опкод, a, b))

        elif опкод == "AND":
            a, b = self._pop2()
            self._push(bool(a) and bool(b))
        elif опкод == "OR":
            a, b = self._pop2()
            self._push(bool(a) or bool(b))
        elif опкод == "NOT":
            self._push(not bool(self._pop()))

        elif опкод == "JUMP":
            self.pc = аргумент
            return
        elif опкод == "JUMP_FALSE":
            умова = self._pop()
            if not bool(умова):
                self.pc = аргумент
                return

        elif опкод == "MAKE_LIST":
            n = аргумент
            елементи = [self._pop() for _ in range(n)]
            елементи.reverse()
            self._push(елементи)
        elif опкод == "INDEX_GET":
            idx = self._pop()
            колекція = self._pop()
            self._push(self._індекс_get(колекція, idx))
        elif опкод == "INDEX_SET":
            значення = self._pop()
            idx = self._pop()
            колекція = self._pop()
            self._індекс_set(колекція, idx, значення)
        elif опкод == "SLICE_GET":
            кінець = self._pop()
            початок = self._pop()
            колекція = self._pop()
            self._push(self._зріз_get(колекція, початок, кінець))

        elif опкод == "MAKE_FUNCTION":
            імя, параметри, адреса = аргумент
            self.функції[імя] = {"параметри": параметри, "адреса": адреса}
        elif опкод == "CALL":
            self._виклик_дії(аргумент)
            return
        elif опкод == "RETURN":
            значення = self._pop()
            if not self.стек_повернень:
                self._помилка("«поверни» без активного виклику дії.")
            self.pc = self.стек_повернень.pop()
            self.кадри.pop()
            self._push(значення)
            return
        elif опкод == "CALL_NATIVE":
            self._виклик_native(аргумент)

        else:
            self._помилка(f"Невідомий опкод «{опкод}».")

        self.pc += 1

    # ---- арифметика / порівняння -----------------------------------------------

    def _pop2(self):
        b = self._pop()
        a = self._pop()
        return a, b

    def _додати(self, пара):
        a, b = пара
        if isinstance(a, str) or isinstance(b, str):
            return до_рядка(a) + до_рядка(b)
        if _є_список(a) and _є_список(b):
            return a + b
        if _є_число(a) and _є_число(b):
            return a + b
        self._помилка(f"Не можна скласти {_тип_укр(a)} і {_тип_укр(b)}.")

    def _числа(self, a, b, дія):
        if not (_є_число(a) and _є_число(b)):
            self._помилка(f"Не можна {дія} {_тип_укр(a)} і {_тип_укр(b)} — потрібні числа.")
        return True

    def _порівняти(self, опкод, a, b):
        if _є_число(a) and _є_число(b):
            pass
        elif isinstance(a, str) and isinstance(b, str):
            pass
        else:
            self._помилка(f"Не можна порівняти {_тип_укр(a)} і {_тип_укр(b)}.")
        if опкод == "LT":
            return a < b
        if опкод == "GT":
            return a > b
        if опкод == "LTE":
            return a <= b
        return a >= b  # GTE

    # ---- списки -------------------------------------------------------------

    def _норм_індекс(self, idx, n):
        """Від'ємний індекс рахується з кінця (як у Python): -1 — останній
        елемент. Повертає вже приведений до [0, n) індекс або None, якщо
        поза межами навіть після приведення."""
        i = idx + n if idx < 0 else idx
        if i < 0 or i >= n:
            return None
        return i

    def _індекс_get(self, колекція, idx):
        if isinstance(колекція, (list, str)):
            if not isinstance(idx, int) or isinstance(idx, bool):
                self._помилка("Індекс має бути цілим числом.")
            i = self._норм_індекс(idx, len(колекція))
            if i is None:
                self._помилка(f"Індекс {idx} поза межами (довжина {len(колекція)}).")
            return колекція[i]
        if isinstance(колекція, dict):
            if idx not in колекція:
                self._помилка(f"У словнику немає ключа «{idx}».")
            return колекція[idx]
        self._помилка(f"Не можна індексувати значення типу «{_тип_укр(колекція)}».")

    def _індекс_set(self, колекція, idx, значення):
        if isinstance(колекція, list):
            if not isinstance(idx, int) or isinstance(idx, bool):
                self._помилка("Індекс має бути цілим числом.")
            i = self._норм_індекс(idx, len(колекція))
            if i is None:
                self._помилка(f"Індекс {idx} поза межами (довжина {len(колекція)}).")
            колекція[i] = значення
            return
        if isinstance(колекція, dict):
            колекція[idx] = значення
            return
        self._помилка(f"Не можна записати за індексом у значення типу «{_тип_укр(колекція)}».")

    def _зріз_get(self, колекція, початок, кінець):
        """Python-подібний зріз: обидві межі — прапорці None («не задано»)
        або ціле число (від'ємне — з кінця); на відміну від звичайної
        індексації, межі зрізу лагідно обрізаються до [0, довжина], а не
        падають з помилкою."""
        if not isinstance(колекція, (list, str)):
            self._помилка(f"Не можна зробити зріз значення типу «{_тип_укр(колекція)}».")
        n = len(колекція)

        def межа(x, типове):
            if x is None:
                return типове
            if not isinstance(x, int) or isinstance(x, bool):
                self._помилка("Межа зрізу має бути цілим числом.")
            if x < 0:
                x += n
            return max(0, min(x, n))

        п = межа(початок, 0)
        к = межа(кінець, n)
        return колекція[п:к]

    # ---- виклики ----------------------------------------------------------------

    def _виклик_дії(self, аргумент):
        імя, argc = аргумент
        fn = self.функції.get(імя)
        if fn is None:
            self._помилка(f"Невідома дія «{імя}».")
        якщо_очікує = len(fn["параметри"])
        if якщо_очікує != argc:
            self._помилка(
                f"Дія «{імя}» очікує {якщо_очікує} аргумент(и), а отримала {argc}."
            )
        args = [self._pop() for _ in range(argc)]
        args.reverse()
        if len(self.кадри) >= ГЛИБИНА_ВИКЛИКІВ_МАКС:
            self._помилка(f"Забагато вкладених викликів (можлива нескінченна рекурсія в «{імя}»).")
        self.кадри.append(dict(zip(fn["параметри"], args)))
        self.стек_повернень.append(self.pc + 1)
        self.pc = fn["адреса"]

    def _виклик_native(self, аргумент):
        імя, argc = аргумент
        fn = self._native.get(імя)
        if fn is None:
            self._помилка(f"Невідома вбудована функція «{імя}».")
        args = [self._pop() for _ in range(argc)]
        args.reverse()
        try:
            результат = fn(*args)
        except ПомилкаВиконання:
            raise
        except TypeError as e:
            self._помилка(f"Функція «{імя}» викликана з неправильними аргументами ({e}).")
        self._push(результат)


def виконати_байткод(байткод, без_пристрою=False):
    вм = ВМ(без_пристрою=без_пристрою)
    вм.виконати(байткод)
    return вм
