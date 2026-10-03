"""Discovery of the serial port that hosts the CO2 sensor."""

from __future__ import annotations

from serial.tools import list_ports

DEFAULT_PORT = "/dev/ttyUSB0"
USB_PORT_MARKERS = ("ttyUSB", "ttyACM", "usbserial", "usbmodem")
NO_PORTS_DESCRIPTION = "none"


class SerialPortFinder:
    """Resolves the serial port to use, preferring USB-UART adapters."""

    def resolve(self, explicit_port: str | None = None) -> str:
        """Return the requested port or the first detected USB serial port."""
        if explicit_port:
            return explicit_port
        detected = self._detect_usb_port()
        return detected if detected is not None else DEFAULT_PORT

    def available_ports(self) -> list[str]:
        """Return every serial port the system reports."""
        try:
            return [port.device for port in list_ports.comports()]
        except OSError:
            return []

    def describe(self) -> str:
        """Return a human-readable summary of the available ports."""
        ports = self.available_ports()
        if not ports:
            return NO_PORTS_DESCRIPTION
        return ", ".join(ports)

    def _detect_usb_port(self) -> str | None:
        """Return the first detected USB serial port, if any."""
        for port in self.available_ports():
            if any(marker in port for marker in USB_PORT_MARKERS):
                return port
        return None
