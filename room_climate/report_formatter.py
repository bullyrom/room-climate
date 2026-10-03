"""Formatting of calibration summaries for humans and machines."""

from __future__ import annotations

import json
from dataclasses import asdict

from .calibration_summary import CalibrationSummary
from .liveness_report import LivenessReport

SEPARATOR = "=" * 60


class ReportFormatter:
    """Renders calibration and liveness results as text or JSON."""

    def format_text(self, summary: CalibrationSummary) -> str:
        """Return a human-readable multi-line report."""
        lines = [
            SEPARATOR,
            "CO2 sensor calibration report",
            SEPARATOR,
            *self._identity_lines(summary),
            *self._liveness_lines(summary),
            *self._calibration_lines(summary),
        ]
        return "\n".join(lines)

    def format_json(self, summary: CalibrationSummary) -> str:
        """Return the summary serialised as JSON."""
        return json.dumps(asdict(summary), default=str, indent=2)

    def format_liveness(self, report: LivenessReport) -> str:
        """Return a human-readable liveness report."""
        lines = [
            "[liveness]",
            f"  verdict: {report.verdict.value}",
            f"  samples: {report.valid_sample_count}/{report.sample_count} valid",
            f"  co2: {report.co2_min}..{report.co2_max} ppm",
            f"  temperature: {report.temperature_celsius} C",
            f"  pre-clamp co2: {report.pre_clamp_co2_ppm} ppm",
            f"  min light adc: {report.minimum_light_adc}",
            *[f"  reason: {reason}" for reason in report.reasons],
        ]
        return "\n".join(lines)

    @staticmethod
    def _identity_lines(summary: CalibrationSummary) -> list[str]:
        """Return report lines describing the sensor identity."""
        identity = summary.identity
        detected = "yes" if identity.detected else "no"
        return [
            "[identity]",
            f"  detected: {detected}",
            f"  family: {identity.family}",
            f"  firmware: {identity.firmware_version}",
            f"  range: {identity.detection_range_ppm} ppm",
            *[f"  warning: {warning}" for warning in identity.warnings],
        ]

    def _liveness_lines(self, summary: CalibrationSummary) -> list[str]:
        """Return report lines describing the liveness verdict."""
        return self.format_liveness(summary.liveness).splitlines()

    @staticmethod
    def _calibration_lines(summary: CalibrationSummary) -> list[str]:
        """Return report lines describing the calibration operations."""
        lines = ["[calibration]", f"  abc enabled: {summary.abc_enabled}"]
        for result in summary.results:
            lines.append(
                f"  {result.operation}: {result.outcome.value} - {result.message}"
            )
        return lines
