"""Parsed MH-Z19 response frame value object."""

from __future__ import annotations

from dataclasses import dataclass

TEMPERATURE_OFFSET_CELSIUS = 40
TWO_BYTES = 2
FIRMWARE_VERSION_LENGTH = 4
DETECTION_RANGE_LENGTH = 4
ABC_STATUS_INDEX = 5
TEMPERATURE_INDEX = 2


@dataclass(frozen=True)
class MhZ19Response:
    """Immutable, checksum-verified MH-Z19 response frame.

    The ``data`` payload is the six response bytes that follow the command
    byte (``r2..r7`` in the MH-Z19 operation mode 0 protocol).
    """

    command: int
    data: bytes

    def _first_word(self) -> int:
        """Return the first two payload bytes interpreted as big-endian."""
        return int.from_bytes(self.data[:TWO_BYTES], "big")

    @property
    def co2_ppm(self) -> int:
        """Return the final CO2 concentration in ppm (command 0x86)."""
        return self._first_word()

    @property
    def temperature_celsius(self) -> int:
        """Return the internal temperature in Celsius (command 0x86)."""
        return self.data[TEMPERATURE_INDEX] - TEMPERATURE_OFFSET_CELSIUS

    @property
    def pre_clamp_co2_ppm(self) -> int:
        """Return the CO2 level before clamping (command 0x85)."""
        return self._first_word()

    @property
    def minimum_light_adc(self) -> int:
        """Return the minimum light ADC value (command 0x85)."""
        return int.from_bytes(self.data[4:6], "big")

    @property
    def firmware_version(self) -> str:
        """Return the firmware version string (command 0xA0)."""
        return self.data[:FIRMWARE_VERSION_LENGTH].decode("ascii", errors="replace")

    @property
    def detection_range_ppm(self) -> int:
        """Return the configured detection range in ppm (command 0x9B)."""
        return int.from_bytes(self.data[:DETECTION_RANGE_LENGTH], "big")

    @property
    def abc_enabled(self) -> bool:
        """Return the automatic baseline correction flag (command 0x7D)."""
        return self.data[ABC_STATUS_INDEX] != 0
