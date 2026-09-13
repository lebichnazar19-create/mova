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
