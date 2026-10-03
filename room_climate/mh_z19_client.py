"""High-level MH-Z19 sensor client built on the UART protocol."""

from __future__ import annotations

from .mh_z19_protocol import (
    ABC_OFF_VALUE,
    ABC_ON_VALUE,
    COMMAND_AUTO_BASELINE_CORRECTION,
    COMMAND_CALIBRATE_SPAN,
    COMMAND_CALIBRATE_ZERO,
    COMMAND_READ_AUTO_BASELINE_CORRECTION,
    COMMAND_READ_CO2,
    COMMAND_READ_FIRMWARE_VERSION,
    COMMAND_READ_PRE_CLAMP_CO2,
    COMMAND_READ_RANGE,
    FRAME_LENGTH,
    SPAN_REFERENCE_PPM,
    MhZ19Protocol,
)
from .mh_z19_response import MhZ19Response
from .serial_transport import SerialTransport


class MhZ19Client:
    """Sends MH-Z19 commands over a transport and returns parsed responses."""

    def __init__(self, transport: SerialTransport) -> None:
        """Store the transport used for command exchanges."""
        self._transport = transport

    def _request(self, command: int, data: bytes = b"") -> MhZ19Response | None:
        """Send one command and parse its response frame."""
        request = MhZ19Protocol.build_command(command, data)
        frame = self._transport.exchange(request, FRAME_LENGTH)
        return MhZ19Protocol.parse_response(frame, command)

    def read_measurement(self) -> MhZ19Response | None:
        """Read the final CO2 concentration and temperature (0x86)."""
        return self._request(COMMAND_READ_CO2)

    def read_pre_clamp_measurement(self) -> MhZ19Response | None:
        """Read raw light and CO2 diagnostics for liveness analysis (0x85)."""
        return self._request(COMMAND_READ_PRE_CLAMP_CO2)

    def read_firmware_version(self) -> str | None:
        """Read the firmware version string (0xA0)."""
        response = self._request(COMMAND_READ_FIRMWARE_VERSION)
        return response.firmware_version if response is not None else None

    def read_detection_range(self) -> int | None:
        """Read the configured detection range in ppm (0x9B)."""
        response = self._request(COMMAND_READ_RANGE)
        return response.detection_range_ppm if response is not None else None

    def read_auto_baseline_correction(self) -> bool | None:
        """Read whether automatic baseline correction is enabled (0x7D)."""
        response = self._request(COMMAND_READ_AUTO_BASELINE_CORRECTION)
        return response.abc_enabled if response is not None else None

    def set_auto_baseline_correction(self, enabled: bool) -> bool:
        """Enable or disable automatic baseline correction (0x79)."""
        value = ABC_ON_VALUE if enabled else ABC_OFF_VALUE
        response = self._request(COMMAND_AUTO_BASELINE_CORRECTION, bytes([value]))
        return response is not None

    def calibrate_zero_point(self) -> bool:
        """Calibrate the zero point against a 400 ppm reference (0x87)."""
        return self._request(COMMAND_CALIBRATE_ZERO) is not None

    def calibrate_span_point(self, reference_ppm: int = SPAN_REFERENCE_PPM) -> bool:
        """Calibrate the span point against a reference gas (0x88)."""
        data = reference_ppm.to_bytes(2, "big")
        return self._request(COMMAND_CALIBRATE_SPAN, data) is not None
