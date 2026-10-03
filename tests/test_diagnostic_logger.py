"""Tests for the console and file diagnostic logger."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from room_climate.diagnostic_logger import DiagnosticLogger

RUN_LOG_NAME_PATTERN = re.compile(r"^tool_\d{8}_\d{6}\.log$")


def test_logger_writes_to_file(tmp_path: Path) -> None:
    log_path = tmp_path / "tool.log"
    log = DiagnosticLogger(log_path)
    logger = log.start()
    logger.info("diagnostic message")
    log.stop()
    assert "diagnostic message" in log_path.read_text()


def test_resolve_log_path_is_timestamped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    path = DiagnosticLogger.resolve_log_path("tool.log")
    assert path.parent == Path.cwd()
    assert RUN_LOG_NAME_PATTERN.match(path.name)
