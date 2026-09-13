"""0.9: довідка (yadro/dovidka.py) — повна, згрупована, з прикладами."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yadro import dovidka
from yadro.keywords import КЛЮЧОВІ_СЛОВА
from yadro.natives import ІМЕНА_NATIVE


def test_є_кожне_ключове_слово_і_кожна_вбудована_дія():
    імена = set(dovidka._ЗА_ІМЕНЕМ)
    assert set(КЛЮЧОВІ_СЛОВА) <= імена, set(КЛЮЧОВІ_СЛОВА) - імена
    assert ІМЕНА_NATIVE <= імена, ІМЕНА_NATIVE - імена
    # і нічого вигаданого, крім вбудованих сталих (ПІ, вихід/вхід/вхід_підтяжка)
    from yadro.kompilyator import ВБУДОВАНІ_СТАЛІ
    assert імена - set(КЛЮЧОВІ_СЛОВА) - ІМЕНА_NATIVE == set(ВБУДОВАНІ_СТАЛІ)


def test_кожен_запис_має_приклад_і_один_рядок_опису():
    for група, елементи in dovidka.ГРУПИ:
        assert група
        for імя, приклад, опис in елементи:
            assert приклад.strip() and "\n" not in опис and опис.strip(), імя
            assert імя in приклад, імя  # приклад справді показує це слово


def test_групи_як_у_завданні():
    назви = [г for г, _ in dovidka.ГРУПИ]
    for очікувана in ("Мова", "Списки", "Словники", "Рядки", "Математика", "Геометрія", "Файли", "Пристрій", "Малювання"):
        assert any(н.startswith(очікувана) for н in назви), очікувана


def test_текст_довідки_згрупований_і_повний():
    текст = dovidka.текст_довідки()
    assert текст.startswith("ДОВІДКА МОВИ")
    for група, елементи in dovidka.ГРУПИ:
        assert f"== {група} ==" in текст
        for імя, _, опис in елементи:
            assert f"{імя} — {опис}" in текст
    # приклади — з відступом під описом
    assert "\n    хай х = 5\n" in текст


def test_приклад_і_опис_за_іменем():
    assert dovidka.приклад("словник").startswith("хай д = словник(")
    assert dovidka.опис("кнопка")
    assert dovidka.приклад("такого_нема") is None and dovidka.опис("такого_нема") is None
