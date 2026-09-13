"""Версія — єдине джерело yadro/versiya.py: main.py, buildozer.spec і
zastosunky.py беруть її звідти, а не зашивають окремо."""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from yadro.versiya import ВЕРСІЯ

КОРІНЬ = Path(__file__).resolve().parent.parent


def test_версія_має_вигляд_числа():
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", ВЕРСІЯ)


def test_buildozer_бере_версію_з_versiya_тим_самим_регулярним_виразом():
    spec = (КОРІНЬ / "buildozer.spec").read_text(encoding="utf-8")
    assert not re.search(r"^version = ", spec, re.M)          # без окремо зашитої версії
    регекс = re.search(r"^version\.regex = (.+)$", spec, re.M).group(1)
    файл = re.search(r"^version\.filename = %\(source\.dir\)s/(.+)$", spec, re.M).group(1)
    assert файл == "yadro/versiya.py"
    вміст = (КОРІНЬ / файл).read_text(encoding="utf-8")
    assert re.search(регекс, вміст).group(1) == ВЕРСІЯ
    assert "title = Мова" in spec and "${" not in spec


def test_main_і_zastosunky_не_зашивають_версію():
    main = (КОРІНЬ / "main.py").read_text(encoding="utf-8")
    assert "from yadro.versiya import ВЕРСІЯ" in main
    assert not re.search(r'^ВЕРСІЯ = "\d', main, re.M)
    assert "${" not in main and 'title = "Мова"' in main and 'text=f"Мова {ВЕРСІЯ}"' in main
    import zastosunky
    assert "version = " + ВЕРСІЯ in zastosunky.файли_застосунку("Тест", "друкуй(1)\n")["buildozer.spec"]


def test_числова_версія_зростає_і_збігається_зі_spec():
    from yadro.versiya import числова_версія, ЧИСЛОВА_ВЕРСІЯ
    assert числова_версія("1.3") == 10300 and числова_версія("1.3.2") == 10302
    assert числова_версія("1.12") == 11200 and числова_версія("2.0") == 20000
    assert числова_версія("1.2.1") < числова_версія("1.3") < числова_версія("1.10") < числова_версія("2.0")
    spec = (КОРІНЬ / "buildozer.spec").read_text(encoding="utf-8")
    assert re.search(r"^android\.numeric_version = (\d+)$", spec, re.M).group(1) == str(ЧИСЛОВА_ВЕРСІЯ)
    import zastosunky
    assert f"android.numeric_version = {ЧИСЛОВА_ВЕРСІЯ}" in zastosunky.файли_застосунку("Т", "друкуй(1)\n")["buildozer.spec"]
    assert f"version = {ВЕРСІЯ}" in (КОРІНЬ / "застосунки" / "кабель" / "buildozer.spec").read_text(encoding="utf-8")


def test_workflow_пише_збірку_і_числову_версію():
    for назва in ("build.yml", "zastosunky.yml"):
        текст = (КОРІНЬ / ".github" / "workflows" / назва).read_text(encoding="utf-8")
        assert 'pathlib.Path("yadro/zbirka.py").write_text(' in текст
        assert "android\\.numeric_version" in текст and "ЧИСЛОВА_ВЕРСІЯ" in текст
        assert "VERSIYA=" in текст


def test_рядок_версії_у_довідці():
    from yadro import dovidka, zbirka
    рядок = dovidka.рядок_версії()
    assert рядок.startswith(f"Мова {ВЕРСІЯ} — збірка ") and "коміт" in рядок
    assert zbirka.ДАТА == "локальна" and zbirka.КОМІТ == "—"   # у репозиторії — типові значення
    assert dovidka.текст_довідки().split("\n")[0] == рядок
