"""Command-line interface for the CO2 sensor liveness diagnostic."""

from __future__ import annotations

import argparse
import logging
import traceback
from collections.abc import Sequence
from pathlib import Path

import serial

from .diagnostic_logger import DiagnosticLogger
from .liveness_report import LivenessReport
from .liveness_verdict import LivenessVerdict
from .mh_z19_client import MhZ19Client
from .report_formatter import ReportFormatter
from .sensor_liveness import (
    DEFAULT_SAMPLE_COUNT,
    DEFAULT_SAMPLE_INTERVAL_SECONDS,
    SensorLiveness,
)
from .serial_port_finder import SerialPortFinder
from .serial_transport import SerialTransport

DEFAULT_BAUD_RATE = 9600
LOG_FILENAME = "mh_z19_liveness.log"
EXIT_ALIVE = 0
EXIT_ERROR = 1
EXIT_PORT_ERROR = 2
EXIT_DEGRADED = 3
EXIT_DEAD = 4
EXIT_UNREACHABLE = 5
VERDICT_EXIT_CODES = {
    LivenessVerdict.ALIVE: EXIT_ALIVE,
    LivenessVerdict.DEGRADED: EXIT_DEGRADED,
    LivenessVerdict.DEAD: EXIT_DEAD,
    LivenessVerdict.UNREACHABLE: EXIT_UNREACHABLE,
}


class LivenessCli:
    """Parses arguments, runs the liveness diagnosis and logs the result."""

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
            logger.info("MH-Z19 liveness diagnostic")
            return self._execute(args, logger, log_path)
        except Exception:
            logger.error("Unexpected failure:\n%s", traceback.format_exc())
            return EXIT_ERROR
        finally:
            log.stop()

    def _execute(
        self, args: argparse.Namespace, logger: logging.Logger, log_path: Path
    ) -> int:
        """Resolve the port, take samples and log the liveness report."""
        finder = SerialPortFinder()
        logger.info("Detected serial ports: %s", finder.describe())
        if args.list_ports:
            return EXIT_ALIVE
        port = finder.resolve(args.port)
        logger.info(
            "Port: %s | baud: %s | samples: %s | log: %s",
            port,
            args.speed,
            args.samples,
            log_path,
        )
        try:
            report = self._assess(port, args)
        except serial.SerialException as error_:
            logger.error("Failed to open %s: %s", port, error_)
            logger.error("Available ports: %s", finder.describe())
            return EXIT_PORT_ERROR
        except OSError as error_:
            logger.error("Serial communication error on %s: %s", port, error_)
            return EXIT_ERROR
        logger.info(self._format_report(report))
        exit_code = self._exit_code(report.verdict)
        logger.info("Verdict: %s | exit code: %s", report.verdict.value, exit_code)
        return exit_code

    @staticmethod
    def _assess(port: str, args: argparse.Namespace) -> LivenessReport:
        """Open the port and run the liveness assessment."""
        with SerialTransport(port, args.speed) as transport:
            return SensorLiveness(
                MhZ19Client(transport),
                sample_count=args.samples,
                sample_interval_seconds=args.interval,
            ).assess()

    @staticmethod
    def _format_report(report: LivenessReport) -> str:
        """Render the liveness report as text."""
        return ReportFormatter().format_liveness(report)

    @staticmethod
    def _exit_code(verdict: LivenessVerdict) -> int:
        """Return the process exit code for a liveness verdict."""
        return VERDICT_EXIT_CODES[verdict]

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        """Return the argument parser for the liveness diagnostic CLI."""
        parser = argparse.ArgumentParser(
            description="Diagnose MH-Z19 CO2 sensor liveness"
        )
        parser.add_argument("--port", help="Serial port (auto-detected when omitted)")
        parser.add_argument(
            "--speed",
            type=int,
            default=DEFAULT_BAUD_RATE,
            help="Baud rate (MH-Z19 default is 9600)",
        )
        parser.add_argument(
            "--samples",
            type=int,
            default=DEFAULT_SAMPLE_COUNT,
            help="Number of liveness samples to take",
        )
        parser.add_argument(
            "--interval",
            type=float,
            default=DEFAULT_SAMPLE_INTERVAL_SECONDS,
            help="Seconds between liveness samples",
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
