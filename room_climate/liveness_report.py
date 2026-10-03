"""Liveness assessment result value object."""

from __future__ import annotations

from dataclasses import dataclass

from .liveness_verdict import LivenessVerdict


@dataclass(frozen=True)
class LivenessReport:
    """Health summary derived from several measurement samples."""

    verdict: LivenessVerdict
    sample_count: int
    valid_sample_count: int
    co2_min: int | None
    co2_max: int | None
    temperature_celsius: int | None
    pre_clamp_co2_ppm: int | None
    minimum_light_adc: int | None
    reasons: tuple[str, ...]
