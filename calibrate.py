"""CO2 sensor identification, diagnosis and calibration entry point."""

from room_climate.startup_guard import StartupGuard

TOOL_NAME = "mh_z19_calibrate"
LOG_FILENAME = "mh_z19_calibrate.log"


def main(argv: list[str]) -> int:
    """Import and run the calibration CLI."""
    from room_climate.calibration_cli import CalibrationCli

    return CalibrationCli().run(argv)


if __name__ == "__main__":
    raise SystemExit(StartupGuard(TOOL_NAME, LOG_FILENAME).run(main))
