"""Liveness assessment of the attached CO2 sensor."""

from __future__ import annotations

import time

from .liveness_report import LivenessReport
from .liveness_verdict import LivenessVerdict
from .mh_z19_client import MhZ19Client
from .mh_z19_response import MhZ19Response

DEFAULT_SAMPLE_COUNT = 5
DEFAULT_SAMPLE_INTERVAL_SECONDS = 2.0
MIN_PLAUSIBLE_CO2_PPM = 100
MAX_PLAUSIBLE_CO2_PPM = 10000
PINNED_LOW_CO2_PPM = 0
PINNED_HIGH_CO2_PPM = 5000
MIN_PLAUSIBLE_TEMPERATURE_CELSIUS = -20
MAX_PLAUSIBLE_TEMPERATURE_CELSIUS = 70


class SensorLiveness:
    """Reads several samples and decides whether the sensor still works."""

    def __init__(
        self,
        client: MhZ19Client,
        sample_count: int = DEFAULT_SAMPLE_COUNT,
        sample_interval_seconds: float = DEFAULT_SAMPLE_INTERVAL_SECONDS,
    ) -> None:
        """Store the client and sampling parameters."""
        self._client = client
        self._sample_count = sample_count
        self._sample_interval_seconds = sample_interval_seconds

    def assess(self) -> LivenessReport:
        """Sample the sensor and return its liveness report."""
        samples = self._collect_samples()
        diagnostics = self._client.read_pre_clamp_measurement()
        return self._build_report(samples, diagnostics)

    def _collect_samples(self) -> list[MhZ19Response | None]:
        """Read the configured number of measurement samples."""
        samples: list[MhZ19Response | None] = []
        for index in range(self._sample_count):
            samples.append(self._client.read_measurement())
            if index < self._sample_count - 1:
                time.sleep(self._sample_interval_seconds)
        return samples

    def _build_report(
        self,
        samples: list[MhZ19Response | None],
        diagnostics: MhZ19Response | None,
    ) -> LivenessReport:
        """Turn raw samples and diagnostics into a liveness report."""
        valid = [sample for sample in samples if sample is not None]
        co2_values = [sample.co2_ppm for sample in valid]
        if not valid:
            return self._unreachable_report(len(samples))
        dead_reasons = self._dead_reasons(valid, co2_values, diagnostics)
        degraded_reasons = self._degraded_reasons(valid, co2_values)
        return self._compose_report(
            len(samples), valid, co2_values, diagnostics, dead_reasons, degraded_reasons
        )

    def _unreachable_report(self, sample_count: int) -> LivenessReport:
        """Return a report for a sensor that answered with nothing valid."""
        return LivenessReport(
            verdict=LivenessVerdict.UNREACHABLE,
            sample_count=sample_count,
            valid_sample_count=0,
            co2_min=None,
            co2_max=None,
            temperature_celsius=None,
            pre_clamp_co2_ppm=None,
            minimum_light_adc=None,
            reasons=("No valid response frames; sensor may be unpowered or dead",),
        )

    @staticmethod
    def _dead_reasons(
        valid: list[MhZ19Response],
        co2_values: list[int],
        diagnostics: MhZ19Response | None,
    ) -> list[str]:
        """Return reasons that prove the sensing element does not work."""
        reasons: list[str] = []
        if diagnostics is not None and diagnostics.minimum_light_adc == 0:
            reasons.append(
                "Minimum light ADC is zero; IR lamp or photo path is not responding"
            )
        if all(value <= PINNED_LOW_CO2_PPM for value in co2_values):
            reasons.append("All readings are pinned at the lower bound")
        if all(value >= PINNED_HIGH_CO2_PPM for value in co2_values):
            reasons.append("All readings are pinned at the upper bound")
        return reasons

    @staticmethod
    def _degraded_reasons(
        valid: list[MhZ19Response], co2_values: list[int]
    ) -> list[str]:
        """Return reasons that only warn about a degraded sensor."""
        reasons: list[str] = []
        if any(value < MIN_PLAUSIBLE_CO2_PPM for value in co2_values):
            reasons.append("Some readings are below the plausible CO2 range")
        if any(value > MAX_PLAUSIBLE_CO2_PPM for value in co2_values):
            reasons.append("Some readings are above the plausible CO2 range")
        temperatures = [sample.temperature_celsius for sample in valid]
        if all(
            temperature < MIN_PLAUSIBLE_TEMPERATURE_CELSIUS
            or temperature > MAX_PLAUSIBLE_TEMPERATURE_CELSIUS
            for temperature in temperatures
        ):
            reasons.append("Internal temperature is outside the plausible range")
        if len(set(co2_values)) == 1 and co2_values[0] not in (
            PINNED_LOW_CO2_PPM,
            PINNED_HIGH_CO2_PPM,
        ):
            reasons.append("Readings never change; verify airflow over the sensor")
        return reasons

    @staticmethod
    def _compose_report(
        sample_count: int,
        valid: list[MhZ19Response],
        co2_values: list[int],
        diagnostics: MhZ19Response | None,
        dead_reasons: list[str],
        degraded_reasons: list[str],
    ) -> LivenessReport:
        """Combine all findings into the final liveness report."""
        if dead_reasons:
            verdict = LivenessVerdict.DEAD
            reasons = tuple(dead_reasons + degraded_reasons)
        elif degraded_reasons:
            verdict = LivenessVerdict.DEGRADED
            reasons = tuple(degraded_reasons)
        else:
            verdict = LivenessVerdict.ALIVE
            reasons = ("Sensor responds with plausible measurements",)
        return LivenessReport(
            verdict=verdict,
            sample_count=sample_count,
            valid_sample_count=len(valid),
            co2_min=min(co2_values),
            co2_max=max(co2_values),
            temperature_celsius=valid[-1].temperature_celsius,
            pre_clamp_co2_ppm=(
                diagnostics.pre_clamp_co2_ppm if diagnostics is not None else None
            ),
            minimum_light_adc=(
                diagnostics.minimum_light_adc if diagnostics is not None else None
            ),
            reasons=reasons,
        )
