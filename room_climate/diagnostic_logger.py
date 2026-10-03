"""Console and per-run file logging for the user-side diagnostic tools."""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TextIO

from .flushing_file_handler import FlushingFileHandler

LOGGER_NAME = "room_climate.diagnostic"
LOG_FORMAT = "%(asctime)s %(levelname)s %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_TIMESTAMP_FORMAT = "%Y%m%d_%H%M%S"
FILE_LOG_MODE = "a"
LOG_FALLBACK_DIRECTORY = Path(tempfile.gettempdir())


class DiagnosticLogger:
    """Configures a logger that writes to the console and a per-run log file.

    Every run gets its own timestamped file. The location is chosen from the
    executable directory, the working directory and finally the system
    temporary directory, and ``start`` never raises: if the log file cannot be
    opened the run continues with console output only.
    """

    def __init__(self, log_path: Path) -> None:
        """Store the log file path and prepare a fresh logger."""
        self._log_path = log_path
        self._logger = logging.getLogger(LOGGER_NAME)
        self._logger.setLevel(logging.INFO)
        self._logger.handlers.clear()

    @property
    def log_path(self) -> Path:
        """Return the path of the log file actually in use."""
        return self._log_path

    def start(self) -> logging.Logger:
        """Attach the console and file handlers and return the logger."""
        self._logger.addHandler(self._console_handler())
        self._attach_file_handler()
        return self._logger

    def stop(self) -> None:
        """Flush and detach every handler."""
        for handler in list(self._logger.handlers):
            handler.flush()
            handler.close()
            self._logger.removeHandler(handler)

    @staticmethod
    def resolve_log_path(filename: str) -> Path:
        """Return a writable timestamped per-run log path."""
        stem = Path(filename).stem
        timestamp = datetime.now().strftime(LOG_TIMESTAMP_FORMAT)
        name = f"{stem}_{timestamp}.log"
        for directory in DiagnosticLogger._candidate_directories():
            if DiagnosticLogger._is_writable(directory):
                return directory / name
        return LOG_FALLBACK_DIRECTORY / name

    def _attach_file_handler(self) -> None:
        """Attach a file handler, falling back to the temp directory."""
        for candidate in (self._log_path, self._fallback_path()):
            try:
                self._log_path = candidate
                handler = self._file_handler()
                self._logger.addHandler(handler)
                return
            except OSError as error_:
                DiagnosticLogger._announce_error(
                    f"Could not open log file {candidate}: {error_}"
                )
        DiagnosticLogger._announce_error(
            "No log file could be opened; console output only"
        )

    def _fallback_path(self) -> Path:
        """Return the temp directory counterpart of the current log path."""
        return LOG_FALLBACK_DIRECTORY / self._log_path.name

    @staticmethod
    def _candidate_directories() -> tuple[Path, ...]:
        """Return the directories to try, most preferred first."""
        candidates: list[Path] = []
        if getattr(sys, "frozen", False):
            candidates.append(Path(sys.executable).resolve().parent)
        candidates.append(Path.cwd())
        candidates.append(LOG_FALLBACK_DIRECTORY)
        unique: list[Path] = []
        for candidate in candidates:
            if candidate not in unique:
                unique.append(candidate)
        return tuple(unique)

    @staticmethod
    def _is_writable(directory: Path) -> bool:
        """Return True when the directory exists or can be created writably."""
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError:
            return False
        return os.access(directory, os.W_OK)

    @staticmethod
    def _announce_error(message: str) -> None:
        """Write an error directly to stderr, ignoring a broken stream."""
        stream: TextIO | None = sys.stderr
        if stream is None:
            return
        try:
            stream.write(f"ERROR: {message}\n")
            stream.flush()
        except (OSError, ValueError):
            pass

    @staticmethod
    def _console_handler() -> logging.Handler:
        """Return a handler that writes to standard output."""
        stream = sys.stdout if sys.stdout is not None else sys.stderr
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        return handler

    def _file_handler(self) -> logging.Handler:
        """Return a handler that writes to the log file."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        handler = FlushingFileHandler(self._log_path, mode=FILE_LOG_MODE)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
        return handler
