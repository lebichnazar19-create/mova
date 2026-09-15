#!/usr/bin/env python3
"""Книжка з документації «Мови» — один PDF з ПІДРУЧНИК.md і ДОВІДНИК.md.

    python3 tools/knyzhka.py            # -> КНИЖКА.pdf у корені репозиторію
    python3 tools/knyzhka.py вихід.pdf

Нічого нового не пише: титул (назва, версія з yadro/versiya.py), зміст із
номерами сторінок, далі підручник, далі довідник — текст береться з
markdown-файлів як є. Потрібні fpdf2 (pip install fpdf2) і шрифт DejaVu
(apt install fonts-dejavu): вбудовані шрифти PDF без кирилиці.

Підмножина markdown, якої досить для цих двох файлів: заголовки «#» (частина)
і «##» (розділ), абзаци (рядки зливаються), огорожі ``` (моноширинним
шрифтом, з відступом і сірим тлом), таблиці «| … |», списки «- », жирний
**…**, код у зворотних лапках `…`, горизонтальні лінії «---» (пропускаються).
Зміст — у два проходи: спершу тіло рендериться без змісту, щоб дізнатись
сторінки розділів, потім усе разом (зсув сторінок = титул + сторінки
змісту); якщо зміст зайняв інакшу кількість сторінок, ніж очікувалось —
ще один прохід.
"""

import re
import sys
from pathlib import Path

КОРІНЬ = Path(__file__).resolve().parent.parent
ДЖЕРЕЛА = ("ПІДРУЧНИК.md", "ДОВІДНИК.md")
ВИХІД = КОРІНЬ / "КНИЖКА.pdf"

ТЕКИ_ШРИФТІВ = (
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
    Path("/data/data/com.termux/files/usr/share/fonts"),
    Path.home() / ".fonts",
)
ШРИФТИ = {
    ("DejaVu", ""): "DejaVuSans.ttf",
    ("DejaVu", "B"): "DejaVuSans-Bold.ttf",
    ("DejaVuMono", ""): "DejaVuSansMono.ttf",
    ("DejaVuMono", "B"): "DejaVuSansMono-Bold.ttf",
}

РОЗМІР = 10.5        # основний текст, pt
РОЗМІР_КОДУ = 9
МІЖРЯДКОВИЙ = 5.2    # мм
ВІДСТУП_КОДУ = 5     # мм зліва для блоків коду і списків
СІРЕ_ТЛО = (243, 243, 243)


# ---- розбір markdown ------------------------------------------------------------

def розібрати(текст):
    """Список блоків: ("h1"|"h2", текст), ("p", текст), ("code", [рядки]),
    ("table", [[клітинки], ...]), ("list", [пункти])."""
    блоки = []
    рядки = текст.split("\n")
    i = 0
    абзац = []

    def закрити_абзац():
        if абзац:
            блоки.append(("p", " ".join(р.strip() for р in абзац)))
            абзац.clear()

    while i < len(рядки):
        р = рядки[i]
        if р.startswith("```"):
            закрити_абзац()
            i += 1
            код = []
            while i < len(рядки) and not рядки[i].startswith("```"):
                код.append(рядки[i])
                i += 1
            блоки.append(("code", код))
            i += 1
            continue
        if р.startswith("# "):
            закрити_абзац()
            блоки.append(("h1", р[2:].strip()))
        elif р.startswith("## "):
            закрити_абзац()
            блоки.append(("h2", р[3:].strip()))
        elif р.startswith("|"):
            закрити_абзац()
            рядки_таблиці = []
            while i < len(рядки) and рядки[i].startswith("|"):
                клітинки = [к.strip() for к in рядки[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", к) for к in клітинки):
                    рядки_таблиці.append(клітинки)
                i += 1
            блоки.append(("table", рядки_таблиці))
            continue
        elif re.match(r"^\s*[-*] ", р):
            закрити_абзац()
            пункти = []
            while i < len(рядки) and рядки[i].strip():
                if re.match(r"^\s*[-*] ", рядки[i]):
                    пункти.append(re.sub(r"^\s*[-*] ", "", рядки[i]).strip())
                else:
                    пункти[-1] += " " + рядки[i].strip()
                i += 1
            блоки.append(("list", пункти))
            continue
        elif р.strip() == "---" or not р.strip():
            закрити_абзац()
        else:
            абзац.append(р)
        i += 1
    закрити_абзац()
    return блоки


def _фрагменти(текст):
    """Інлайн-розмітка -> [(текст, стиль)], стиль: "" | "code" | "b"."""
    результат = []
    for частина in re.split(r"(`[^`]*`|\*\*[^*]+\*\*)", текст):
        if not частина:
            continue
        if частина.startswith("`") and частина.endswith("`") and len(частина) >= 2:
            результат.append((частина[1:-1], "code"))
        elif частина.startswith("**") and частина.endswith("**") and len(частина) >= 4:
            результат.append((частина[2:-2], "b"))
        else:
            результат.append((частина, ""))
    return результат


def _без_розмітки(текст):
    return "".join(т for т, _ in _фрагменти(текст))


# ---- PDF ---------------------------------------------------------------------------

def _знайти_шрифт(файл):
    for тека in ТЕКИ_ШРИФТІВ:
        шлях = тека / файл
        if шлях.is_file():
            return шлях
    raise SystemExit(
        f"Немає шрифту {файл}: постав DejaVu (apt install fonts-dejavu) — "
        "без нього кирилиця в PDF не відрендериться."
    )


def _клас_pdf():
    from fpdf import FPDF

    class Книжка(FPDF):
        def __init__(self):
            super().__init__(orientation="P", unit="mm", format="A4")
            self.set_margins(20, 18, 18)
            self.set_auto_page_break(auto=True, margin=18)
            for (сім_я, стиль), файл in ШРИФТИ.items():
                self.add_font(сім_я, стиль, str(_знайти_шрифт(файл)))
            self.без_номера = set()   # сторінки без номера внизу (титул)

        def footer(self):
            if self.page in self.без_номера:
                return
            self.set_y(-12)
            self.set_font("DejaVu", "", 8.5)
            self.set_text_color(110)
            self.cell(0, 6, str(self.page), align="C")
            self.set_text_color(0)

        # -- елементи --

        def _ширина(self):
            return self.w - self.l_margin - self.r_margin

        def інлайн(self, текст, розмір=РОЗМІР, h=МІЖРЯДКОВИЙ):
            """Абзац з інлайн-кодом і жирним; переноси робить write()."""
            for фрагмент, стиль in _фрагменти(текст):
                if стиль == "code":
                    self.set_font("DejaVuMono", "", розмір - 0.5)
                elif стиль == "b":
                    self.set_font("DejaVu", "B", розмір)
                else:
                    self.set_font("DejaVu", "", розмір)
                self.write(h, фрагмент)
            self.ln(h)

        def абзац(self, текст):
            self.set_x(self.l_margin)
            self.інлайн(текст)
            self.ln(2)

        def заголовок_частини(self, текст):
            self.add_page()
            self.ln(40)
            self.set_font("DejaVu", "B", 24)
            self.multi_cell(0, 12, текст, align="C")
            self.ln(10)

        def заголовок_розділу(self, текст):
            # заголовок не лишається сам унизу сторінки
            if self.get_y() > self.h - self.b_margin - 40:
                self.add_page()
            self.ln(4)
            self.set_font("DejaVu", "B", 14)
            self.set_x(self.l_margin)
            self.multi_cell(0, 7.5, _без_розмітки(текст))
            self.ln(2.5)

        def код(self, рядки):
            self.set_font("DejaVuMono", "", РОЗМІР_КОДУ)
            self.set_fill_color(*СІРЕ_ТЛО)
            self.ln(1)
            старий_відступ = self.l_margin
            self.set_left_margin(старий_відступ + ВІДСТУП_КОДУ)
            for р in рядки or [""]:
                self.set_x(self.l_margin)
                self.multi_cell(self._ширина(), 4.6, " " + р.replace("\t", "    ") if р else " ", fill=True)
            self.set_left_margin(старий_відступ)
            self.set_x(старий_відступ)
            self.ln(3)

        def список(self, пункти):
            старий_відступ = self.l_margin
            for п in пункти:
                self.set_x(старий_відступ)
                self.set_font("DejaVu", "", РОЗМІР)
                self.cell(ВІДСТУП_КОДУ, МІЖРЯДКОВИЙ, "•")
                self.set_left_margin(старий_відступ + ВІДСТУП_КОДУ)
                self.інлайн(п)
                self.set_left_margin(старий_відступ)
            self.set_x(старий_відступ)
            self.ln(2)

        def таблиця(self, рядки):
            from fpdf.fonts import FontFace

            колонок = max(len(р) for р in рядки)
            рядки = [р + [""] * (колонок - len(р)) for р in рядки]
            # ширини — за довжиною вмісту, але не вужче за 14 %
            довжини = [max(len(_без_розмітки(р[k])) for р in рядки) or 1 for k in range(колонок)]
            ваги = [max(д ** 0.6, 1) for д in довжини]
            ширини = [max(в / sum(ваги), 0.14) for в in ваги]
            ширини = [round(100 * ш / sum(ширини)) for ш in ширини]
            self.set_font("DejaVu", "", РОЗМІР - 1)
            моно = FontFace(family="DejaVuMono", size_pt=РОЗМІР - 1.5)
            жирний = FontFace(family="DejaVu", emphasis="BOLD", size_pt=РОЗМІР - 1)
            self.ln(1)
            with self.table(
                col_widths=ширини, line_height=4.8, padding=1.2,
                borders_layout="HORIZONTAL_LINES", text_align="LEFT", width=self._ширина(),
            ) as таблиця:
                for i, р in enumerate(рядки):
                    ряд = таблиця.row()
                    for клітинка in р:
                        if i == 0:
                            ряд.cell(_без_розмітки(клітинка), style=жирний)
                        elif re.fullmatch(r"`[^`]*`", клітинка.strip()):
                            ряд.cell(клітинка.strip()[1:-1], style=моно)   # уся клітинка — код
                        else:
                            ряд.cell(_без_розмітки(клітинка))
            self.ln(3)

    return Книжка


def _рендер(pdf, блоки, зміст=None):
    """Тіло книжки; повертає [(рівень, назва, сторінка)] для змісту."""
    записи = []
    for тип, вміст in блоки:
        if тип == "h1":
            pdf.заголовок_частини(вміст)
            записи.append((1, вміст, pdf.page))
        elif тип == "h2":
            pdf.заголовок_розділу(вміст)
            записи.append((2, _без_розмітки(вміст), pdf.page))
        elif тип == "p":
            pdf.абзац(вміст)
        elif тип == "code":
            pdf.код(вміст)
        elif тип == "table":
            pdf.таблиця(вміст)
        elif тип == "list":
            pdf.список(вміст)
    return записи


def _титул(pdf, версія):
    pdf.add_page()
    pdf.без_номера.add(pdf.page)
    pdf.ln(70)
    pdf.set_font("DejaVu", "B", 40)
    pdf.cell(0, 20, "Мова", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("DejaVu", "", 16)
    pdf.cell(0, 12, "Підручник і довідник", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("DejaVu", "", 12)
    pdf.cell(0, 10, f"версія {версія}", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(40)
    pdf.set_font("DejaVu", "", 9.5)
    pdf.set_text_color(110)
    pdf.multi_cell(0, 5, "Зібрано з ПІДРУЧНИК.md і ДОВІДНИК.md (tools/knyzhka.py).", align="C")
    pdf.set_text_color(0)


def _зміст(pdf, записи, зсув):
    """Сторінки змісту; повертає, скільки їх вийшло."""
    pdf.add_page()
    перша = pdf.page
    pdf.set_font("DejaVu", "B", 18)
    pdf.cell(0, 12, "Зміст", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    ширина = pdf.w - pdf.l_margin - pdf.r_margin
    for рівень, назва, сторінка in записи:
        номер = str(сторінка + зсув)
        if рівень == 1:
            pdf.ln(2)
            pdf.set_font("DejaVu", "B", 11.5)
            відступ = 0
        else:
            pdf.set_font("DejaVu", "", 10.5)
            відступ = 6
        ш_номера = pdf.get_string_width(номер) + 2
        pdf.set_x(pdf.l_margin + відступ)
        текст = назва
        while pdf.get_string_width(текст + " …") > ширина - відступ - ш_номера and len(текст) > 4:
            текст = текст[:-2].rstrip()
        крапки = ""
        while pdf.get_string_width(текст + " " + крапки + ".") <= ширина - відступ - ш_номера:
            крапки += "."
        pdf.cell(ширина - відступ - ш_номера, 6.2, текст + " " + крапки)
        pdf.cell(ш_номера, 6.2, номер, align="R", new_x="LMARGIN", new_y="NEXT")
    return pdf.page - перша + 1


def зібрати(вихід=ВИХІД, джерела=ДЖЕРЕЛА, версія=None):
    """Зібрати книжку; повертає [(рівень, назва, сторінка_у_pdf)] змісту."""
    if версія is None:
        sys.path.insert(0, str(КОРІНЬ))
        from yadro.versiya import ВЕРСІЯ as версія
    Книжка = _клас_pdf()
    блоки = []
    for назва in джерела:
        блоки.extend(розібрати((КОРІНЬ / назва).read_text(encoding="utf-8")))

    # прохід 1: тіло без титулу й змісту — сторінки розділів
    записи = _рендер(Книжка(), блоки)
    сторінок_змісту = 1
    for _ in range(4):
        pdf = Книжка()
        _титул(pdf, версія)
        зсув = 1 + сторінок_змісту
        вийшло = _зміст(pdf, записи, зсув)
        if вийшло != сторінок_змісту:
            сторінок_змісту = вийшло
            continue
        записи_тіла = _рендер(pdf, блоки)
        # _рендер повертає абсолютні сторінки pdf; у другому проході перед
        # тілом уже стоять титул і зміст, тож віднімаємо зсув.
        assert [з[2] - зсув for з in записи_тіла] == [з[2] for з in записи], "сторінки розділів зсунулись"
        pdf.set_title(f"Мова {версія} — підручник і довідник")
        pdf.set_author("Мова")
        pdf.output(str(вихід))
        return [(р, н, с + зсув) for р, н, с in записи]
    raise SystemExit("Не вдалося стабілізувати кількість сторінок змісту.")


def перевірити_гліфи(джерела=ДЖЕРЕЛА):
    """Символи з джерел, яких немає в DejaVu Sans — щоб не було квадратиків."""
    from fontTools.ttLib import TTFont

    cmap = TTFont(str(_знайти_шрифт("DejaVuSans.ttf"))).getBestCmap()
    символи = set()
    for назва in джерела:
        символи |= set((КОРІНЬ / назва).read_text(encoding="utf-8"))
    return sorted(с for с in символи if ord(с) >= 32 and ord(с) not in cmap)


if __name__ == "__main__":
    вихід = Path(sys.argv[1]) if len(sys.argv) > 1 else ВИХІД
    відсутні = перевірити_гліфи()
    if відсутні:
        print("Увага: у DejaVu Sans немає гліфів для:", " ".join(f"{с} (U+{ord(с):04X})" for с in відсутні))
    записи = зібрати(вихід)
    print(f"{вихід}: {len(записи)} записів у змісті, остання сторінка змісту вказує на {записи[-1][2]}")
