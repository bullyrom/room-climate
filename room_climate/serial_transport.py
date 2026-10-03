"""Serial port transport for talking to the CO2 sensor."""

from __future__ import annotations

import serial

DEFAULT_READ_TIMEOUT_SECONDS = 1.0


class SerialTransport:
    """Owns a pyserial connection and performs request/response exchanges."""

    def __init__(
        self,
        port: str,
        baud_rate: int,
        read_timeout: float = DEFAULT_READ_TIMEOUT_SECONDS,
    ) -> None:
        """Open the serial port using the given parameters."""
        self._port = port
        self._baud_rate = baud_rate
        self._connection = serial.Serial(
            port=port, baudrate=baud_rate, timeout=read_timeout
        )

    @property
    def port(self) -> str:
        """Return the open serial port name."""
        return self._port

    @property
    def baud_rate(self) -> int:
        """Return the configured baud rate."""
        return self._baud_rate

    def exchange(self, request: bytes, response_length: int) -> bytes:
        """Write a request and read a single response frame."""
        self._connection.reset_input_buffer()
        self._connection.write(request)
        return self._connection.read(response_length)

    def close(self) -> None:
        """Close the serial connection."""
        self._connection.close()

    def __enter__(self) -> "SerialTransport":
        """Return self so the transport can be used as a context manager."""
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        """Close the serial connection on context exit."""
        self.close()
