"""Command-line interface for Wi-Fi credential provisioning."""

from __future__ import annotations

import argparse
import getpass
import logging
import traceback
from collections.abc import Sequence
from pathlib import Path

import serial

from .diagnostic_logger import DiagnosticLogger
from .provision_outcome import ProvisionOutcome
from .serial_port_finder import SerialPortFinder
from .wifi_provisioner import (
    DEFAULT_BAUD_RATE,
    DEFAULT_CONFIRM_TIMEOUT_SECONDS,
    DEFAULT_READY_TIMEOUT_SECONDS,
    DEFAULT_VERIFY_TIMEOUT_SECONDS,
    LINE_POLL_SECONDS,
    WifiProvisioner,
)

LOG_FILENAME = "mh_z19_provision.log"
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PORT_ERROR = 2
NVS_ERASE_REGION = "0x9000 0x6000"
OUTCOME_MESSAGES = {
    ProvisionOutcome.SAVED: "Credentials saved on the device.",
    ProvisionOutcome.NOT_SAVED: "The device reported that it could not save the credentials.",
    ProvisionOutcome.NO_CONFIRMATION: "The device did not confirm saving the credentials.",
}


class ProvisionCli:
    """Prompts for credentials and stores them on the device over serial."""

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
            logger.info("MH-Z19 Wi-Fi provisioning")
            return self._execute(args, logger)
        except Exception:
            logger.error("Unexpected failure:\n%s", traceback.format_exc())
            return EXIT_ERROR
        finally:
            log.stop()

    def _execute(self, args: argparse.Namespace, logger: logging.Logger) -> int:
        """Resolve the port, read the credentials and provision the device."""
        finder = SerialPortFinder()
        logger.info("Detected serial ports: %s", finder.describe())
        port = finder.resolve(args.port)
        logger.info("Port: %s | baud: %s", port, args.speed)

        ssid = input("Wi-Fi SSID: ").strip()
        if not ssid:
            logger.error("SSID is required")
            return EXIT_ERROR
        password = getpass.getpass("Wi-Fi password (hidden): ")

        try:
            with serial.Serial(
                port=port, baudrate=args.speed, timeout=LINE_POLL_SECONDS
            ) as connection:
                provisioner = WifiProvisioner(
                    connection,
                    ready_timeout=args.ready_timeout,
                    confirm_timeout=args.confirm_timeout,
                    verify_timeout=args.verify_timeout,
                    logger=logger,
                )
                outcome = provisioner.provision(ssid, password)
        except serial.SerialException as error_:
            logger.error("Failed to open %s: %s", port, error_)
            logger.error("Available ports: %s", finder.describe())
            return EXIT_PORT_ERROR
        except OSError as error_:
            logger.error("Serial communication error on %s: %s", port, error_)
            return EXIT_ERROR
        finally:
            password = ""

        return self._report(outcome, port, logger)

    @staticmethod
    def _report(outcome: ProvisionOutcome, port: str, logger: logging.Logger) -> int:
        """Log the outcome and return the matching exit code."""
        if outcome is ProvisionOutcome.SAVED:
            logger.info(OUTCOME_MESSAGES[outcome])
            return EXIT_OK
        logger.error(OUTCOME_MESSAGES[outcome])
        logger.error(
            "If the device already holds credentials, erase the nvs partition first:"
        )
        logger.error("  espflash erase-region --port %s %s", port, NVS_ERASE_REGION)
        return EXIT_ERROR

    @staticmethod
    def _build_parser() -> argparse.ArgumentParser:
        """Return the argument parser for the provisioning CLI."""
        parser = argparse.ArgumentParser(
            description="Store Wi-Fi credentials on the ESP32 over the USB serial port"
        )
        parser.add_argument("--port", help="Serial port (auto-detected when omitted)")
        parser.add_argument(
            "--speed",
            type=int,
            default=DEFAULT_BAUD_RATE,
            help="Console baud rate (the firmware uses 115200)",
        )
        parser.add_argument(
            "--ready-timeout",
            type=float,
            default=DEFAULT_READY_TIMEOUT_SECONDS,
            help="Seconds to wait for the firmware provisioning prompt",
        )
        parser.add_argument(
            "--confirm-timeout",
            type=float,
            default=DEFAULT_CONFIRM_TIMEOUT_SECONDS,
            help="Seconds to wait for the save confirmation line",
        )
        parser.add_argument(
            "--verify-timeout",
            type=float,
            default=DEFAULT_VERIFY_TIMEOUT_SECONDS,
            help="Seconds to wait, after a reboot, for the stored credentials",
        )
        parser.add_argument(
            "--log-file",
            help="Log file path (defaults to a timestamped file next to the executable)",
        )
        return parser
