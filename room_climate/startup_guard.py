"""Fail-safe entry point for the user-side diagnostic binaries."""

from __future__ import annotations

import os
import platform
import sys
import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TextIO

from .diagnostic_logger import DiagnosticLogger, LOG_DATE_FORMAT

LOG_FILE_ARGUMENT = "--log-file"
INTERRUPT_EXIT_CODE = 130
CRASH_EXIT_CODE = 1


class StartupGuard:
    """Runs a CLI tool while guaranteeing console output and a log file.

    It announces the runtime environment before the tool starts, resolves the
    log file (falling back to the temp directory), injects ``--log-file`` into
    the arguments when the user did not provide one, and reports any early
    failure with a traceback to both the console and the log file.
    """

    def __init__(
        self,
        tool_name: str,
        log_filename: str,
        argv: list[str] | None = None,
    ) -> None:
        """Resolve the log path and prepare the arguments for the tool."""
        self._tool_name = tool_name
        self._argv = list(sys.argv[1:]) if argv is None else list(argv)
        explicit_log = self._log_argument()
        self._log_path = (
            Path(explicit_log)
            if explicit_log is not None
            else DiagnosticLogger.resolve_log_path(log_filename)
        )
        if explicit_log is None:
            self._argv = self._argv + [LOG_FILE_ARGUMENT, str(self._log_path)]

    def run(self, entry: Callable[[list[str]], int]) -> int:
        """Announce, run the tool and report any failure."""
        self._announce_startup()
        try:
            return int(entry(self._argv))
        except KeyboardInterrupt:
            self._write_lines(["interrupted by user"])
            return INTERRUPT_EXIT_CODE
        except SystemExit as exit_:
            return int(exit_.code or 0)
        except BaseException:
            self._write_lines(["unexpected failure:", traceback.format_exc()])
            return CRASH_EXIT_CODE

    def _log_argument(self) -> str | None:
        """Return the value of ``--log-file`` from the arguments, if present."""
        for index, token in enumerate(self._argv):
            if token == LOG_FILE_ARGUMENT and index + 1 < len(self._argv):
                return self._argv[index + 1]
            if token.startswith(f"{LOG_FILE_ARGUMENT}="):
                return token.split("=", 1)[1]
        return None

    def _announce_startup(self) -> None:
        """Write the startup banner to the console and the log file."""
        self._write_lines(
            [
                f"{self._tool_name} starting",
                f"time: {datetime.now().strftime(LOG_DATE_FORMAT)}",
                f"executable: {sys.executable}",
                f"frozen: {getattr(sys, 'frozen', False)}",
                f"cwd: {os.getcwd()}",
                f"argv: {self._argv}",
                f"python: {platform.python_version()}",
                f"platform: {platform.platform()}",
                f"log: {self._log_path}",
            ]
        )

    def _write_lines(self, lines: list[str]) -> None:
        """Write text to the console and the log file, ignoring failures."""
        text = "\n".join(lines)
        if not StartupGuard._write_stream(sys.stdout, text):
            StartupGuard._write_stream(sys.stderr, text)
        self._append_log(text)

    def _append_log(self, text: str) -> None:
        """Append text to the log file, ignoring failures."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as handle:
                handle.write(text + "\n")
        except OSError:
            pass

    @staticmethod
    def _write_stream(stream: TextIO | None, text: str) -> bool:
        """Write text to a stream, returning False on a missing/broken stream."""
        if stream is None:
            return False
        try:
            stream.write(text + "\n")
            stream.flush()
            return True
        except (OSError, ValueError):
            return False
