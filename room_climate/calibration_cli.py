"""Command-line interface for CO2 sensor identification and calibration."""

from __future__ import annotations

import argparse
import logging
import traceback
from collections.abc import Sequence
from pathlib import Path

import serial

from .calibration_pipeline import CalibrationPipeline
from .calibration_summary import CalibrationSummary
from .diagnostic_logger import DiagnosticLogger
from .mh_z19_client import MhZ19Client
from .report_formatter import ReportFormatter
from .serial_port_finder import SerialPortFinder
from .serial_transport import SerialTransport
from .sensor_calibrator import SensorCalibrator
from .sensor_identifier import SensorIdentifier
from .sensor_liveness import (
    DEFAULT_SAMPLE_COUNT,
    DEFAULT_SAMPLE_INTERVAL_SECONDS,
    SensorLiveness,
)

DEFAULT_PORT = "/dev/ttyUSB0"
DEFAULT_BAUD_RATE = 9600
LOG_FILENAME = "mh_z19_calibrate.log"
EXIT_OK = 0
EXIT_ERROR = 1


class CalibrationCli:
    """Parses arguments and runs the calibration pipeline."""

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
            logger.info("MH-Z19 calibration on %s at %s baud", args.port, args.speed)
            return self._execute(args, logger, log_path)
        except Exception:
            logger.error("Unexpected failure:\n%s", traceback.format_exc())
            return EXIT_ERROR
        finally:
            log.stop()

    def _execute(
        self, args: argparse.Namespace, logger: logging.Logger, log_path: Path
    ) -> int:
        """Resolve the port, run the pipeline and log the report."""
        finder = SerialPortFinder()
        logger.info("Detected serial ports: %s", finder.describe())
        if args.list_ports:
            return EXIT_OK
        port = finder.resolve(args.port)
        try:
            with SerialTransport(port, args.speed) as transport:
                summary = self._run_pipeline(transport, args)
        except serial.SerialException as error_:
            logger.error("Failed to open %s: %s", port, error_)
            logger.error("Available ports: %s", finder.describe())
            return EXIT_ERROR
        except OSError as error_:
            logger.error("Serial communication error on %s: %s", port, error_)
            return EXIT_ERROR
        logger.info("\n%s", self._format_summary(summary, args))
        logger.info("Log written to %s", log_path)
        return EXIT_OK

    @staticmethod
    def _format_summary(summary: CalibrationSummary, args: argparse.Namespace) -> str:
        """Render the pipeline summary as JSON or text."""
        formatter = ReportFormatter()
        if args.json:
            return formatter.format_json(summary)
        return formatter.format_text(summary)

    def _run_pipeline(
        self, transport: SerialTransport, args: argparse.Namespace
    ) -> CalibrationSummary:
        """Wire the pipeline steps and execute them."""
        client = MhZ19Client(transport)
        pipeline = CalibrationPipeline(
            identifier=SensorIdentifier(client),
            liveness=SensorLiveness(
                client,
                sample_count=args.samples,
                sample_interval_seconds=args.interval,
            ),
            calibrator=SensorCalibrator(client),
            apply_calibration=args.apply,
            confirm_reference=args.confirm_reference,
            abc_setting=self._abc_setting(args),
        )
        return pipeline.run()

    @staticmethod
    def _abc_setting(args: argparse.Namespace) -> bool | None:
        """Return the requested ABC change, or None to leave it untouched."""
        if args.enable_abc:
            return True
        if args.disable_abc:
            return False
        return None

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        """Return the argument parser for the calibration CLI."""
        parser = argparse.ArgumentParser(
            description="Identify, diagnose and calibrate an MH-Z19 CO2 sensor"
        )
        parser.add_argument("--port", default=DEFAULT_PORT, help="Serial port")
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
            "--apply",
            action="store_true",
            help="Actually write calibration; without it the run is read-only",
        )
        parser.add_argument(
            "--confirm-reference",
            action="store_true",
            help="Confirm the sensor sits in stable 400 ppm air for 20 minutes",
        )
        abc_group = parser.add_mutually_exclusive_group()
        abc_group.add_argument(
            "--enable-abc",
            action="store_true",
            help="Turn automatic baseline correction on (requires --apply)",
        )
        abc_group.add_argument(
            "--disable-abc",
            action="store_true",
            help="Turn automatic baseline correction off (requires --apply)",
        )
        parser.add_argument(
            "--list-ports",
            action="store_true",
            help="List the detected serial ports and exit",
        )
        parser.add_argument(
            "--json", action="store_true", help="Print the report as JSON"
        )
        parser.add_argument(
            "--log-file",
            help="Log file path (defaults to a timestamped file next to the executable)",
        )
        return parser
