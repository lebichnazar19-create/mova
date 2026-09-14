"""1.1: «Зробити застосунок» (zastosunky.py) і публікація в GitHub через API
(github.py) — усе без Kivy і без мережі."""

import ast
import io
import json
import struct
import sys
import urllib.error
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import github
import zastosunky as з

КОД = 'друкуй("привіт")\n'


# ---- назви ---------------------------------------------------------------------

def test_безпечна_назва_і_слаг():
    assert з.безпечна_назва(" Мій  кабель/1.0 ") == "Мій кабель1.0"
    assert з.безпечна_назва("...") is None and з.безпечна_назва("") is None
    assert з.слаг("Кабель") == "kabel"
    assert з.слаг("Мій кабель 2") == "mii_kabel_2"
    assert з.слаг("Щоденник п'ять") == "shchodennyk_piat"
    assert з.слаг("123") == "mova_123" and з.слаг("!!!") == "mova_app"
    assert з.слаг("Cable App") == "cable_app"


# ---- файли застосунку ----------------------------------------------------------

def test_файли_застосунку_повний_набір():
    ф = з.файли_застосунку("Кабель", КОД, версія="1.1")
    assert set(ф) == {"програма.мова", "main.py", "buildozer.spec", "icon.png"}
    assert ф["програма.мова"] == КОД
    spec = ф["buildozer.spec"]
    assert "title = Кабель" in spec and "package.name = kabel" in spec
    assert "version = 1.1" in spec and "icon.filename = icon.png" in spec
    assert "source.include_exts = py,png,jpg,kv,atlas,мова" in spec
    assert "requirements = python3,kivy==2.3.0" in spec


def test_запускач_синтаксично_правильний_і_без_редактора():
    main = з.файли_застосунку("Кабель", КОД)["main.py"]
    ast.parse(main)  # чинний Python
    assert 'НАЗВА = \'Кабель\'' in main or "НАЗВА = 'Кабель'" in main
    assert 'ФАЙЛ_ПРОГРАМИ = "програма.мова"' in main
    assert "from zapusk import виконати_код" in main
    assert "CodeInput" not in main and "redaktor" not in main  # без редактора
    for потрібне in ("питай=self._питай", "кнопка=self._додати_кнопку", "при_кресленні=self._при_кресленні"):
        assert потрібне in main


def test_програма_отримує_перенос_рядка_в_кінці():
    assert з.файли_застосунку("а", "друкуй(1)")["програма.мова"] == "друкуй(1)\n"


def test_іконка_чинний_png_192():
    png = з.іконка_png("Кабель")
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    ширина, висота, глибина, тип = struct.unpack(">IIBB", png[16:26])
    assert (ширина, висота, глибина, тип) == (192, 192, 8, 2)
    # IDAT розпаковується у 192 рядки по 1 + 192*3 байти
    поз = png.index(b"IDAT")
    довжина = struct.unpack(">I", png[поз - 4:поз])[0]
    сирі = zlib.decompress(png[поз + 4:поз + 4 + довжина])
    assert len(сирі) == 192 * (1 + 192 * 3)
    # різні назви — різні кольори, та сама назва — той самий файл
    assert з.іконка_png("Кабель") == png and з.іконка_png("Інше") != png


def test_порожня_назва_чи_код_помилка():
    with pytest.raises(з.ПомилкаЗастосунку):
        з.файли_застосунку("", КОД)
    with pytest.raises(з.ПомилкаЗастосунку):
        з.файли_застосунку("Кабель", "   \n")


def test_створити_застосунок_пише_теку_і_список(tmp_path):
    тека, файли = з.створити_застосунок(tmp_path, "Мій кабель", КОД, "1.1")
    assert тека == tmp_path / "застосунки" / "Мій кабель"
    assert sorted(файли) == sorted(["програма.мова", "main.py", "buildozer.spec", "icon.png"])
    assert (тека / "програма.мова").read_text(encoding="utf-8") == КОД
    assert (тека / "icon.png").read_bytes().startswith(b"\x89PNG")
    assert з.список_застосунків(tmp_path) == ["Мій кабель"]
    # повторне створення перезаписує без помилки
    з.створити_застосунок(tmp_path, "Мій кабель", 'друкуй(2)\n')
    assert (тека / "програма.мова").read_text(encoding="utf-8") == 'друкуй(2)\n'
    assert з.список_застосунків(tmp_path / "нема") == []


def test_шляхи_для_публікації():
    ш = з.шляхи_для_публікації("Кабель", {"main.py": "x", "icon.png": b"y"})
    assert ш == {"застосунки/Кабель/main.py": "x", "застосунки/Кабель/icon.png": b"y"}


def test_приклад_кабель_у_репозиторії_збігається_з_програмою_геометрії():
    корінь = Path(__file__).resolve().parent.parent
    тека = корінь / "застосунки" / "кабель"
    assert (тека / "програма.мова").read_text(encoding="utf-8") == (корінь / "приклади" / "геометрія.мова").read_text(encoding="utf-8")
    for ф in ("main.py", "buildozer.spec", "icon.png"):
        assert (тека / ф).is_file()
    assert "title = кабель" in (тека / "buildozer.spec").read_text(encoding="utf-8")


def test_workflow_збирає_кожну_теку_і_докладає_ядро():
    текст = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "zastosunky.yml").read_text(encoding="utf-8")
    assert "matrix:" in текст and "fromJSON" in текст
    assert "cp -r yadro biblioteky zapusk.py vidzhety.py" in текст
    assert "name: програми-APK-${{ env.VERSIYA }}-${{ matrix.app }}" in текст   # однозначна назва артефакта
    основний = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "build.yml").read_text(encoding="utf-8")
    assert "name: мова-APK-${{ env.VERSIYA }}" in основний
    assert "from yadro.versiya import ВЕРСІЯ" in основний and "from yadro.versiya import ВЕРСІЯ" in текст
    import re
    # ідентифікатори jobs/steps і вирази ${{ }} — лише латиниця, інакше GitHub не розбирає файл
    for id_ in re.findall(r"^  ([^\s:#-][^:]*):$", текст, re.M) + re.findall(r"^\s+- id: (\S+)$", текст, re.M):
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", id_), id_
    for вираз in re.findall(r"\$\{\{(.*?)\}\}", текст):
        assert вираз.isascii(), вираз


# ---- публікація в GitHub через API (без мережі) --------------------------------------

class _Відповідь(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _фальшивий_urlopen(журнал):
    def відкрити(запит, timeout=0):
        журнал.append((запит.get_method(), запит.full_url, запит.headers.get("Authorization"),
                       json.loads(запит.data.decode()) if запит.data else None))
        шлях = запит.full_url
        if шлях.endswith("/git/ref/heads/main"):
            return _Відповідь(json.dumps({"object": {"sha": "base111"}}).encode())
        if "/git/commits/base111" in шлях:
            return _Відповідь(json.dumps({"tree": {"sha": "tree000"}}).encode())
        if шлях.endswith("/git/blobs"):
            return _Відповідь(json.dumps({"sha": "blob" + str(len(журнал))}).encode())
        if шлях.endswith("/git/trees"):
            return _Відповідь(json.dumps({"sha": "tree999"}).encode())
        if шлях.endswith("/git/commits"):
            return _Відповідь(json.dumps({"sha": "commit777"}).encode())
        if "/git/refs/heads/main" in шлях:
            return _Відповідь(b"{}")
        raise AssertionError(шлях)
    return відкрити


def test_опублікувати_робить_один_коміт_з_усіма_файлами():
    журнал = []
    sha = github.опублікувати(
        "ghp_секрет", "user/repo",
        {"застосунки/Кабель/main.py": "print(1)", "застосунки/Кабель/icon.png": b"\x89PNG"},
        "Застосунок Кабель", відкрити=_фальшивий_urlopen(журнал),
    )
    assert sha == "commit777"
    методи = [(м, u.split("/repos/user/repo")[1]) for м, u, _, _ in журнал]
    assert методи == [
        ("GET", "/git/ref/heads/main"), ("GET", "/git/commits/base111"),
        ("POST", "/git/blobs"), ("POST", "/git/blobs"),
        ("POST", "/git/trees"), ("POST", "/git/commits"), ("PATCH", "/git/refs/heads/main"),
    ]
    assert all(а == "token ghp_секрет" for _, _, а, _ in журнал)
    дерево = журнал[4][3]
    assert дерево["base_tree"] == "tree000"
    assert sorted(е["path"] for е in дерево["tree"]) == ["застосунки/Кабель/icon.png", "застосунки/Кабель/main.py"]
    коміт = журнал[5][3]
    assert коміт["message"] == "Застосунок Кабель" and коміт["parents"] == ["base111"]
    assert журнал[6][3] == {"sha": "commit777"}


def test_помилки_публікації_не_містять_токена():
    with pytest.raises(github.ПомилкаПублікації) as info:
        github.опублікувати("", "user/repo", {}, "м")
    assert "Токен" in str(info.value)
    with pytest.raises(github.ПомилкаПублікації):
        github.опублікувати("ghp_x", "без_слеша", {}, "м")

    def відхилити(запит, timeout=0):
        raise urllib.error.HTTPError(запит.full_url, 401, "Unauthorized", {}, io.BytesIO(b'{"message":"Bad credentials"}'))

    with pytest.raises(github.ПомилкаПублікації) as info:
        github.опублікувати("ghp_секретний", "user/repo", {"a": "b"}, "м", відкрити=відхилити)
    assert "401" in str(info.value) and "ghp_секретний" not in str(info.value)


def test_налаштування_зберігаються_і_токен_маскується(tmp_path):
    assert github.прочитати_налаштування(tmp_path) == {"токен": "", "репо": github.РЕПО_ТИПОВЕ, "гілка": "main"}
    github.зберегти_налаштування(tmp_path, токен=" ghp_abcdef123 ")
    github.зберегти_налаштування(tmp_path, репо="me/mova")
    н = github.прочитати_налаштування(tmp_path)
    assert н["токен"] == "ghp_abcdef123" and н["репо"] == "me/mova"
    assert github.замаскувати(н["токен"]).startswith("ghp_") and "abcdef" not in github.замаскувати(н["токен"])
    assert (tmp_path / github.ФАЙЛ_НАЛАШТУВАНЬ).is_file()
