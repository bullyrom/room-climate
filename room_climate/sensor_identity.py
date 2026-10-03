"""Value object describing an identified CO2 sensor."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SensorIdentity:
    """Result of probing which CO2 sensor is attached to the port."""

    detected: bool
    family: str
    firmware_version: str | None
    detection_range_ppm: int | None
    warnings: tuple[str, ...]
