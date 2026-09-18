"""Проба OpenGL (proby/gl_kub.py): математика й куб без Kivy."""

import math
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

КОРІНЬ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(КОРІНЬ / "proby"))

import gl_kub as g


def довжина(в):
    return math.sqrt(sum(к * к for к in в[:3]))


def приблизно(а, б):
    return all(abs(x - y) < 1e-9 for x, y in zip(а, б))


# ---- куб -------------------------------------------------------------------------

Р = g.РОЗМІР_ВЕРШИНИ


def вершина(н):
    return g.ВЕРШИНИ[н * Р:(н + 1) * Р]


def test_куб_24_вершини_36_індексів():
    assert Р == 9 and len(g.ВЕРШИНИ) == 24 * Р and len(g.ІНДЕКСИ) == 36
    assert min(g.ІНДЕКСИ) == 0 and max(g.ІНДЕКСИ) == 23
    assert [назва for назва, _, _ in g.ФОРМАТ] == [b"v_pos", b"v_color", b"v_normal"]


def test_кожна_грань_одноколірна_на_одній_площині_і_з_двох_трикутників():
    for н, (назва, колір, кути) in enumerate(g.ГРАНІ):
        вершини = [вершина(н * 4 + i) for i in range(4)]
        assert all(tuple(в[3:6]) == колір for в in вершини), назва
        # одна з координат стала (±1) — грань лежить у площині
        assert any(len({в[к] for в in вершини}) == 1 and abs(вершини[0][к]) == 1 for к in range(3)), назва
        assert set(g.ІНДЕКСИ[н * 6:н * 6 + 6]) == {н * 4, н * 4 + 1, н * 4 + 2, н * 4 + 3}


def test_усі_8_кутів_куба_вжиті():
    кути = {tuple(g.ВЕРШИНИ[i:i + 3]) for i in range(0, len(g.ВЕРШИНИ), Р)}
    assert кути == {(x, y, z) for x in (-1.0, 1.0) for y in (-1.0, 1.0) for z in (-1.0, 1.0)}


def test_нормаль_кожної_грані_одинична_і_назовні():
    for н, (назва, _, кути) in enumerate(g.ГРАНІ):
        нормаль = g.нормаль_грані(кути)
        assert abs(довжина(нормаль) - 1) < 1e-9, назва
        # назовні: у той самий бік, що й центр грані від центру куба
        центр = [sum(к[i] for к in кути) / 4 for i in range(3)]
        assert sum(a * b for a, b in zip(нормаль, центр)) > 0.99, назва
        # нормаль паралельна одній осі, і саме тій, де координата грані стала
        assert sorted(abs(к) for к in нормаль) == [0, 0, 1], назва
        # і та сама нормаль у всіх 4 вершинах грані в буфері
        for i in range(4):
            assert tuple(вершина(н * 4 + i)[6:9]) == нормаль, назва
    assert g.нормаль_грані(((0, 0, 0), (1, 0, 0), (0, 1, 0))) == (0, 0, 1)   # проти год. стрілки → +Z
    assert g.нормаль_грані(((0, 0, 0), (0, 1, 0), (1, 0, 0))) == (0, 0, -1)  # за год. стрілкою → -Z


def test_нормалізуй():
    assert g.нормалізуй((3, 0, 4)) == (0.6, 0, 0.8)
    assert g.нормалізуй((0, 0, 0)) == (0, 0, 0)
    assert abs(довжина(g.НАПРЯМ_СВІТЛА) - 1) < 1e-9


# ---- освітлення ----------------------------------------------------------------

def test_освітленість_косинус_плюс_розсіяне():
    світло = (0, 0, 1)
    assert g.освітленість((0, 0, 1), світло, 0.25) == 1.0             # грань дивиться на світло
    assert g.освітленість((0, 0, -1), світло, 0.25) == 0.25           # відвернута — лише розсіяне, не 0
    assert g.освітленість((1, 0, 0), світло, 0.25) == 0.25            # боком — теж лише розсіяне
    assert abs(g.освітленість((1, 0, 1), світло, 0.25) - (0.25 + 0.75 * math.cos(math.radians(45)))) < 1e-9
    assert g.освітленість((0, 0, 1), (0, 0, 5), 0.25) == 1.0          # напрям світла нормалізується
    assert 0 < g.РОЗСІЯНЕ < 0.5


def test_грані_куба_освітлені_по_різному_і_жодна_не_чорна():
    я = {назва: g.освітленість(g.нормаль_грані(кути)) for назва, _, кути in g.ГРАНІ}
    assert min(я.values()) >= g.РОЗСІЯНЕ and max(я.values()) < 1.0
    assert я["перед"] > я["верх"] > я["право"] > я["зад"] == я["низ"] == я["ліво"] == g.РОЗСІЯНЕ


def test_нормаль_після_повороту_без_зсуву():
    # матриця моделі має зсув на -ВІДСТАНЬ, але на нормаль він не діє
    assert приблизно(g.нормаль_після_повороту(g.матриця_моделі(g.одинична()), (0, 0, 1)), (0, 0, 1))
    assert приблизно(g.нормаль_після_повороту(g.матриця_моделі(g.поворот_y(90)), (0, 0, 1)), (1, 0, 0))
    # після повороту куба на 180° передня грань — відвернута від світла
    м = g.матриця_моделі(g.поворот_y(180))
    assert g.освітленість(g.нормаль_після_повороту(м, (0, 0, 1)), (0, 0, 1)) == g.РОЗСІЯНЕ


# ---- матриці ---------------------------------------------------------------------

def test_одинична_і_множення():
    м = g.зсув(1, 2, 3)
    assert g.множ(g.одинична(), м) == м and g.множ(м, g.одинична()) == м
    assert g.застосуй(g.множ(g.зсув(1, 2, 3), g.зсув(10, 20, 30)), (0, 0, 0, 1)) == (11, 22, 33, 1)
    # порядок має значення: спершу застосовується права
    точка = (1, 0, 0, 1)
    assert приблизно(g.застосуй(g.множ(g.зсув(0, 0, 5), g.поворот_y(90)), точка), (0, 0, 4, 1))
    assert приблизно(g.застосуй(g.множ(g.поворот_y(90), g.зсув(0, 0, 5)), точка), (5, 0, -1, 1))


def test_поворот_зберігає_довжину_і_крутить_у_правильний_бік():
    assert приблизно(g.застосуй(g.поворот_y(90), (0, 0, 1, 1)), (1, 0, 0, 1))
    assert приблизно(g.застосуй(g.поворот_x(90), (0, 0, 1, 1)), (0, -1, 0, 1))
    for м in (g.поворот_x(33), g.поворот_y(-71), g.множ(g.поворот_x(10), g.поворот_y(20))):
        assert abs(довжина(g.застосуй(м, (1, 2, 3, 1))) - довжина((1, 2, 3))) < 1e-9


def test_перспектива_близько_минус_один_далеко_плюс_один():
    п = g.перспектива(45, 1.0, 0.1, 100)
    def ndc(x, y, z):
        x2, y2, z2, w = g.застосуй(п, (x, y, z, 1))
        return x2 / w, y2 / w, z2 / w
    assert abs(ndc(0, 0, -0.1)[2] + 1) < 1e-9
    assert abs(ndc(0, 0, -100)[2] - 1) < 1e-9
    # далеке — менше: та сама точка вдвічі далі — вдвічі ближче до центру
    assert abs(ndc(1, 1, -4)[0] * 2 - ndc(1, 1, -2)[0]) < 1e-9
    assert ndc(1, 0, -2)[0] > 0 and ndc(0, -1, -2)[1] < 0
    # ширший екран стискає x, y не чіпає
    ш = g.перспектива(45, 2.0, 0.1, 100)
    assert abs(g.застосуй(ш, (1, 1, -2, 1))[0] * 2 - g.застосуй(п, (1, 1, -2, 1))[0]) < 1e-9
    assert g.застосуй(ш, (1, 1, -2, 1))[1] == g.застосуй(п, (1, 1, -2, 1))[1]


# ---- перетягування ---------------------------------------------------------------

def test_перетягування_праворуч_і_вгору_тягне_передню_грань_за_пальцем():
    перед = (0, 0, 1, 1)
    м = g.поворот_перетягування(g.одинична(), 20, 0)
    x, y, z, _ = g.застосуй(м, перед)
    assert x > 0 and abs(y) < 1e-9 and z < 1
    м = g.поворот_перетягування(g.одинична(), 0, 20)
    x, y, z, _ = g.застосуй(м, перед)
    assert y > 0 and abs(x) < 1e-9
    assert g.поворот_перетягування(g.одинична(), 0, 0) == g.одинична()


def test_перетягування_в_осях_екрана_а_не_куба():
    # куб уже повернутий на 90° навколо Y; палець угору все одно тягне
    # передню (з погляду камери) грань угору
    старт = g.поворот_y(90)
    перед_камери = (0, 0, 1, 1)
    м = g.поворот_перетягування(старт, 0, 20)
    # точка куба, що зараз дивиться на камеру
    та_що_попереду = (-1, 0, 0, 1)
    assert приблизно(g.застосуй(старт, та_що_попереду), перед_камери)
    _, y, _, _ = g.застосуй(м, та_що_попереду)
    assert y > 0
    assert abs(g.застосуй(м, та_що_попереду)[0]) < 1e-9


def test_матриця_моделі_відсуває_куб_від_камери():
    x, y, z, w = g.застосуй(g.матриця_моделі(g.одинична()), (0, 0, 0, 1))
    assert (x, y, z, w) == (0, 0, -g.ВІДСТАНЬ, 1)
    # весь куб між «близько» і «далеко»
    assert g.БЛИЗЬКО < g.ВІДСТАНЬ - math.sqrt(3) and g.ВІДСТАНЬ + math.sqrt(3) < g.ДАЛЕКО


# ---- шейдери ---------------------------------------------------------------------

KIVY_ТИПОВИЙ_ФРАГМЕНТНИЙ = """
#ifdef GL_ES
precision highp float;
#endif
varying vec4 frag_color;
varying vec2 tex_coord0;
uniform sampler2D texture0;
void main (void) { gl_FragColor = frag_color * texture2D(texture0, tex_coord0); }
"""


def test_шейдери_узгоджені_з_форматом_буфера():
    for назва, _, _ in g.ФОРМАТ:
        assert f"attribute vec3 {назва.decode()}" in g.ВЕРШИННИЙ
    assert "gl_Position" in g.ВЕРШИННИЙ and "uniform mat4 proj_mat" in g.ВЕРШИННИЙ
    assert "uniform mat4 model_mat" in g.ВЕРШИННИЙ
    assert "gl_FragColor" in g.ФРАГМЕНТНИЙ and "precision mediump float" in g.ФРАГМЕНТНИЙ
    assert g.узгодженість_шейдерів() == []
    # освітлення: нормаль іде varying-ом, світло — uniform-ами, які задає застосунок
    assert "varying vec3 normal_v" in g.ВЕРШИННИЙ and "varying vec3 normal_v" in g.ФРАГМЕНТНИЙ
    assert "uniform vec3 light_dir" in g.ФРАГМЕНТНИЙ and "uniform float ambient" in g.ФРАГМЕНТНИЙ
    assert "vec4(v_normal, 0.0)" in g.ВЕРШИННИЙ     # w = 0 — зсув на нормаль не діє
    текст = (КОРІНЬ / "proby" / "gl_kub.py").read_text(encoding="utf-8")
    assert 'self.canvas["light_dir"]' in текст and 'self.canvas["ambient"]' in текст


def test_узгодженість_ловить_розбіжність_varying_імена_kivy_і_precision():
    assert g.узгодженість_шейдерів(g.ВЕРШИННИЙ, g.ФРАГМЕНТНИЙ.replace("vec3 kolir", "vec4 kolir")) == [
        "varying kolir: у вершинному vec3, у фрагментному vec4"]
    assert g.узгодженість_шейдерів(g.ВЕРШИННИЙ, g.ФРАГМЕНТНИЙ.replace("varying vec3 kolir;", "varying vec3 kolir2;")) == [
        "varying kolir2 є у фрагментному, але не у вершинному",
        "varying kolir є у вершинному, але не у фрагментному"]
    # саме так проба впала на телефоні: ім'я як у Kivy, тип інший
    проблеми = g.узгодженість_шейдерів(g.ВЕРШИННИЙ.replace("kolir", "frag_color"),
                                       g.ФРАГМЕНТНИЙ.replace("kolir", "frag_color").replace("precision", ""))
    assert any("frag_color збігається з типовим шейдером Kivy" in п for п in проблеми)
    assert "у фрагментному немає precision (обов'язково в GLSL ES 1.00)" in проблеми
    assert g.узгодженість_шейдерів(g.ВЕРШИННИЙ.replace("attribute vec3 v_color", "attribute vec4 v_color"), g.ФРАГМЕНТНИЙ) == [
        "attribute v_color має бути vec3 у вершинному"]


def test_наші_varying_не_збігаються_з_типовими_kivy():
    for ім_я in g.KIVY_VARYING:
        assert ім_я not in g.ВЕРШИННИЙ and ім_я not in g.ФРАГМЕНТНИЙ


def test_render_context_отримує_обидва_шейдери_разом():
    """shader.vs = … лінкує наш вершинний з типовим фрагментним Kivy — не можна."""
    текст = (КОРІНЬ / "proby" / "gl_kub.py").read_text(encoding="utf-8")
    assert "vs=ВЕРШИННИЙ, fs=ФРАГМЕНТНИЙ" in текст
    assert "shader.vs =" not in текст and "shader.fs =" not in текст
    # info log драйвера — у наш лог, для компіляції обох і для зв'язування
    for виклик in ("glGetShaderInfoLog", "glGetProgramInfoLog", "GL_LINK_STATUS", "GL_COMPILE_STATUS"):
        assert виклик in текст, виклик


def _glslang(tmp_path, вершинний, фрагментний):
    v, f = tmp_path / "k.vert", tmp_path / "k.frag"
    v.write_text("#version 100\n" + вершинний, encoding="utf-8")
    f.write_text("#version 100\n" + фрагментний, encoding="utf-8")
    return subprocess.run(["glslangValidator", "-l", str(v), str(f)], capture_output=True, text=True)


немає_glslang = pytest.mark.skipif(shutil.which("glslangValidator") is None, reason="немає glslangValidator")


@немає_glslang
def test_обидва_шейдери_звязуються_разом_glsl_es_100(tmp_path):
    """-l: не по одному, а лінкування вершинного з фрагментним — саме тут
    ловляться розбіжності varying, які CI раніше пропускав."""
    р = _glslang(tmp_path, g.ВЕРШИННИЙ, g.ФРАГМЕНТНИЙ)
    assert р.returncode == 0, р.stdout + р.stderr


@немає_glslang
def test_glslang_справді_ловить_розбіжність_і_пастку_kivy(tmp_path):
    р = _glslang(tmp_path, g.ВЕРШИННИЙ, g.ФРАГМЕНТНИЙ.replace("vec3 kolir", "vec4 kolir").replace("vec4(kolir, 1.0)", "kolir"))
    assert р.returncode != 0 and "Types must match" in р.stdout
    # старий варіант проби (varying vec3 frag_color) з типовим фрагментним Kivy
    р = _glslang(tmp_path, g.ВЕРШИННИЙ.replace("kolir", "frag_color"), KIVY_ТИПОВИЙ_ФРАГМЕНТНИЙ)
    assert р.returncode != 0 and "frag_color" in р.stdout


# ---- збірка APK ------------------------------------------------------------------

def test_spec_проби_узгоджений_з_головним():
    import configparser
    проба, головний = configparser.ConfigParser(), configparser.ConfigParser()
    проба.read(КОРІНЬ / "proby" / "gl_kub.spec", encoding="utf-8")
    головний.read(КОРІНЬ / "buildozer.spec", encoding="utf-8")
    assert проба["app"]["package.name"] == "probagl" and проба["app"]["title"] == "Проба GL"
    assert проба["app"]["requirements"] == "python3,kivy==2.3.0"
    # ті самі p4a/NDK/API — спільний кеш SDK на раннері
    for ключ in ("p4a.branch", "android.ndk", "android.api", "android.build_tools_version", "android.archs"):
        assert проба["app"][ключ] == головний["app"][ключ], ключ
    # проба не потрапляє в головний APK
    assert "proby" in головний["app"]["source.exclude_dirs"].split(",")


def test_workflow_проби_збирає_gl_kub_в_артефакт():
    текст = (КОРІНЬ / ".github" / "workflows" / "proby.yml").read_text(encoding="utf-8")
    assert "name: проба-GL-APK" in текст
    assert "cp proby/gl_kub.py zbirka_gl/main.py" in текст
    assert "cp proby/gl_kub.spec zbirka_gl/buildozer.spec" in текст
    assert 'hashFiles(\'proby/gl_kub.spec\')' in текст
    assert '- "proby/**"' in текст


# ---- лог у файл ------------------------------------------------------------------

def test_відкрити_лог_пише_в_усі_доступні_і_пропускає_недоступні(tmp_path, capsys):
    а, б = tmp_path / "а" / "mova_gl.log", tmp_path / "mova_gl.log"
    а.parent.mkdir()
    немає = tmp_path / "немає_такої_теки" / "mova_gl.log"
    assert g.відкрити_лог([str(а), str(немає), str(б)]) == [str(а), str(б)]
    g.лог("крок 1")
    for ф in (а, б):
        текст = ф.read_text(encoding="utf-8")
        assert "===== старт " in текст and "лог пишеться у: " in текст and "крок 1" in текст
        assert "не вдалось відкрити " + str(немає) in текст
    assert not немає.parent.exists()          # тек не створюємо
    assert "крок 1" in capsys.readouterr().out  # і на stdout (лог Kivy/консоль)
    g.відкрити_лог([])


def test_записати_помилку_кладе_повний_traceback(tmp_path):
    ф = tmp_path / "mova_gl.log"
    g.відкрити_лог([str(ф)])
    try:
        raise RuntimeError("шейдер не зібрався")
    except RuntimeError as п:
        g.записати_помилку(п)
    текст = ф.read_text(encoding="utf-8")
    assert "ПОМИЛКА: Traceback" in текст and "RuntimeError: шейдер не зібрався" in текст
    assert "test_проба_gl.py" in текст       # рядок файлу, де впало
    g.відкрити_лог([])


def test_кандидати_логу_на_компютері_і_на_android(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANDROID_ARGUMENT", raising=False)
    assert g.кандидати_логу() == [str(tmp_path / "mova_gl.log")]
    monkeypatch.setenv("ANDROID_ARGUMENT", "/data/data/org.mova.probagl/files/app")
    monkeypatch.setenv("EXTERNAL_STORAGE", "/storage/emulated/0")
    к = g.кандидати_логу()   # без jnius на комп'ютері — без Android/data, але без падіння
    assert к[:3] == ["/storage/emulated/0/mova_gl.log", "/storage/emulated/0/Download/mova_gl.log",
                     "/storage/emulated/0/Documents/mova_gl.log"]
    assert к[-1] == str(tmp_path / "mova_gl.log")


def test_запуск_логує_кожен_крок_і_ловить_падіння():
    текст = (КОРІНЬ / "proby" / "gl_kub.py").read_text(encoding="utf-8")
    for крок in ('лог("старт proby/gl_kub.py")', 'лог("імпорт Kivy…")', "вікно створено", 'RenderContext з обома шейдерами',
                 "шейдер зібрано і зв'язано", "Mesh створено", 'лог("матриці задано")', 'лог("перший кадр намальовано")',
                 'лог("on_start', "підчепити_лог_kivy()"):
        assert крок in текст, крок
    assert "except BaseException as п:" in текст and "записати_помилку(п)" in текст
    # відкрити_лог() — до всього, ще до імпорту Kivy
    assert текст.index("відкрити_лог()\n") < текст.index("запустити()\n")
