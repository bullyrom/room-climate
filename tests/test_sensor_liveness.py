"""Tests for the CO2 sensor liveness assessment."""

from __future__ import annotations

from room_climate.liveness_report import LivenessReport
from room_climate.liveness_verdict import LivenessVerdict
from room_climate.mh_z19_response import MhZ19Response
from room_climate.sensor_liveness import SensorLiveness


class FakeClient:
    """Minimal MH-Z19 client stub returning prepared responses."""

    def __init__(
        self,
        samples: list[MhZ19Response | None],
        diagnostics: MhZ19Response | None = None,
    ) -> None:
        """Store the queued samples and diagnostics response."""
        self._samples = list(samples)
        self._diagnostics = diagnostics

    def read_measurement(self) -> MhZ19Response | None:
        """Return the next queued measurement or None when exhausted."""
        if not self._samples:
            return None
        return self._samples.pop(0)

    def read_pre_clamp_measurement(self) -> MhZ19Response | None:
        """Return the prepared diagnostics response."""
        return self._diagnostics


def measurement(co2_ppm: int, temperature_celsius: int = 22) -> MhZ19Response:
    """Build a synthetic 0x86 measurement response."""
    data = (
        co2_ppm.to_bytes(2, "big") + bytes([temperature_celsius + 40]) + b"\x00\x00\x00"
    )
    return MhZ19Response(command=0x86, data=data)


def diagnostics(pre_clamp_ppm: int, minimum_light_adc: int) -> MhZ19Response:
    """Build a synthetic 0x85 diagnostics response."""
    data = (
        pre_clamp_ppm.to_bytes(2, "big")
        + b"\x00\x00"
        + minimum_light_adc.to_bytes(2, "big")
    )
    return MhZ19Response(command=0x85, data=data)


def assess(
    samples: list[MhZ19Response | None],
    diagnostics_response: MhZ19Response | None = None,
) -> LivenessReport:
    """Run liveness assessment without real sleeps."""
    client = FakeClient(samples, diagnostics_response)
    liveness = SensorLiveness(
        client, sample_count=len(samples), sample_interval_seconds=0
    )
    return liveness.assess()


def test_unreachable_when_no_responses() -> None:
    report = assess([None, None])
    assert report.verdict is LivenessVerdict.UNREACHABLE
    assert report.valid_sample_count == 0


def test_alive_for_plausible_readings() -> None:
    report = assess(
        [measurement(800), measurement(810), measurement(820)],
        diagnostics(900, 120),
    )
    assert report.verdict is LivenessVerdict.ALIVE
    assert report.co2_min == 800
    assert report.co2_max == 820


def test_dead_when_light_adc_is_zero() -> None:
    report = assess(
        [measurement(800), measurement(805)],
        diagnostics(900, 0),
    )
    assert report.verdict is LivenessVerdict.DEAD


def test_dead_when_readings_pinned_low() -> None:
    report = assess([measurement(0), measurement(0)])
    assert report.verdict is LivenessVerdict.DEAD


def test_degraded_when_readings_below_plausible_range() -> None:
    report = assess([measurement(50), measurement(60)])
    assert report.verdict is LivenessVerdict.DEGRADED
