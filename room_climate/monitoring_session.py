"""Long-running periodic CO2 monitoring session."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime

import serial

from .mh_z19_client import MhZ19Client
from .monitoring_sample import MonitoringSample

DEFAULT_INTERVAL_SECONDS = 10.0
UNLIMITED_DURATION_SECONDS = 0.0
SAMPLE_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
NO_FRAME_MESSAGE = "No valid frame; skipping this sample"


class MonitoringSession:
    """Samples the sensor periodically and logs every measurement.

    The loop runs until the duration expires (when greater than zero) or until
    it is interrupted by the user. A lost serial response or a read error only
    skips the current sample, so a long run keeps going.
    """

    def __init__(
        self,
        client: MhZ19Client,
        logger: logging.Logger,
        interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
        duration_seconds: float = UNLIMITED_DURATION_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        """Store the client, logger and loop timing helpers."""
        self._client = client
        self._logger = logger
        self._interval_seconds = interval_seconds
        self._duration_seconds = duration_seconds
        self._clock = clock
        self._sleeper = sleeper
        self._samples: list[MonitoringSample] = []

    def run(self) -> int:
        """Run the monitoring loop and log a summary at the end."""
        started = self._clock()
        index = 0
        self._logger.info(
            "Monitoring started: interval=%ss duration=%ss",
            self._interval_seconds,
            self._duration_seconds,
        )
        while not self._expired(started):
            index += 1
            sample = self._take_sample(index)
            if sample is not None:
                self._samples.append(sample)
            if self._expired(started):
                break
            self._sleeper(self._interval_seconds)
        self._log_summary()
        return 0

    def _take_sample(self, index: int) -> MonitoringSample | None:
        """Read one measurement and log it, returning None when unavailable."""
        try:
            response = self._client.read_measurement()
        except (serial.SerialException, OSError) as error_:
            self._logger.error("Read failed: %s", error_)
            return None
        if response is None:
            self._logger.warning(NO_FRAME_MESSAGE)
            return None
        sample = MonitoringSample(
            timestamp=datetime.now().strftime(SAMPLE_TIMESTAMP_FORMAT),
            co2_ppm=response.co2_ppm,
            temperature_celsius=response.temperature_celsius,
        )
        self._logger.info(
            "sample %s co2=%s temperature=%s",
            index,
            sample.co2_ppm,
            sample.temperature_celsius,
        )
        return sample

    def _expired(self, started: float) -> bool:
        """Return True when the configured duration has elapsed."""
        if self._duration_seconds <= UNLIMITED_DURATION_SECONDS:
            return False
        return self._clock() - started >= self._duration_seconds

    def _log_summary(self) -> None:
        """Log how many samples were taken and their CO2 range."""
        if not self._samples:
            self._logger.info("Monitoring finished: no valid samples")
            return
        co2_values = [sample.co2_ppm for sample in self._samples]
        average = sum(co2_values) / len(co2_values)
        self._logger.info(
            "Monitoring finished: %s samples, co2 min=%s max=%s avg=%.1f ppm",
            len(self._samples),
            min(co2_values),
            max(co2_values),
            average,
        )
