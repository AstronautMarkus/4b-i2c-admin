import logging
from abc import ABC, abstractmethod

from core.config import LCD_BACKEND

logger = logging.getLogger("lcd")


class LCDDisplay(ABC):
    @abstractmethod
    def init(self):
        ...

    @abstractmethod
    def clear(self):
        ...

    @abstractmethod
    def write_lines(self, line1, line2):
        ...

    @abstractmethod
    def create_char(self, location, bitmap):
        ...

    @abstractmethod
    def write_at(self, col, line, byte_list):
        ...


class RealLCD(LCDDisplay):
    """Implementación real: delega en lcd_i2c.py (import diferido, nunca a nivel de módulo)."""

    def __init__(self):
        import lcd_i2c as hw

        self._hw = hw
        self._lines = {1: hw.LCD_LINE_1, 2: hw.LCD_LINE_2}

    def init(self):
        self._hw.lcd_init()

    def clear(self):
        self._hw.lcd_clear()

    def write_lines(self, line1, line2):
        self._hw.lcd_message(line1, self._hw.LCD_LINE_1)
        self._hw.lcd_message(line2, self._hw.LCD_LINE_2)

    def create_char(self, location, bitmap):
        self._hw.lcd_create_char(location, bitmap)
        self._hw.lcd_byte(self._hw.LCD_LINE_1, self._hw.LCD_CMD)  # vuelve a DDRAM

    def write_at(self, col, line, byte_list):
        self._hw.lcd_write_at(col, self._lines[line], byte_list)


class ConsoleLCD(LCDDisplay):
    """Implementación de desarrollo: imprime el contenido del LCD por stdout."""

    def __init__(self):
        self._last_frame = None

    def init(self):
        print("[LCD] init (console backend)")

    def clear(self):
        pass

    def write_lines(self, line1, line2):
        frame = (line1.ljust(16)[:16], line2.ljust(16)[:16])
        if frame == self._last_frame:
            return
        self._last_frame = frame
        printable = tuple(
            "".join(c if 32 <= ord(c) < 127 else "*" for c in text) for text in frame
        )
        print(f"+{'-' * 16}+\n|{printable[0]}|\n|{printable[1]}|\n+{'-' * 16}+")

    def create_char(self, location, bitmap):
        pass

    def write_at(self, col, line, byte_list):
        text = "".join(chr(b) if 32 <= b < 127 else "*" for b in byte_list)
        print(f"[LCD col={col} line={line}] {text}")


def get_lcd_backend(mode=None):
    mode = mode or LCD_BACKEND

    if mode == "console":
        return ConsoleLCD()
    if mode == "real":
        return RealLCD()

    # auto: intenta hardware real, cae a consola ante cualquier fallo (sin smbus, sin bus I2C, etc.)
    try:
        return RealLCD()
    except Exception as exc:
        logger.warning("No se pudo inicializar el LCD real (%s); usando ConsoleLCD.", exc)
        return ConsoleLCD()
