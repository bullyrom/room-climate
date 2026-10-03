"""Calibration and configuration operations for an MH-Z19 sensor."""

from __future__ import annotations

from .calibration_outcome import CalibrationOutcome
from .calibration_result import CalibrationResult
from .mh_z19_client import MhZ19Client

ZERO_POINT_REFERENCE_PPM = 400
ZERO_POINT_STABILIZATION_MINUTES = 20


class SensorCalibrator:
    """Runs calibration commands and reports their outcome."""

    def __init__(self, client: MhZ19Client) -> None:
        """Store the client used to send calibration commands."""
        self._client = client

    def read_auto_baseline_correction(self) -> bool | None:
        """Return whether automatic baseline correction is enabled."""
        return self._client.read_auto_baseline_correction()

    def set_auto_baseline_correction(self, enabled: bool) -> CalibrationResult:
        """Enable or disable automatic baseline correction."""
        succeeded = self._client.set_auto_baseline_correction(enabled)
        state = "enabled" if enabled else "disabled"
        return CalibrationResult(
            operation="automatic_baseline_correction",
            outcome=(
                CalibrationOutcome.SUCCESS if succeeded else CalibrationOutcome.FAILED
            ),
            message=(
                f"Automatic baseline correction {state}"
                if succeeded
                else "Sensor did not acknowledge the ABC command"
            ),
        )

    def calibrate_zero_point(self) -> CalibrationResult:
        """Calibrate the zero point against a 400 ppm reference."""
        succeeded = self._client.calibrate_zero_point()
        return CalibrationResult(
            operation="zero_point_calibration",
            outcome=(
                CalibrationOutcome.SUCCESS if succeeded else CalibrationOutcome.FAILED
            ),
            message=(
                f"Zero point calibrated to {ZERO_POINT_REFERENCE_PPM} ppm"
                if succeeded
                else "Sensor did not acknowledge the zero point command"
            ),
        )
