"""Стекова віртуальна машина. Виконує байткод, нічого не знає про синтаксис
мови — лише про інструкції з розділу 5 ТЗ (плюс MAKE_FUNCTION/MAKE_LIST/
INDEX_GET/INDEX_SET, потрібні для дій і списків).

VM отримує вже готовий байткод (dict з ключами "константи", "код",
опційно "позиції") і виконує його. Про природу помилки (тип, повідомлення)
дбає сама VM; текст рядка джерела для гарного виводу з «^» додає викликач
(ядро/мова.py), бо лише він тримає оригінальний текст програми.
"""

import time

from . import екран, малюнок, пристрій, розум
from .вбудовані import (
    ПРИСТРІЙ as _ІМЕНА_ПРИСТРІЙ,
    РОЗУМ as _ІМЕНА_РОЗУМ,
    МАЛЮНОК as _ІМЕНА_МАЛЮНОК,
    ЕКРАН as _ІМЕНА_ЕКРАН,
)
from .помилки import ПомилкаВиконання

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
            пристрій.увімкнути_симуляцію(True)
            розум.увімкнути_симуляцію(True)

        self._native = {
            "друкуй": self._друкуй,
            "питай": self._питай,
            "спи": self._спи,
            "довжина": self._довжина,
            "рядок": до_рядка,
            "число": self._число,
            "цілий": self._цілий,
            "діапазон": self._діапазон,
        }
        for ім_я in _ІМЕНА_ПРИСТРІЙ:
            self._native[ім_я] = getattr(пристрій, ім_я)
        for ім_я in _ІМЕНА_РОЗУМ:
            self._native[ім_я] = getattr(розум, ім_я)
        for ім_я in _ІМЕНА_МАЛЮНОК:
            self._native[ім_я] = getattr(малюнок, ім_я)
        for ім_я in _ІМЕНА_ЕКРАН:
            self._native[ім_я] = getattr(екран, ім_я)

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

    # ---- допоміжне -----------------------------------------------------------

    def _поточна_позиція(self):
        if 0 <= self.pc < len(self.позиції):
            return tuple(self.позиції[self.pc])
        return (0, 0)

    def _помилка(self, повідомлення):
        рядок, кол = self._поточна_позиція()
        raise ПомилкаВиконання(повідомлення, рядок, кол)

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
        позиції = байткод.get("позиції") or [[0, 0]] * len(новий_код)
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
                    рядок, кол = self._поточна_позиція()
                    e.рядок, e.позиція = рядок, кол
                raise
            except (ZeroDivisionError, IndexError, KeyError, ValueError, TypeError) as e:
                рядок, кол = self._поточна_позиція()
                raise ПомилкаВиконання(f"Помилка під час виконання: {e}", рядок, кол) from e

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

    def _індекс_get(self, колекція, idx):
        if isinstance(колекція, (list, str)):
            if not isinstance(idx, int) or isinstance(idx, bool):
                self._помилка("Індекс має бути цілим числом.")
            if idx < 0 or idx >= len(колекція):
                self._помилка(f"Індекс {idx} поза межами (довжина {len(колекція)}).")
            return колекція[idx]
        if isinstance(колекція, dict):
            if idx not in колекція:
                self._помилка(f"У словнику немає ключа «{idx}».")
            return колекція[idx]
        self._помилка(f"Не можна індексувати значення типу «{_тип_укр(колекція)}».")

    def _індекс_set(self, колекція, idx, значення):
        if isinstance(колекція, list):
            if not isinstance(idx, int) or isinstance(idx, bool):
                self._помилка("Індекс має бути цілим числом.")
            if idx < 0 or idx >= len(колекція):
                self._помилка(f"Індекс {idx} поза межами (довжина {len(колекція)}).")
            колекція[idx] = значення
            return
        if isinstance(колекція, dict):
            колекція[idx] = значення
            return
        self._помилка(f"Не можна записати за індексом у значення типу «{_тип_укр(колекція)}».")

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
