"""0.5: файли — прочитай_файл / запиши_файл / допиши_файл / є_файл.
Відносні шляхи — від теки, переданої у ВМ (тека_файлів)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from yadro.errors import ПомилкаВиконання
from yadro.kompilyator import компілювати
from yadro.parser import парсити_текст
from yadro.vm import виконати_байткод


def запустити(джерело, тека, capsys):
    виконати_байткод(
        компілювати(парсити_текст(джерело)), без_пристрою=True, тека_файлів=str(тека)
    )
    return capsys.readouterr().out


def test_запиши_і_прочитай(tmp_path, capsys):
    вивід = запустити(
        'запиши_файл("нотатки.txt", "привіт\\nсвіт")\n'
        'друкуй(прочитай_файл("нотатки.txt"))\n',
        tmp_path,
        capsys,
    )
    assert вивід == "привіт\nсвіт\n"
    assert (tmp_path / "нотатки.txt").read_text(encoding="utf-8") == "привіт\nсвіт"


def test_допиши_в_кінець_і_створює_якщо_немає(tmp_path, capsys):
    вивід = запустити(
        'допиши_файл("лог.txt", "1\\n")\n'
        'допиши_файл("лог.txt", "2\\n")\n'
        'друкуй(прочитай_файл("лог.txt"))\n',
        tmp_path,
        capsys,
    )
    assert вивід == "1\n2\n\n"


def test_є_файл(tmp_path, capsys):
    (tmp_path / "є.txt").write_text("x", encoding="utf-8")
    вивід = запустити('друкуй(є_файл("є.txt"), є_файл("нема.txt"))\n', tmp_path, capsys)
    assert вивід.split() == ["істина", "хиба"]


def test_відносний_шлях_від_теки_застосунку_а_не_cwd(tmp_path, monkeypatch, capsys):
    інша = tmp_path / "інша"
    інша.mkdir()
    monkeypatch.chdir(інша)
    запустити('запиши_файл("а.txt", "тут")\n', tmp_path, capsys)
    assert (tmp_path / "а.txt").is_file()
    assert not (інша / "а.txt").exists()


def test_підтеки_створюються_а_число_пишеться_як_текст(tmp_path, capsys):
    вивід = запустити(
        'запиши_файл("тека/в.txt", 42)\nдрукуй(прочитай_файл("тека/в.txt"))\n', tmp_path, capsys
    )
    assert вивід.strip() == "42"


def test_читання_неіснуючого_файлу_помилка_яку_можна_перехопити(tmp_path, capsys):
    with pytest.raises(ПомилкаВиконання) as info:
        запустити('прочитай_файл("нема.txt")\n', tmp_path, capsys)
    assert "«нема.txt» не знайдено" in str(info.value)

    вивід = запустити(
        "спробуй\n"
        '    прочитай_файл("нема.txt")\n'
        "якщо помилка\n"
        '    друкуй("ловлю:", помилка)\n',
        tmp_path,
        capsys,
    )
    assert вивід.startswith("ловлю: Файл «нема.txt» не знайдено")


def test_ім_я_файлу_має_бути_рядком(tmp_path, capsys):
    with pytest.raises(ПомилкаВиконання) as info:
        запустити("прочитай_файл(5)\n", tmp_path, capsys)
    assert "непорожнім рядком" in str(info.value)


def test_cli_рахує_шлях_від_теки_програми(tmp_path, monkeypatch, capsys):
    import мова as мова_cli

    (tmp_path / "п.мова").write_text(
        'запиши_файл("вихід.txt", "ок")\nдрукуй(прочитай_файл("вихід.txt"))\n', encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path.parent)
    мова_cli.команда_виконати(str(tmp_path / "п.мова"), без_пристрою=True)
    assert capsys.readouterr().out.strip() == "ок"
    assert (tmp_path / "вихід.txt").read_text(encoding="utf-8") == "ок"


def test_zapusk_передає_теку(tmp_path):
    from zapusk import виконати_код

    вивід, успіх = виконати_код('запиши_файл("з.txt", "apk")\nдрукуй(є_файл("з.txt"))', тека=str(tmp_path))
    assert успіх and вивід.strip() == "істина"
    assert (tmp_path / "з.txt").read_text(encoding="utf-8") == "apk"


def test_рядки_файлу(tmp_path, capsys):
    (tmp_path / "с.txt").write_text("а\nб\n\nв", encoding="utf-8")
    вивід = запустити('друкуй(рядки_файлу("с.txt"), довжина(рядки_файлу("с.txt")))\n', tmp_path, capsys)
    assert вивід.strip() == "[а, б, , в] 4"
    with pytest.raises(ПомилкаВиконання):
        запустити('рядки_файлу("нема.txt")\n', tmp_path, capsys)


def test_файли_в_теці(tmp_path, capsys):
    (tmp_path / "б.txt").write_text("1", encoding="utf-8")
    (tmp_path / "а.txt").write_text("1", encoding="utf-8")
    (tmp_path / "тека").mkdir()
    вивід = запустити('друкуй(файли_в_теці(), файли_в_теці("тека"), файли_в_теці("."))\n', tmp_path, capsys)
    assert вивід.strip() == "[а.txt, б.txt, тека] [] [а.txt, б.txt, тека]"
    with pytest.raises(ПомилкаВиконання) as info:
        запустити('файли_в_теці("нема")\n', tmp_path, capsys)
    assert "Теку «нема» не знайдено" in str(info.value)


def test_видали_файл(tmp_path, capsys):
    (tmp_path / "в.txt").write_text("1", encoding="utf-8")
    вивід = запустити('видали_файл("в.txt")\nдрукуй(є_файл("в.txt"))\n', tmp_path, capsys)
    assert вивід.strip() == "хиба" and not (tmp_path / "в.txt").exists()
    with pytest.raises(ПомилкаВиконання) as info:
        запустити('видали_файл("в.txt")\n', tmp_path, capsys)
    assert "не знайдено" in str(info.value)
    (tmp_path / "тека").mkdir()
    with pytest.raises(ПомилкаВиконання) as info:
        запустити('видали_файл("тека")\n', tmp_path, capsys)
    assert "це тека" in str(info.value)
