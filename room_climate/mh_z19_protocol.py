"""MH-Z19 UART protocol framing and checksum helpers."""

from __future__ import annotations

from .mh_z19_response import MhZ19Response

START_BYTE = 0xFF
SENSOR_ADDRESS = 0x01
FRAME_LENGTH = 9
COMMAND_PARAMETER_COUNT = 5

COMMAND_READ_CO2 = 0x86
COMMAND_CALIBRATE_ZERO = 0x87
COMMAND_CALIBRATE_SPAN = 0x88
COMMAND_AUTO_BASELINE_CORRECTION = 0x79
COMMAND_READ_AUTO_BASELINE_CORRECTION = 0x7D
COMMAND_READ_FIRMWARE_VERSION = 0xA0
COMMAND_READ_RANGE = 0x9B
COMMAND_READ_PRE_CLAMP_CO2 = 0x85

ABC_ON_VALUE = 0xA0
ABC_OFF_VALUE = 0x00
SPAN_REFERENCE_PPM = 2000


class MhZ19Protocol:
    """Builds and parses 9-byte MH-Z19 operation mode 0 frames."""

    @staticmethod
    def checksum(payload: bytes) -> int:
        """Return the MH-Z19 checksum for the given payload bytes."""
        return (0xFF - (sum(payload) % 0x100) + 1) & 0xFF

    @classmethod
    def build_command(cls, command: int, data: bytes = b"") -> bytes:
        """Build a 9-byte command frame for the given command code."""
        parameters = data[:COMMAND_PARAMETER_COUNT].ljust(
            COMMAND_PARAMETER_COUNT, b"\x00"
        )
        body = bytes([START_BYTE, SENSOR_ADDRESS, command]) + parameters
        return body + bytes([cls.checksum(body[1:])])

    @classmethod
    def parse_response(
        cls, frame: bytes, expected_command: int
    ) -> MhZ19Response | None:
        """Parse a response frame, returning None when it is malformed."""
        if len(frame) != FRAME_LENGTH:
            return None
        if frame[0] != START_BYTE or frame[1] != expected_command:
            return None
        if frame[-1] != cls.checksum(frame[1:-1]):
            return None
        return MhZ19Response(command=frame[1], data=frame[2:-1])
