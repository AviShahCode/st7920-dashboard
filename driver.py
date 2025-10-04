import spidev
import time
from gpiozero import OutputDevice
from copy import deepcopy


SPI_SPEED_HZ = 2_000_000  # 2MHz


class ST7920:
    def __init__(self, cs_pin, bus=0, device=0, reset_pin=None, width=128, height=64):
        self.width = width
        self.height = height

        # SPI setup
        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = SPI_SPEED_HZ
        self.spi.mode = 0b00

        # Chip select pin
        self.cs_pin = OutputDevice(cs_pin)
        self.cs_pin.off()

        # Optional reset pin
        self.reset_pin = OutputDevice(reset_pin) if reset_pin is not None else None
        if self.reset_pin:
            self.reset_pin.on()  # active low

        # State
        self.extended = False
        self.graphics = False
        self.old_buffer: Bitmap | None = None

        self.initialize()

    # ----------------------
    # Low-level SPI helpers
    # ----------------------
    def _send(self, byte, is_data=False):
        """Send a single byte (cmd or data)."""
        if not isinstance(byte, int):
            byte = byte.item()

        sync_byte = 0xF8 | (0x02 if is_data else 0x00)
        upper = byte & 0xF0
        lower = (byte << 4) & 0xF0

        self.cs_pin.on()
        self.spi.writebytes([sync_byte, upper, lower])
        self.cs_pin.off()
        time.sleep(1e-4)

    def _send_cmd(self, b):
        self._send(b, False)

    def _send_data(self, b):
        self._send(b, True)

    # ----------------------
    # Reset / Initialization
    # ----------------------
    def reset(self):
        if self.reset_pin:
            self.reset_pin.off()
            time.sleep(0.01)
            self.reset_pin.on()
            time.sleep(0.01)

    def initialize(self):
        """Basic init in text mode."""
        self.reset()
        self._send_cmd(0x30)  # Function set (8-bit, basic)
        self._send_cmd(0x0C)  # Display ON, cursor/blink OFF
        self.clear()
        self._send_cmd(0x06)  # Entry mode: increment

    # ----------------------
    # Instruction sets
    # ----------------------
    def set_instruction_set(self, extended=False, graphics=False):
        self.extended = extended
        self._send_cmd(0x30 | (extended << 2))
        if graphics:
            if not extended:
                raise ValueError("Graphics mode requires extended set")
            self.graphics = True
            self._send_cmd(0x30 | (1 << 2) | (1 << 1))

    # ----------------------
    # Text mode
    # ----------------------
    def clear(self):
        self._send_cmd(0x01)
        time.sleep(0.01)

    def set_ddram_address(self, addr):
        self._send_cmd((addr & 0x7F) | 0x80)

    def write_str(self, s):
        for c in s:
            self._send_data(ord(c))

    # ----------------------
    # Graphics mode
    # ----------------------
    def set_gdram_address(self, row, col_word):
        """
        row: 0–63
        col_word: 0–15 (each word = 16 pixels)
        """
        if not (0 <= row < self.height):
            raise ValueError("Row out of range")
        if not (0 <= col_word < self.width // 16):
            raise ValueError("Column out of range")

        # refer https://dk7ih.de/interfacing-an-lcd12864-st7920-controller-to-a-microcontroller/
        if row >= 32:
            row -= 32
            col_word += 8

        self._send_cmd(0x80 | row)
        self._send_cmd(0x80 | col_word)

    def write_gdram_word(self, word16):
        self._send_data((word16 >> 8) & 0xFF)
        self._send_data(word16 & 0xFF)

    def clear_gdram(self):
        for row in range(64):
            self.set_gdram_address(row, 0)
            for col in range(8):  # 128/16 = 8 words
                self.write_gdram_word(0x0000)
        self.old_buffer = None

    def write_gdram_buffer(self, bmp):
        """
        Writes Bitmap.words (uint16) to the LCD.
        Only updates words that changed since last call.
        """
        for row in range(bmp.height):
            for col_word in range(bmp.width // 16):
                new_word = bmp.words[row, col_word]

                if self.old_buffer is not None:
                    old_word = self.old_buffer.words[row, col_word]
                else:
                    old_word = None

                if new_word != old_word:
                    self.set_gdram_address(row, col_word)
                    self.write_gdram_word(int(new_word))

        self.old_buffer = deepcopy(bmp)

    def close(self):
        self.spi.close()
        self.cs_pin.close()
        if self.reset_pin:
            self.reset_pin.close()


if __name__ == "__main__":
    lcd = ST7920(13, reset_pin=26)

    # --- text mode ---
    lcd.set_ddram_address(0x80)
    lcd.write_str("Hello world!")
    lcd.set_ddram_address(0x90)
    lcd.write_str("Line 2")

