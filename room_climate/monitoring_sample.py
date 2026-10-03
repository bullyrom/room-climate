"""A single timestamped monitoring measurement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MonitoringSample:
    """One CO2 and temperature measurement taken during monitoring."""

    timestamp: str
    co2_ppm: int
    temperature_celsius: int
