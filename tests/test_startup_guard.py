"""Tests for the fail-safe startup guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from room_climate.startup_guard import StartupGuard


def test_guard_runs_entry_with_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "guard.log"
    captured: list[list[str]] = []

    def entry(argv: list[str]) -> int:
        captured.append(argv)
        return 0

    code = StartupGuard("tool", "tool.log", argv=["--log-file", str(log_path)]).run(
        entry
    )
    assert code == 0
    assert captured == [["--log-file", str(log_path)]]
    assert log_path.exists()


def test_guard_injects_log_file_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    captured: list[list[str]] = []

    def entry(argv: list[str]) -> int:
        captured.append(argv)
        return 0

    StartupGuard("tool", "tool.log", argv=[]).run(entry)
    assert "--log-file" in captured[0]


def test_guard_reports_crash(tmp_path: Path) -> None:
    log_path = tmp_path / "guard.log"

    def entry(argv: list[str]) -> int:
        raise RuntimeError("boom")

    code = StartupGuard("tool", "tool.log", argv=["--log-file", str(log_path)]).run(
        entry
    )
    assert code == 1
    assert "boom" in log_path.read_text()
