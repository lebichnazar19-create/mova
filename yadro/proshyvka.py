"""Етап 3: прошивання плат з телефона — протокол ROM-завантажувача ESP32
(той самий, що в esptool), без комп'ютера і без Arduino IDE.

Дії мовою: проший(файл, плата), стерти(плата), інфо(плата). Прогрес
заливки — у відсотках через при_прогресі (застосунок показує в редакторі)
і рядками у вивід.

Протокол (esptool, ROM loader ESP32):
- SLIP-кадрування: 0xC0 на початку і в кінці кадру, 0xC0 -> DB DC,
  0xDB -> DB DD;
- запит: <BBHI> напрям 0x00, команда, довжина даних, контрольна сума
  (XOR усіх байтів даних з початковим 0xEF — лише для FLASH_DATA, інакше 0),
  далі дані; відповідь: <BBHI> напрям 0x01, команда, довжина, значення
  (READ_REG повертає тут регістр), далі дані, останні 4 байти — статус
  [статус, код_помилки, 0, 0] (ROM ESP32);
- команди: SYNC 0x08, READ_REG 0x0A, WRITE_REG 0x09, SPI_ATTACH 0x0D,
  SPI_SET_PARAMS 0x0B, FLASH_BEGIN 0x02, FLASH_DATA 0x03, FLASH_END 0x04;
- вхід у завантажувач: DTR/RTS на GPIO0 і EN — послідовність esptool
  (RTS=1 тримає EN у скиді, DTR=1 тягне GPIO0 до землі, відпускаємо EN,
  потім GPIO0);
- запис блоками по 4096 байт, кожен з контрольною сумою; розмір флешу —
  через SPI-команду RDID (0x9F) регістрами SPI, як у esptool.

Порт — будь-який об'єкт з write(bytes), read(n, таймаут) -> bytes,
set_dtr(bool), set_rts(bool), close(): UsbПорт (Android, через
plata.UsbSerial) або СимуляторESP32 (yadro/esp32_sym.py). По Wi-Fi
прошивати не можна — потрібен кабель.

НЕ ПЕРЕВІРЕНО НА ЗАЛІЗІ: усе нижче підтверджено лише симулятором (див.
README, розділ «Не перевірено на залізі»).
"""

import struct
import time
from pathlib import Path

from .errors import ПомилкаВиконання

# ---- сталі протоколу ---------------------------------------------------------------
SLIP_КІНЕЦЬ, SLIP_ESC, SLIP_ESC_КІНЕЦЬ, SLIP_ESC_ESC = 0xC0, 0xDB, 0xDC, 0xDD
КОНТРОЛЬНА_ПОЧАТОК = 0xEF
НАПРЯМ_ЗАПИТ, НАПРЯМ_ВІДПОВІДЬ = 0x00, 0x01
СТАТУС_БАЙТІВ = 4                 # ROM ESP32: [статус][помилка][0][0]

CMD = {
    "FLASH_BEGIN": 0x02, "FLASH_DATA": 0x03, "FLASH_END": 0x04,
    "SYNC": 0x08, "WRITE_REG": 0x09, "READ_REG": 0x0A,
    "SPI_SET_PARAMS": 0x0B, "SPI_ATTACH": 0x0D,
}
ПОМИЛКИ_ROM = {
    0x05: "отримано неправильне повідомлення (bad message)",
    0x06: "не вдалося виконати команду (failed to act)",
    0x07: "неправильна контрольна сума (bad checksum)",
    0x08: "запис у флеш не вдався (flash write error)",
    0x09: "читання флешу не вдалося (flash read error)",
    0x0A: "флеш прочитано не повністю (flash read length error)",
    0x0B: "стирання флешу не вдалося (deflate error)",
}

БЛОК = 4096                       # FLASH_WRITE_SIZE ROM-завантажувача
ТАЙМАУТ_С = 3.0
ТАЙМАУТ_SYNC_С = 0.1
СПРОБ_SYNC = 7
ТАЙМАУТ_СТИРАННЯ_С_НА_МБ = 30.0

ЧИПИ = {                          # значення регістра 0x40001000
    0x00F01D83: "ESP32",
    0x000007C6: "ESP32-S2",
    0x00000009: "ESP32-S3",
    0x6921506F: "ESP32-C3", 0x1B31506F: "ESP32-C3",
    0xFFF0C101: "ESP8266",
}
РЕГ_МАГІЯ = 0x40001000
РЕГ_EFUSE_MAC0, РЕГ_EFUSE_MAC1 = 0x3FF5A004, 0x3FF5A008      # ESP32: BLK0_RDATA1/2
# регістри SPI0 ESP32 для RDID
SPI_БАЗА = 0x3FF42000
SPI_CMD, SPI_USR, SPI_USR1, SPI_USR2 = SPI_БАЗА + 0x00, SPI_БАЗА + 0x1C, SPI_БАЗА + 0x20, SPI_БАЗА + 0x24
SPI_MOSI_DLEN, SPI_MISO_DLEN, SPI_W0 = SPI_БАЗА + 0x28, SPI_БАЗА + 0x2C, SPI_БАЗА + 0x80
SPI_USR_COMMAND, SPI_USR_MISO, SPI_USR_MOSI, SPI_CMD_USR = 1 << 31, 1 << 28, 1 << 27, 1 << 18
РОЗМІРИ_ФЛЕШУ = {0x12: 256 * 1024, 0x13: 512 * 1024, 0x14: 1 << 20, 0x15: 2 << 20, 0x16: 4 << 20,
                 0x17: 8 << 20, 0x18: 16 << 20, 0x19: 32 << 20}

при_прогресі = None               # застосунок: callback(відсоток, текст)


class ПомилкаПрошивки(ПомилкаВиконання):
    ЗАГОЛОВОК = "Помилка прошивки"


# ---- SLIP і кадри ------------------------------------------------------------------

def slip_закодувати(дані):
    вих = bytearray([SLIP_КІНЕЦЬ])
    for б in дані:
        if б == SLIP_КІНЕЦЬ:
            вих += bytes([SLIP_ESC, SLIP_ESC_КІНЕЦЬ])
        elif б == SLIP_ESC:
            вих += bytes([SLIP_ESC, SLIP_ESC_ESC])
        else:
            вих.append(б)
    вих.append(SLIP_КІНЕЦЬ)
    return bytes(вих)


def slip_розкодувати(кадр):
    """Вміст одного кадру (без 0xC0 по краях)."""
    вих = bytearray()
    i = 0
    while i < len(кадр):
        б = кадр[i]
        if б == SLIP_ESC:
            i += 1
            if i >= len(кадр):
                raise ПомилкаПрошивки("SLIP: кадр обірвано після байта-екрану 0xDB.")
            if кадр[i] == SLIP_ESC_КІНЕЦЬ:
                вих.append(SLIP_КІНЕЦЬ)
            elif кадр[i] == SLIP_ESC_ESC:
                вих.append(SLIP_ESC)
            else:
                raise ПомилкаПрошивки(f"SLIP: неправильна екран-послідовність DB {кадр[i]:02X}.")
        else:
            вих.append(б)
        i += 1
    return bytes(вих)


def контрольна_сума(дані):
    с = КОНТРОЛЬНА_ПОЧАТОК
    for б in дані:
        с ^= б
    return с


def запакувати_запит(команда, дані=b"", сума=0):
    return struct.pack("<BBHI", НАПРЯМ_ЗАПИТ, команда, len(дані), сума) + дані


def розпакувати_відповідь(кадр):
    """-> (команда, значення, дані_без_статусу, статус, код_помилки)."""
    if len(кадр) < 8 + СТАТУС_БАЙТІВ:
        raise ПомилкаПрошивки(f"Відповідь закоротка ({len(кадр)} байт).")
    напрям, команда, довжина, значення = struct.unpack("<BBHI", кадр[:8])
    if напрям != НАПРЯМ_ВІДПОВІДЬ:
        raise ПомилкаПрошивки(f"Очікувалась відповідь (0x01), отримано напрям 0x{напрям:02X}.")
    дані = кадр[8:]
    статус, код = дані[-СТАТУС_БАЙТІВ], дані[-СТАТУС_БАЙТІВ + 1]
    return команда, значення, дані[:-СТАТУС_БАЙТІВ], статус, код


# ---- читання кадрів з порту -----------------------------------------------------------

class _Читач:
    def __init__(self, порт):
        self.порт = порт
        self._буфер = b""

    def кадр(self, таймаут):
        """Наступний повний SLIP-кадр або None за таймаутом."""
        кінець = time.monotonic() + таймаут
        while True:
            поч = self._буфер.find(bytes([SLIP_КІНЕЦЬ]))
            if поч >= 0:
                кін = self._буфер.find(bytes([SLIP_КІНЕЦЬ]), поч + 1)
                if кін == поч + 1:            # порожній кадр C0 C0 — пропустити
                    self._буфер = self._буфер[поч + 1:]
                    continue
                if кін > 0:
                    кадр = self._буфер[поч + 1:кін]
                    self._буфер = self._буфер[кін + 1:]
                    return slip_розкодувати(кадр)
            лишилось = кінець - time.monotonic()
            if лишилось <= 0:
                return None
            шмат = self.порт.read(256, min(лишилось, 0.2))
            if шмат:
                self._буфер += шмат


# ---- завантажувач --------------------------------------------------------------------

class Завантажувач:
    """Сеанс із ROM-завантажувачем ESP32 через порт із DTR/RTS."""

    def __init__(self, порт, прогрес=None):
        self.порт = порт
        self.читач = _Читач(порт)
        self.прогрес = прогрес
        self.чип = None
        self.розмір_флешу = None

    # -- нижній рівень --

    def _команда(self, назва, дані=b"", сума=0, таймаут=ТАЙМАУТ_С, очікувати=True):
        код = CMD[назва]
        self.порт.write(slip_закодувати(запакувати_запит(код, дані, сума)))
        if not очікувати:
            return None
        кінець = time.monotonic() + таймаут
        while True:
            лишилось = кінець - time.monotonic()
            if лишилось <= 0:
                raise ПомилкаПрошивки(f"Плата не відповідає на {назва} ({таймаут:.1f} с). Перевір кабель і чи плата в режимі завантажувача.")
            кадр = self.читач.кадр(лишилось)
            if кадр is None:
                continue
            команда, значення, дані_в, статус, помилка = розпакувати_відповідь(кадр)
            if команда != код:
                continue                      # чужа/запізніла відповідь (напр., зайві SYNC)
            if статус != 0:
                raise ПомилкаПрошивки(f"Плата відхилила {назва}: {ПОМИЛКИ_ROM.get(помилка, f'код 0x{помилка:02X}')}.")
            return значення, дані_в

    def read_reg(self, адреса):
        значення, _ = self._команда("READ_REG", struct.pack("<I", адреса))
        return значення

    def write_reg(self, адреса, значення, маска=0xFFFFFFFF, затримка=0):
        self._команда("WRITE_REG", struct.pack("<IIII", адреса, значення, маска, затримка))

    # -- вхід у завантажувач і SYNC --

    def увійти_в_завантажувач(self):
        """Послідовність esptool (ClassicReset): DTR -> GPIO0, RTS -> EN."""
        п = self.порт
        п.set_dtr(False)        # GPIO0 = HIGH
        п.set_rts(True)         # EN = LOW — чип у скиді
        time.sleep(0.1)
        п.set_dtr(True)         # GPIO0 = LOW — режим завантажувача
        п.set_rts(False)        # EN = HIGH — чип стартує
        time.sleep(0.05)
        п.set_dtr(False)        # GPIO0 відпустити
        self.читач._буфер = b""

    def sync(self):
        дані = b"\x07\x07\x12\x20" + b"\x55" * 32
        for спроба in range(СПРОБ_SYNC):
            try:
                self._команда("SYNC", дані, таймаут=ТАЙМАУТ_SYNC_С)
            except ПомилкаПрошивки:
                continue
            # ROM шле кілька відповідей на SYNC — дочитати їх
            while self.читач.кадр(0.05) is not None:
                pass
            return True
        raise ПомилкаПрошивки(
            "Не вдалося синхронізуватись із завантажувачем: плата не відповідає на SYNC. "
            "Перевір кабель (потрібен USB, не Wi-Fi), або затисни BOOT і натисни EN."
        )

    def підключитись(self):
        self.увійти_в_завантажувач()
        self.sync()
        self.чип = ЧИПИ.get(self.read_reg(РЕГ_МАГІЯ), "невідомий чип")
        return self.чип

    # -- інформація --

    def mac(self):
        m0, m1 = self.read_reg(РЕГ_EFUSE_MAC0), self.read_reg(РЕГ_EFUSE_MAC1)
        байти = [(m1 >> 8) & 0xFF, m1 & 0xFF, (m0 >> 24) & 0xFF, (m0 >> 16) & 0xFF, (m0 >> 8) & 0xFF, m0 & 0xFF]
        return ":".join(f"{б:02X}" for б in байти)

    def flash_id(self):
        """RDID (0x9F) через регістри SPI0 — як esptool.run_spiflash_command."""
        self._команда("SPI_ATTACH", struct.pack("<II", 0, 0))
        старий_usr, старий_usr2 = self.read_reg(SPI_USR), self.read_reg(SPI_USR2)
        self.write_reg(SPI_MISO_DLEN, 24 - 1)
        self.write_reg(SPI_MOSI_DLEN, 0)
        self.write_reg(SPI_USR, SPI_USR_COMMAND | SPI_USR_MISO)
        self.write_reg(SPI_USR2, ((8 - 1) << 28) | 0x9F)
        self.write_reg(SPI_W0, 0)
        self.write_reg(SPI_CMD, SPI_CMD_USR)
        for _ in range(10):
            if self.read_reg(SPI_CMD) & SPI_CMD_USR == 0:
                break
        else:
            raise ПомилкаПрошивки("SPI-команда RDID не завершилась.")
        ід = self.read_reg(SPI_W0)
        self.write_reg(SPI_USR, старий_usr)
        self.write_reg(SPI_USR2, старий_usr2)
        return ід & 0xFFFFFF

    def розмір_флешу_байт(self):
        ід = self.flash_id()
        розмір = РОЗМІРИ_ФЛЕШУ.get((ід >> 16) & 0xFF)
        if розмір is None:
            raise ПомилкаПрошивки(f"Невідомий розмір флешу (flash id 0x{ід:06X}).")
        self.розмір_флешу = розмір
        return розмір

    def інфо(self):
        return {"чип": self.чип, "mac": self.mac(), "флеш": self.розмір_флешу_байт()}

    # -- запис --

    def _повідомити(self, відсоток, текст):
        if self.прогрес:
            self.прогрес(відсоток, текст)
        if при_прогресі:
            при_прогресі(відсоток, текст)

    def flash_begin(self, розмір, зсув):
        блоків = (розмір + БЛОК - 1) // БЛОК
        стерти = блоків * БЛОК
        таймаут = max(ТАЙМАУТ_С, ТАЙМАУТ_СТИРАННЯ_С_НА_МБ * стерти / (1 << 20))
        self._команда("FLASH_BEGIN", struct.pack("<IIII", стерти, блоків, БЛОК, зсув), таймаут=таймаут)
        return блоків

    def flash_data(self, блок, номер):
        дані = блок + b"\xFF" * (БЛОК - len(блок))
        self._команда("FLASH_DATA", struct.pack("<IIII", len(дані), номер, 0, 0) + дані, сума=контрольна_сума(дані))

    def flash_end(self, перезавантажити=True):
        self._команда("FLASH_END", struct.pack("<I", 0 if перезавантажити else 1))

    def записати(self, образ, зсув=0x0):
        if not образ:
            raise ПомилкаПрошивки("Образ прошивки порожній.")
        self._повідомити(0, "стирання")
        блоків = self.flash_begin(len(образ), зсув)
        for і in range(блоків):
            self.flash_data(образ[і * БЛОК:(і + 1) * БЛОК], і)
            self._повідомити(int((і + 1) * 100 / блоків), f"блок {і + 1}/{блоків}")
        self.flash_end()
        self._повідомити(100, "готово")
        return блоків

    def стерти(self):
        розмір = self.розмір_флешу or self.розмір_флешу_байт()
        self._повідомити(0, "стирання всього флешу")
        таймаут = max(ТАЙМАУТ_С, ТАЙМАУТ_СТИРАННЯ_С_НА_МБ * розмір / (1 << 20))
        # ROM-завантажувач стирає у FLASH_BEGIN: увесь флеш, 0 блоків даних
        self._команда("FLASH_BEGIN", struct.pack("<IIII", розмір, 0, БЛОК, 0), таймаут=таймаут)
        self.flash_end(перезавантажити=False)
        self._повідомити(100, "стерто")
        return розмір

    def перезавантажити(self):
        п = self.порт
        п.set_rts(True)
        time.sleep(0.1)
        п.set_rts(False)


# ---- порти -------------------------------------------------------------------------

class UsbПорт:
    """USB-серіал з DTR/RTS через usb-serial-for-android (лише Android)."""

    def __init__(self, індекс=0):
        from . import plata
        self._усб = plata.UsbSerial(індекс)
        self._порт = self._усб._порт
        self.назва = self._усб.назва

    def write(self, дані):
        self._усб.send(дані)

    def read(self, n, таймаут):
        return self._усб.recv(n, таймаут)

    def set_dtr(self, стан):
        self._порт.setDTR(bool(стан))

    def set_rts(self, стан):
        self._порт.setRTS(bool(стан))

    def close(self):
        self._усб.close()


def _відкрити_порт(плата):
    from . import plata
    if not isinstance(плата, str):
        raise ПомилкаПрошивки('Назва плати має бути рядком: проший("агент.bin", "USB").')
    н = плата.strip().lower()
    if н.startswith("wi") or н.startswith("tcp") or (н and н[0].isdigit()):
        # навіть у симуляції: по Wi-Fi прошивати не можна — це помилка користувача
        raise ПомилкаПрошивки("По Wi-Fi прошивати не можна — потрібен USB-кабель: проший(файл, \"USB\").")
    if plata._СИМУЛЯЦІЯ or н.startswith("симуляц"):
        from .esp32_sym import СимуляторESP32
        return СимуляторESP32()
    if н.startswith("usb"):
        індекс = int(плата.split(":", 1)[1]) if ":" in плата and плата.split(":", 1)[1].strip().isdigit() else 0
        return UsbПорт(індекс)
    raise ПомилкаПрошивки(f"Невідома плата «{плата}» для прошивання: \"USB\" або \"Симуляція\".")


def _сеанс(плата, прогрес=None):
    порт = _відкрити_порт(плата)
    з = Завантажувач(порт, прогрес)
    try:
        з.підключитись()
    except ПомилкаПрошивки:
        порт.close()
        raise
    return з


# ---- дії мови -------------------------------------------------------------------------

def _прогрес_у_вивід():
    останній = [-1]

    def показати(відсоток, текст):
        if відсоток // 10 != останній[0] // 10 or відсоток == 100:
            останній[0] = відсоток
            print(f"Заливка: {відсоток}% ({текст})")
    return показати


def проший(файл, плата="USB", зсув=0x0):
    """Залити .bin на плату. Повертає кількість записаних блоків."""
    if isinstance(файл, (bytes, bytearray)):
        образ = bytes(файл)
        назва = "образ"
    else:
        from . import fayly
        шлях = fayly.шлях(файл, _тека())
        if not шлях.is_file():
            raise ПомилкаПрошивки(f"Файл прошивки «{файл}» не знайдено.")
        if шлях.suffix.lower() != ".bin":
            raise ПомилкаПрошивки(f"Прошивка має бути файлом .bin, а не «{шлях.suffix}».")
        образ = шлях.read_bytes()
        назва = шлях.name
    if not isinstance(зсув, int) or зсув < 0:
        raise ПомилкаПрошивки("Зсув має бути невід'ємним цілим числом.")
    з = _сеанс(плата, _прогрес_у_вивід())
    try:
        print(f"Чип {з.чип}, заливаю {назва} ({len(образ)} байт) за адресою 0x{зсув:X}")
        блоків = з.записати(образ, зсув)
        з.перезавантажити()
        return блоків
    finally:
        з.порт.close()


def стерти(плата="USB"):
    з = _сеанс(плата, _прогрес_у_вивід())
    try:
        розмір = з.стерти()
        print(f"Флеш {розмір // (1 << 20)} МБ стерто.")
        return розмір
    finally:
        з.порт.close()


def інфо(плата="USB"):
    з = _сеанс(плата)
    try:
        і = з.інфо()
        return {"чип": і["чип"], "mac": і["mac"], "флеш": і["флеш"]}
    finally:
        з.порт.close()


_ТЕКА = [None]


def задати_теку(тека):
    _ТЕКА[0] = тека


def _тека():
    return _ТЕКА[0]


ФАЙЛ_АГЕНТА = "agent/agent_esp32/agent_esp32.bin"


def знайти_агента(корінь=None, тека_застосунку=None):
    """Шлях до готового .bin агента ESP32 або None з поясненням, де він має бути."""
    кандидати = []
    if корінь:
        кандидати.append(Path(корінь) / ФАЙЛ_АГЕНТА)
    if тека_застосунку:
        кандидати.append(Path(тека_застосунку) / "agent_esp32.bin")
    for к in кандидати:
        if к.is_file():
            return к
    return None
