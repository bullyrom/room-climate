"""Tests for the calibration pipeline decision logic."""

from __future__ import annotations

from room_climate.calibration_outcome import CalibrationOutcome
from room_climate.calibration_pipeline import CalibrationPipeline
from room_climate.calibration_result import CalibrationResult
from room_climate.liveness_report import LivenessReport
from room_climate.liveness_verdict import LivenessVerdict
from room_climate.sensor_identity import SensorIdentity


class FakeIdentifier:
    """Identifier stub returning a fixed identity."""

    def identify(self) -> SensorIdentity:
        """Return a detected Winsen sensor identity."""
        return SensorIdentity(
            detected=True,
            family="Winsen MH-Z19 family (UART, operation mode 0)",
            firmware_version="0430",
            detection_range_ppm=5000,
            warnings=(),
        )


class FakeLiveness:
    """Liveness stub returning a prepared verdict."""

    def __init__(self, verdict: LivenessVerdict) -> None:
        """Store the verdict to report."""
        self._verdict = verdict

    def assess(self) -> LivenessReport:
        """Return a report with the stored verdict."""
        return LivenessReport(
            verdict=self._verdict,
            sample_count=3,
            valid_sample_count=3,
            co2_min=800,
            co2_max=820,
            temperature_celsius=22,
            pre_clamp_co2_ppm=900,
            minimum_light_adc=120,
            reasons=(),
        )


class FakeCalibrator:
    """Calibrator stub tracking whether the zero point was calibrated."""

    def __init__(self) -> None:
        """Initialise the call counters."""
        self.zero_point_calls = 0
        self.abc_calls: list[bool] = []

    def read_auto_baseline_correction(self) -> bool:
        """Return that ABC is enabled."""
        return True

    def set_auto_baseline_correction(self, enabled: bool) -> CalibrationResult:
        """Record a successful ABC change."""
        self.abc_calls.append(enabled)
        return CalibrationResult(
            operation="automatic_baseline_correction",
            outcome=CalibrationOutcome.SUCCESS,
            message="ok",
        )

    def calibrate_zero_point(self) -> CalibrationResult:
        """Record a successful zero point calibration."""
        self.zero_point_calls += 1
        return CalibrationResult(
            operation="zero_point_calibration",
            outcome=CalibrationOutcome.SUCCESS,
            message="ok",
        )


def build_pipeline(
    verdict: LivenessVerdict,
    apply_calibration: bool,
    confirm_reference: bool,
    abc_setting: bool | None = None,
) -> tuple[CalibrationPipeline, FakeCalibrator]:
    """Build a pipeline with stubs and return it with the calibrator."""
    calibrator = FakeCalibrator()
    pipeline = CalibrationPipeline(
        identifier=FakeIdentifier(),
        liveness=FakeLiveness(verdict),
        calibrator=calibrator,
        apply_calibration=apply_calibration,
        confirm_reference=confirm_reference,
        abc_setting=abc_setting,
    )
    return pipeline, calibrator


def test_dry_run_does_not_calibrate() -> None:
    pipeline, calibrator = build_pipeline(
        LivenessVerdict.ALIVE, apply_calibration=False, confirm_reference=True
    )
    summary = pipeline.run()
    assert summary.results[0].outcome is CalibrationOutcome.REFUSED
    assert calibrator.zero_point_calls == 0


def test_calibration_refused_for_dead_sensor() -> None:
    pipeline, calibrator = build_pipeline(
        LivenessVerdict.DEAD, apply_calibration=True, confirm_reference=True
    )
    summary = pipeline.run()
    assert summary.results[0].outcome is CalibrationOutcome.REFUSED
    assert calibrator.zero_point_calls == 0


def test_calibration_requires_reference_confirmation() -> None:
    pipeline, calibrator = build_pipeline(
        LivenessVerdict.ALIVE, apply_calibration=True, confirm_reference=False
    )
    summary = pipeline.run()
    assert summary.results[0].outcome is CalibrationOutcome.REFUSED
    assert calibrator.zero_point_calls == 0


def test_calibration_runs_when_all_conditions_met() -> None:
    pipeline, calibrator = build_pipeline(
        LivenessVerdict.ALIVE, apply_calibration=True, confirm_reference=True
    )
    summary = pipeline.run()
    assert summary.results[0].outcome is CalibrationOutcome.SUCCESS
    assert calibrator.zero_point_calls == 1


def test_abc_change_runs_without_zero_calibration() -> None:
    pipeline, calibrator = build_pipeline(
        LivenessVerdict.ALIVE,
        apply_calibration=True,
        confirm_reference=False,
        abc_setting=False,
    )
    summary = pipeline.run()
    assert calibrator.abc_calls == [False]
    assert calibrator.zero_point_calls == 0
    assert summary.results[0].outcome is CalibrationOutcome.SUCCESS


def test_abc_change_then_zero_calibration() -> None:
    pipeline, calibrator = build_pipeline(
        LivenessVerdict.ALIVE,
        apply_calibration=True,
        confirm_reference=True,
        abc_setting=False,
    )
    pipeline.run()
    assert calibrator.abc_calls == [False]
    assert calibrator.zero_point_calls == 1


def test_nothing_requested_is_refused() -> None:
    pipeline, calibrator = build_pipeline(
        LivenessVerdict.ALIVE,
        apply_calibration=True,
        confirm_reference=False,
        abc_setting=None,
    )
    summary = pipeline.run()
    assert summary.results[0].outcome is CalibrationOutcome.REFUSED
    assert calibrator.abc_calls == []
    assert calibrator.zero_point_calls == 0
