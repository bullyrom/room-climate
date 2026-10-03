"""Calibration operation result value object."""

from __future__ import annotations

from dataclasses import dataclass

from .calibration_outcome import CalibrationOutcome


@dataclass(frozen=True)
class CalibrationResult:
    """Outcome of one calibration or configuration operation."""

    operation: str
    outcome: CalibrationOutcome
    message: str
