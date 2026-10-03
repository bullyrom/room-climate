"""Command-line interface for long-term CO2 monitoring."""

from __future__ import annotations

import argparse
import logging
import traceback
from collections.abc import Sequence
from pathlib import Path

import serial

from .diagnostic_logger import DiagnosticLogger
from .mh_z19_client import MhZ19Client
from .monitoring_session import (
    DEFAULT_INTERVAL_SECONDS,
    UNLIMITED_DURATION_SECONDS,
    MonitoringSession,
)
from .serial_port_finder import SerialPortFinder
from .serial_transport import SerialTransport

DEFAULT_BAUD_RATE = 9600
LOG_FILENAME = "mh_z19_monitor.log"
EXIT_OK = 0
EXIT_ERROR = 1


class MonitoringCli:
    """Parses arguments and runs the long-term CO2 monitor."""

    def run(self, argv: Sequence[str] | None = None) -> int:
        """Run the CLI and return a process exit code."""
        args = self._build_parser().parse_args(argv)
        log_path = (
            Path(args.log_file)
            if args.log_file
            else DiagnosticLogger.resolve_log_path(LOG_FILENAME)
        )
        log = DiagnosticLogger(log_path)
        logger = log.start()
        try:
            logger.info("MH-Z19 long-term monitoring")
            return self._execute(args, logger, log_path)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
            return EXIT_OK
        except Exception:
            logger.error("Unexpected failure:\n%s", traceback.format_exc())
            return EXIT_ERROR
        finally:
            log.stop()

    def _execute(
        self, args: argparse.Namespace, logger: logging.Logger, log_path: Path
    ) -> int:
        """Resolve the port and run the monitoring session."""
        finder = SerialPortFinder()
        logger.info("Detected serial ports: %s", finder.describe())
        if args.list_ports:
            return EXIT_OK
        port = finder.resolve(args.port)
        logger.info(
            "Port: %s | baud: %s | interval: %ss | duration: %ss | log: %s",
            port,
            args.speed,
            args.interval,
            args.duration,
            log_path,
        )
        try:
            with SerialTransport(port, args.speed) as transport:
                session = MonitoringSession(
                    MhZ19Client(transport),
                    logger,
                    interval_seconds=args.interval,
                    duration_seconds=args.duration,
                )
                return session.run()
        except serial.SerialException as error_:
            logger.error("Failed to open %s: %s", port, error_)
            logger.error("Available ports: %s", finder.describe())
            return EXIT_ERROR
        except OSError as error_:
            logger.error("Serial communication error on %s: %s", port, error_)
            return EXIT_ERROR

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        """Return the argument parser for the monitoring CLI."""
        parser = argparse.ArgumentParser(
            description="Long-term MH-Z19 CO2 and temperature monitoring"
        )
        parser.add_argument("--port", help="Serial port (auto-detected when omitted)")
        parser.add_argument(
            "--speed",
            type=int,
            default=DEFAULT_BAUD_RATE,
            help="Baud rate (MH-Z19 default is 9600)",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=DEFAULT_INTERVAL_SECONDS,
            help="Seconds between measurements",
        )
        parser.add_argument(
            "--duration",
            type=float,
            default=UNLIMITED_DURATION_SECONDS,
            help="Run time in seconds (0 = until Ctrl+C)",
        )
        parser.add_argument(
            "--list-ports",
            action="store_true",
            help="List the detected serial ports and exit",
        )
        parser.add_argument(
            "--log-file",
            help="Log file path (defaults to a timestamped file next to the executable)",
        )
        return parser
