from __future__ import annotations

import logging

import pytest

from room_climate import wifi_provisioner
from room_climate.provision_outcome import ProvisionOutcome
from room_climate.wifi_provisioner import WifiProvisioner


class RecordingLogger(logging.Logger):
    """A logger that keeps the messages it was asked to write."""

    def __init__(self) -> None:
        super().__init__("test")
        self.messages: list[str] = []

    def log(self, level: int, msg: str, *args: object, **kwargs: object) -> None:
        self.messages.append(str(msg))


class FakeConnection:
    """Minimal pyserial-like connection for the provisioner tests.

    The provisioner reboots the chip once before sending and once again to
    verify persistence. On the second reset the queued lines are replaced with
    ``stored_lines``, which models a real reboot that loads the record from
    flash.
    """

    def __init__(
        self, lines: list[bytes], stored_lines: list[bytes] | None = None
    ) -> None:
        self._lines = list(lines)
        self._stored_lines = list(stored_lines) if stored_lines is not None else None
        self.written = bytearray()
        self.dtr = True
        self._rts = True
        self.timeout = 0.0
        self._resets = 0

    @property
    def rts(self) -> bool:
        return self._rts

    @rts.setter
    def rts(self, value: bool) -> None:
        if self._rts and not value:
            self._on_reset()
        self._rts = value

    def _on_reset(self) -> None:
        self._resets += 1
        if self._resets >= 2 and self._stored_lines is not None:
            self._lines = list(self._stored_lines)

    def readline(self) -> bytes:
        if self._lines:
            return self._lines.pop(0)
        return b""

    def write(self, data: bytes) -> int:
        self.written.extend(data)
        return len(data)

    def flush(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wifi_provisioner.time, "sleep", lambda _seconds: None)


def _provisioner(connection: FakeConnection) -> tuple[WifiProvisioner, RecordingLogger]:
    logger = RecordingLogger()
    provisioner = WifiProvisioner(
        connection,
        ready_timeout=0.05,
        confirm_timeout=0.05,
        verify_timeout=0.05,
        logger=logger,
    )
    return provisioner, logger


def test_provision_saves_credentials() -> None:
    connection = FakeConnection(
        [
            b"room-climate firmware (WiFi) starting\n",
            b"wifi: no credentials stored\n",
            b"wifi: send 'wifi <ssid>' then 'pass <password>'\n",
            b"wifi: ssid accepted\n",
            b"wifi: password accepted\n",
            b"wifi: credentials saved for ssid=HomeNet-2.4G\n",
        ],
        stored_lines=[
            b"room-climate firmware (WiFi) starting\n",
            b"wifi: stored credentials found for ssid=HomeNet-2.4G\n",
        ],
    )
    provisioner, logger = _provisioner(connection)

    outcome = provisioner.provision("HomeNet-2.4G", "example-pass")

    assert outcome is ProvisionOutcome.SAVED
    assert b"wifi HomeNet-2.4G\n" in connection.written
    assert b"pass example-pass\n" in connection.written
    assert any("Rebooting to verify" in message for message in logger.messages)
    assert all("example-pass" not in message for message in logger.messages)


def test_provision_confirms_persistence_without_save_line() -> None:
    connection = FakeConnection(
        [
            b"wifi: no credentials stored\n",
            b"wifi: ssid accepted\n",
            b"wifi: password accepted\n",
        ],
        stored_lines=[b"wifi: stored credentials found for ssid=net\n"],
    )
    provisioner, _ = _provisioner(connection)

    assert provisioner.provision("net", "pw") is ProvisionOutcome.SAVED


def test_provision_reports_save_failure() -> None:
    connection = FakeConnection(
        [
            b"wifi: no credentials stored\n",
            b"wifi: could not save credentials: erase failed\n",
        ]
    )
    provisioner, _ = _provisioner(connection)

    assert provisioner.provision("net", "pw") is ProvisionOutcome.NOT_SAVED


def test_provision_without_confirmation_retries() -> None:
    connection = FakeConnection([b"wifi: no credentials stored\n"])
    provisioner, _ = _provisioner(connection)

    assert provisioner.provision("net", "pw") is ProvisionOutcome.NO_CONFIRMATION
    assert connection.written.count(b"pass pw\n") == wifi_provisioner.MAX_ATTEMPTS


def test_provision_tolerates_non_utf8_noise() -> None:
    connection = FakeConnection(
        [
            b"\xd1\x7f\x02 power-on noise\n",
            b"wifi: no credentials stored\n",
            b"wifi: ssid accepted\n",
            b"wifi: password accepted\n",
            b"wifi: credentials saved for ssid=net\n",
        ],
        stored_lines=[b"wifi: stored credentials found for ssid=net\n"],
    )
    provisioner, logger = _provisioner(connection)

    assert provisioner.provision("net", "pw") is ProvisionOutcome.SAVED
    assert any("(hex)>" in message for message in logger.messages)
