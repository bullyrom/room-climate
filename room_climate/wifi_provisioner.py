"""Wi-Fi credential provisioning over the ESP32 USB serial console.

The host must drive the ESP32 auto-reset lines (DTR/RTS) itself: after a flash
the chip can still be in the serial bootloader stub, and a plain serial port
open does not start the application. This class resets the chip into the app,
waits for the firmware's provisioning prompt and then writes the credentials.

Persistence is confirmed by *fact*, not by console line ordering: after sending
the credentials the chip is rebooted and the host waits for the firmware's
`stored credentials found for ssid=...` boot line, which proves the record was
read back from flash. A lost or interleaved `credentials saved` line therefore
no longer looks like a failure. The password is never logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from .provision_outcome import ProvisionOutcome

DEFAULT_BAUD_RATE = 115_200
DEFAULT_READY_TIMEOUT_SECONDS = 20.0
DEFAULT_CONFIRM_TIMEOUT_SECONDS = 20.0
DEFAULT_VERIFY_TIMEOUT_SECONDS = 20.0
LINE_POLL_SECONDS = 0.5
RESET_PULSE_SECONDS = 0.1
RESET_SETTLE_SECONDS = 0.5
MAX_ATTEMPTS = 2

PROMPT_MARKERS = ("no credentials stored", "send 'wifi")
SAVED_MARKER = "credentials saved"
STORED_MARKER = "stored credentials found"
SAVE_FAILURE_MARKERS = (
    "could not save",
    "credentials not saved",
    "no nvs partition",
    "invalid or too long",
)


class WifiProvisioner:
    """Resets the device, sends the credentials and verifies the save.

    The serial connection is supplied by the caller (already open) so the
    reset/read/write sequence can be exercised against a fake connection.
    """

    def __init__(
        self,
        connection: object,
        ready_timeout: float = DEFAULT_READY_TIMEOUT_SECONDS,
        confirm_timeout: float = DEFAULT_CONFIRM_TIMEOUT_SECONDS,
        verify_timeout: float = DEFAULT_VERIFY_TIMEOUT_SECONDS,
        logger: logging.Logger | None = None,
    ) -> None:
        """Store the connection, the timeouts and the optional logger."""
        self._connection = connection
        self._ready_timeout = ready_timeout
        self._confirm_timeout = confirm_timeout
        self._verify_timeout = verify_timeout
        self._logger = logger

    def provision(self, ssid: str, password: str) -> ProvisionOutcome:
        """Store the credentials and confirm them by reading them back.

        The confirmation is the fact that a reboot finds the credentials in
        flash, so it does not depend on the order or completeness of the
        console lines that report the save.
        """
        self._reset_into_app()
        if self._wait_for_prompt():
            self._log("Device is ready for Wi-Fi credentials")
        else:
            self._log("No provisioning prompt seen; sending anyway", logging.WARNING)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            self._send_credentials(ssid, password)
            outcome = self._read_save_result()
            if outcome is ProvisionOutcome.NOT_SAVED:
                return outcome
            if self._verify_stored(ssid):
                return ProvisionOutcome.SAVED
            self._log(
                f"No stored-credential confirmation on attempt {attempt}/{MAX_ATTEMPTS}",
                logging.WARNING,
            )
        return ProvisionOutcome.NO_CONFIRMATION

    def _reset_into_app(self) -> None:
        """Pulse DTR/RTS so the chip runs the application after the reset."""
        self._set_dtr(False)  # GPIO0 high: normal boot
        self._set_rts(True)  # EN low: chip in reset
        time.sleep(RESET_PULSE_SECONDS)
        self._set_rts(False)  # EN high: boot the application
        time.sleep(RESET_SETTLE_SECONDS)

    def _set_dtr(self, level: bool) -> None:
        """Set the DTR line, ignoring a connection that does not support it."""
        try:
            self._connection.dtr = level
        except (AttributeError, OSError):
            pass

    def _set_rts(self, level: bool) -> None:
        """Set the RTS line, ignoring a connection that does not support it."""
        try:
            self._connection.rts = level
        except (AttributeError, OSError):
            pass

    def _wait_for_prompt(self) -> bool:
        """Return True when the firmware asks for credentials."""
        return self._wait_for(self._ready_timeout, _is_prompt) is not None

    def _read_save_result(self) -> ProvisionOutcome | None:
        """Read the device's save result, or None when none was reported.

        This is only an early signal: a `credentials saved` line speeds up the
        diagnosis, but the authoritative answer comes from `_verify_stored`.
        """
        deadline = time.monotonic() + self._confirm_timeout
        while time.monotonic() < deadline:
            line = self._read_line(deadline - time.monotonic())
            if line is None:
                continue
            self._log_device_line(line)
            outcome = _classify_confirmation(line)
            if outcome is not None:
                return outcome
        return None

    def _verify_stored(self, ssid: str) -> bool:
        """Reboot and confirm the credentials persisted by reading them back.

        The firmware prints `stored credentials found for ssid=...` when it
        loads the record from flash at boot. Seeing that line is proof by fact:
        it cannot be produced by a lost, reordered or interleaved save line.
        """
        self._log("Rebooting to verify the stored credentials")
        self._reset_into_app()
        found = self._wait_for(
            self._verify_timeout, lambda line: _is_stored_credentials(line, ssid)
        )
        return found is not None

    def _wait_for(self, timeout: float, predicate: Callable[[str], bool]) -> str | None:
        """Read device lines until one satisfies the predicate or time runs out."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            line = self._read_line(deadline - time.monotonic())
            if line is None:
                continue
            self._log_device_line(line)
            if predicate(line):
                return line
        return None

    def _read_line(self, remaining: float) -> str | None:
        """Read one line from the connection within the remaining time."""
        if remaining <= 0:
            return None
        self._connection.timeout = min(LINE_POLL_SECONDS, remaining)
        try:
            raw = self._connection.readline()
        except (OSError, UnicodeDecodeError):
            return None
        if not raw:
            return None
        return self._decode_line(raw).rstrip("\r\n")

    def _decode_line(self, raw: bytes) -> str:
        """Decode device bytes, tolerating non-UTF-8 noise.

        Serial output can contain garbage (power-on noise, wrong baud, a
        truncated frame). Invalid UTF-8 is logged as hex and decoded as
        latin-1 so a single bad byte can never crash the provisioner.
        """
        if isinstance(raw, str):
            return raw
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            self._log(f"device (hex)> {raw.hex(' ')}", logging.DEBUG)
            return raw.decode("latin-1", errors="replace")

    def _send_credentials(self, ssid: str, password: str) -> None:
        """Write the two provisioning lines to the device."""
        self._connection.write(f"wifi {ssid}\n".encode())
        self._connection.write(f"pass {password}\n".encode())
        self._connection.flush()

    def _log(self, message: str, level: int = logging.INFO) -> None:
        """Log a message through the optional logger."""
        if self._logger is not None:
            self._logger.log(level, message)

    def _log_device_line(self, line: str) -> None:
        """Log a device line (never the credentials the host sent)."""
        self._log(f"device> {line}")


def _is_prompt(line: str) -> bool:
    """Return True when the line is the firmware provisioning prompt."""
    lowered = line.lower()
    return any(marker in lowered for marker in PROMPT_MARKERS)


def _classify_confirmation(line: str) -> ProvisionOutcome | None:
    """Map a device line to a confirmation outcome, if it is one."""
    lowered = line.lower()
    if SAVED_MARKER in lowered:
        return ProvisionOutcome.SAVED
    if any(marker in lowered for marker in SAVE_FAILURE_MARKERS):
        return ProvisionOutcome.NOT_SAVED
    return None


def _is_stored_credentials(line: str, ssid: str) -> bool:
    """Return True when the boot line proves the credentials are in flash."""
    lowered = line.lower()
    return STORED_MARKER in lowered and ssid.lower() in lowered
