"""Tests for the liveness diagnostic CLI helpers."""

from __future__ import annotations

from room_climate.liveness_cli import (
    EXIT_ALIVE,
    EXIT_DEAD,
    EXIT_DEGRADED,
    EXIT_UNREACHABLE,
    LivenessCli,
)
from room_climate.liveness_report import LivenessReport
from room_climate.liveness_verdict import LivenessVerdict
from room_climate.report_formatter import ReportFormatter
from room_climate.serial_port_finder import DEFAULT_PORT, SerialPortFinder


def report(verdict: LivenessVerdict) -> LivenessReport:
    """Build a minimal liveness report for the given verdict."""
    return LivenessReport(
        verdict=verdict,
        sample_count=3,
        valid_sample_count=3,
        co2_min=800,
        co2_max=820,
        temperature_celsius=22,
        pre_clamp_co2_ppm=900,
        minimum_light_adc=120,
        reasons=("test reason",),
    )


def test_exit_code_matches_verdict() -> None:
    assert LivenessCli._exit_code(LivenessVerdict.ALIVE) == EXIT_ALIVE
    assert LivenessCli._exit_code(LivenessVerdict.DEGRADED) == EXIT_DEGRADED
    assert LivenessCli._exit_code(LivenessVerdict.DEAD) == EXIT_DEAD
    assert LivenessCli._exit_code(LivenessVerdict.UNREACHABLE) == EXIT_UNREACHABLE


def test_format_liveness_contains_verdict_and_reason() -> None:
    text = ReportFormatter().format_liveness(report(LivenessVerdict.DEAD))
    assert "verdict: dead" in text
    assert "reason: test reason" in text


def test_port_finder_uses_explicit_port() -> None:
    assert SerialPortFinder().resolve("/dev/ttyS9") == "/dev/ttyS9"


def test_port_finder_falls_back_to_default() -> None:
    finder = SerialPortFinder()
    finder._detect_usb_port = lambda: None
    assert finder.resolve() == DEFAULT_PORT
