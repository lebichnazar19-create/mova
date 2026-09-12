"""Вузли абстрактного синтаксичного дерева (AST) мови «Мова».

Кожен вузол — простий dataclass з полями `рядок`/`позиція` для повідомлень
про помилки на етапі компіляції.
"""

from dataclasses import dataclass, field


# ---- вирази -----------------------------------------------------------

@dataclass
class Вираз:
    рядок: int = field(default=0, kw_only=True)
    позиція: int = field(default=0, kw_only=True)


@dataclass
class ЧислоЛіт(Вираз):
    значення: object = 0


@dataclass
class РядокЛіт(Вираз):
    значення: str = ""


@dataclass
class БулЛіт(Вираз):
    значення: bool = False


@dataclass
class НіщоЛіт(Вираз):
    pass


@dataclass
class СписокЛіт(Вираз):
    елементи: list = field(default_factory=list)


@dataclass
class Змінна(Вираз):
    імя: str = ""


@dataclass
class Унарний(Вираз):
    оп: str = ""
    операнд: object = None


@dataclass
class Бінарний(Вираз):
    оп: str = ""
    ліво: object = None
    право: object = None


@dataclass
class Логічний(Вираз):
    """`і` / `або` — з коротким замиканням, тому окремо від Бінарний."""
    оп: str = ""
    ліво: object = None
    право: object = None


@dataclass
class Виклик(Вираз):
    імя: str = ""
    аргументи: list = field(default_factory=list)


@dataclass
class Індекс(Вираз):
    колекція: object = None
    індекс: object = None


@dataclass
class Зріз(Вираз):
    """`колекція[початок:кінець]` — обидва боки необов'язкові (`None`, якщо
    пропущені: `а[:3]`, `а[1:]`, `а[:]`)."""
    колекція: object = None
    початок: object = None
    кінець: object = None


# ---- інструкції ---------------------------------------------------------

@dataclass
class Хай:
    імя: str
    вираз: object
    рядок: int = 0
    позиція: int = 0


@dataclass
class Стала:
    імя: str
    вираз: object
    рядок: int = 0
    позиція: int = 0


@dataclass
class Присвоєння:
    імя: str
    вираз: object
    рядок: int = 0
    позиція: int = 0


@dataclass
class ПрисвоєнняІндекс:
    колекція: object
    індекс: object
    вираз: object
    рядок: int = 0
    позиція: int = 0


@dataclass
class ВиразІнструкція:
    вираз: object
    рядок: int = 0
    позиція: int = 0


@dataclass
class Якщо:
    умова: object
    тіло: list
    інакше: object  # list[інструкція] | Якщо | None
    рядок: int = 0
    позиція: int = 0


@dataclass
class Поки:
    умова: object
    тіло: list
    рядок: int = 0
    позиція: int = 0


@dataclass
class Для:
    імя: str
    ітерований: object
    тіло: list
    рядок: int = 0
    позиція: int = 0


@dataclass
class Перервись:
    рядок: int = 0
    позиція: int = 0


@dataclass
class Продовж:
    рядок: int = 0
    позиція: int = 0


@dataclass
class Дія:
    імя: str
    параметри: list
    тіло: list
    рядок: int = 0
    позиція: int = 0


@dataclass
class Поверни:
    вираз: object  # може бути None
    рядок: int = 0
    позиція: int = 0


@dataclass
class Програма:
    тіло: list
