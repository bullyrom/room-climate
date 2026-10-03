"""Calibration pipeline summary value object."""

from __future__ import annotations

from dataclasses import dataclass

from .calibration_result import CalibrationResult
from .liveness_report import LivenessReport
from .sensor_identity import SensorIdentity


@dataclass(frozen=True)
class CalibrationSummary:
    """Combined result of identification, liveness and calibration."""

    identity: SensorIdentity
    liveness: LivenessReport
    abc_enabled: bool | None
    results: tuple[CalibrationResult, ...]
