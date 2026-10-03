"""A file logging handler that flushes and fsyncs every record."""

from __future__ import annotations

import logging
import os


class FlushingFileHandler(logging.FileHandler):
    """File handler that pushes every record to disk immediately.

    A long monitoring run's log may be read while the file is still open, so
    every record is flushed and fsynced to make sure the data is on disk as
    soon as it is logged.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Write the record and force it out to the disk."""
        super().emit(record)
        self.flush()
        stream = self.stream
        if stream is None:
            return
        try:
            os.fsync(stream.fileno())
        except (OSError, ValueError):
            pass
