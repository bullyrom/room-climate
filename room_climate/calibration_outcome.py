"""Outcome of a single calibration operation."""

from __future__ import annotations

from enum import Enum


class CalibrationOutcome(Enum):
    """Possible results of a calibration operation."""

    SUCCESS = "success"
    REFUSED = "refused"
    FAILED = "failed"
