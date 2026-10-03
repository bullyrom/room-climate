"""Pipeline orchestrating CO2 sensor identification, liveness and calibration."""

from __future__ import annotations

from .calibration_outcome import CalibrationOutcome
from .calibration_result import CalibrationResult
from .calibration_summary import CalibrationSummary
from .liveness_verdict import LivenessVerdict
from .sensor_calibrator import SensorCalibrator
from .sensor_identifier import SensorIdentifier
from .sensor_liveness import SensorLiveness

DRY_RUN_MESSAGE = "Dry run only; re-run with --apply to write calibration"
DEAD_SENSOR_MESSAGE = "Calibration skipped because the sensor is not reliably alive"
ZERO_POINT_CONFIRMATION_REQUIRED = (
    "Zero point calibration requires an explicit 400 ppm confirmation"
)


class CalibrationPipeline:
    """Coordinates identification, liveness assessment and calibration."""

    def __init__(
        self,
        identifier: SensorIdentifier,
        liveness: SensorLiveness,
        calibrator: SensorCalibrator,
        apply_calibration: bool,
        confirm_reference: bool = False,
        abc_setting: bool | None = None,
    ) -> None:
        """Store the pipeline steps and the execution flags.

        ``abc_setting`` requests an automatic baseline correction change:
        ``True`` enables it, ``False`` disables it and ``None`` leaves it as is.
        """
        self._identifier = identifier
        self._liveness = liveness
        self._calibrator = calibrator
        self._apply_calibration = apply_calibration
        self._confirm_reference = confirm_reference
        self._abc_setting = abc_setting

    def run(self) -> CalibrationSummary:
        """Run every pipeline step and return the combined summary."""
        identity = self._identifier.identify()
        liveness = self._liveness.assess()
        abc_enabled = self._calibrator.read_auto_baseline_correction()
        results = self._run_calibration(liveness.verdict)
        return CalibrationSummary(
            identity=identity,
            liveness=liveness,
            abc_enabled=abc_enabled,
            results=tuple(results),
        )

    def _run_calibration(self, verdict: LivenessVerdict) -> list[CalibrationResult]:
        """Decide whether to calibrate and collect the resulting operations."""
        if not self._apply_calibration:
            return [self._refused(DRY_RUN_MESSAGE)]
        if verdict in (LivenessVerdict.DEAD, LivenessVerdict.UNREACHABLE):
            return [self._refused(DEAD_SENSOR_MESSAGE)]
        if self._abc_setting is None and not self._confirm_reference:
            return [self._refused(ZERO_POINT_CONFIRMATION_REQUIRED)]
        return self._write_calibration()

    def _write_calibration(self) -> list[CalibrationResult]:
        """Apply the requested ABC change and zero point calibration."""
        results: list[CalibrationResult] = []
        if self._abc_setting is not None:
            results.append(
                self._calibrator.set_auto_baseline_correction(self._abc_setting)
            )
        if self._confirm_reference:
            results.append(self._calibrator.calibrate_zero_point())
        return results

    @staticmethod
    def _refused(message: str) -> CalibrationResult:
        """Build a refused calibration result with the given message."""
        return CalibrationResult(
            operation="calibration",
            outcome=CalibrationOutcome.REFUSED,
            message=message,
        )
