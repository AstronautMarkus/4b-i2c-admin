"""
Low-level driver for a 16x2 LCD connected via an I2C backpack (PCF8574)
on a Raspberry Pi 4B.

Wiring:
    LCD (I2C backpack)  ->  Raspberry Pi 4B (GPIO header)
    GND                  ->  GND   (pin 6, or any GND pin)
    VCC (5V)             ->  5V    (pin 2 or 4)
    SDA                  ->  GPIO2 / SDA1  (pin 3)
    SCL                  ->  GPIO3 / SCL1  (pin 5)

Requirements:
    - Enable I2C: sudo raspi-config -> Interface Options -> I2C -> Enable
    - Install dependencies: sudo apt install python3-smbus i2c-tools
    - Confirm the module address: i2cdetect -y 1
      (usually 0x27, some modules use 0x3F)
"""

from smbus import SMBus
from time import sleep

# --- I2C bus configuration ---
LCD_ADDR = 0x27        # I2C address of the module (confirm with i2cdetect -y 1)
I2C_BUS = 1             # On Raspberry Pi 4B the usable I2C bus is 1 (SDA1/SCL1 pins)

bus = SMBus(I2C_BUS)

# --- LCD constants (HD44780 protocol in 4-bit mode) ---
LCD_CHR = 1             # Mode: send character (data)
LCD_CMD = 0             # Mode: send command

LCD_LINE_1 = 0x80       # DDRAM start address of line 1
LCD_LINE_2 = 0xC0       # DDRAM start address of line 2

ENABLE = 0b00000100     # Enable (E) bit of the PCF8574
BACKLIGHT = 0b00001000  # Bit that keeps the backlight on


def lcd_toggle_enable(data):
    """
    Generates the pulse on the Enable (E) pin required for the LCD to
    latch the nibble that was just written to the I2C bus.
    """
    sleep(0.0005)
    bus.write_byte(LCD_ADDR, data | ENABLE)
    sleep(0.0005)
    bus.write_byte(LCD_ADDR, data & ~ENABLE)
    sleep(0.0005)


def lcd_byte(bits, mode):
    """
    Sends a full byte to the LCD in two 4-bit steps (high nibble, then
    low nibble), as required by the HD44780's 4-bit mode.

    mode = LCD_CMD -> the byte is a command (cursor position, clear, etc.)
    mode = LCD_CHR -> the byte is a character to display
    """
    high = mode | (bits & 0xF0) | BACKLIGHT
    low = mode | ((bits << 4) & 0xF0) | BACKLIGHT

    bus.write_byte(LCD_ADDR, high)
    lcd_toggle_enable(high)

    bus.write_byte(LCD_ADDR, low)
    lcd_toggle_enable(low)


def lcd_init():
    """Standard HD44780 initialization sequence in 4-bit mode, 2 lines."""
    lcd_byte(0x33, LCD_CMD)  # Initialize
    lcd_byte(0x32, LCD_CMD)  # Force 4-bit mode
    lcd_byte(0x28, LCD_CMD)  # 2 lines, 5x8 character font
    lcd_byte(0x0C, LCD_CMD)  # Display on, cursor and blink off
    lcd_byte(0x06, LCD_CMD)  # Auto-increment cursor to the right
    lcd_byte(0x01, LCD_CMD)  # Clear display
    sleep(0.005)


def lcd_clear():
    """Clears the screen content and returns the cursor to the origin."""
    lcd_byte(0x01, LCD_CMD)
    sleep(0.005)


def lcd_message(text, line):
    """
    Writes 'text' on the given line (LCD_LINE_1 or LCD_LINE_2).
    The text is padded/truncated to 16 characters so it never overflows.
    """
    text = text.ljust(16)[:16]

    lcd_byte(line, LCD_CMD)
    for char in text:
        lcd_byte(ord(char), LCD_CHR)


def lcd_create_char(location, bitmap):
    """
    Loads a 5x8 pixel pattern into the LCD's CGRAM, at slot 'location'
    (0-7), so it can later be used like any other character (chr(location)).
    After this call the cursor is left in CGRAM, so it must be
    repositioned in DDRAM (lcd_byte(LCD_LINE_1/2, LCD_CMD)) before
    writing regular text again.
    """
    location &= 0x07
    lcd_byte(0x40 | (location << 3), LCD_CMD)
    for row in bitmap:
        lcd_byte(row, LCD_CHR)


def lcd_write_at(col, line, byte_list):
    """Positions the cursor at (col, line) and writes a list of raw bytes."""
    lcd_byte(line + col, LCD_CMD)
    for b in byte_list:
        lcd_byte(b, LCD_CHR)


def main():
    lcd_init()
    lcd_message("AstronautMarkus", LCD_LINE_1)
    lcd_message("Raspberry Pi :D", LCD_LINE_2)

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        lcd_clear()


if __name__ == "__main__":
    main()
