"""Tests for the long-running monitoring session."""

from __future__ import annotations

from collections.abc import Callable

from room_climate.mh_z19_response import MhZ19Response
from room_climate.monitoring_session import MonitoringSession


class FakeClient:
    """Client stub returning queued responses or raising a prepared error."""

    def __init__(
        self,
        responses: list[MhZ19Response | None],
        error: OSError | None = None,
    ) -> None:
        """Store the queued responses and optional read error."""
        self._responses = list(responses)
        self._error = error

    def read_measurement(self) -> MhZ19Response | None:
        """Return the next queued response, raise, or return None."""
        if self._error is not None:
            raise self._error
        if not self._responses:
            return None
        return self._responses.pop(0)


class FakeLogger:
    """Logger stub capturing formatted messages."""

    def __init__(self) -> None:
        """Initialise the message list."""
        self.messages: list[str] = []

    def info(self, message: str, *args: object) -> None:
        """Record an info message."""
        self.messages.append(message % args if args else message)

    def warning(self, message: str, *args: object) -> None:
        """Record a warning message."""
        self.messages.append(message % args if args else message)

    def error(self, message: str, *args: object) -> None:
        """Record an error message."""
        self.messages.append(message % args if args else message)


def measurement(co2_ppm: int, temperature_celsius: int = 22) -> MhZ19Response:
    """Build a synthetic 0x86 measurement response."""
    data = (
        co2_ppm.to_bytes(2, "big") + bytes([temperature_celsius + 40]) + b"\x00\x00\x00"
    )
    return MhZ19Response(command=0x86, data=data)


def virtual_clock() -> tuple[Callable[[], float], Callable[[float], None]]:
    """Return a clock and a sleeper that advances the clock."""
    now = [0.0]

    def clock() -> float:
        return now[0]

    def sleeper(seconds: float) -> None:
        now[0] += seconds

    return clock, sleeper


def build_session(
    client: FakeClient, logger: FakeLogger, duration_seconds: float
) -> MonitoringSession:
    """Build a session driven by a virtual clock."""
    clock, sleeper = virtual_clock()
    return MonitoringSession(
        client,
        logger,
        interval_seconds=1,
        duration_seconds=duration_seconds,
        clock=clock,
        sleeper=sleeper,
    )


def sample_messages(logger: FakeLogger) -> list[str]:
    """Return the recorded per-sample lines."""
    return [message for message in logger.messages if message.startswith("sample ")]


def test_session_samples_until_duration() -> None:
    client = FakeClient([measurement(800), measurement(810), measurement(820)])
    logger = FakeLogger()

    code = build_session(client, logger, duration_seconds=3).run()

    assert code == 0
    assert len(sample_messages(logger)) == 3
    assert any("Monitoring finished: 3 samples" in m for m in logger.messages)


def test_session_skips_missing_frames() -> None:
    client = FakeClient([None, measurement(800), None, measurement(810)])
    logger = FakeLogger()

    build_session(client, logger, duration_seconds=4).run()

    assert len(sample_messages(logger)) == 2
    assert any("Monitoring finished: 2 samples" in m for m in logger.messages)


def test_session_survives_read_errors() -> None:
    client = FakeClient([], error=OSError("device disconnected"))
    logger = FakeLogger()

    code = build_session(client, logger, duration_seconds=2).run()

    assert code == 0
    assert sample_messages(logger) == []
    assert any("Read failed" in m for m in logger.messages)
