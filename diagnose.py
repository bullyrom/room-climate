"""MH-Z19 CO2 sensor liveness diagnostic entry point."""

from room_climate.startup_guard import StartupGuard

TOOL_NAME = "mh_z19_liveness"
LOG_FILENAME = "mh_z19_liveness.log"


def main(argv: list[str]) -> int:
    """Import and run the liveness CLI."""
    from room_climate.liveness_cli import LivenessCli

    return LivenessCli().run(argv)


if __name__ == "__main__":
    raise SystemExit(StartupGuard(TOOL_NAME, LOG_FILENAME).run(main))
