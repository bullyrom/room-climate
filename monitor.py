"""MH-Z19 long-term monitoring entry point."""

from room_climate.startup_guard import StartupGuard

TOOL_NAME = "mh_z19_monitor"
LOG_FILENAME = "mh_z19_monitor.log"


def main(argv: list[str]) -> int:
    """Import and run the monitoring CLI."""
    from room_climate.monitoring_cli import MonitoringCli

    return MonitoringCli().run(argv)


if __name__ == "__main__":
    raise SystemExit(StartupGuard(TOOL_NAME, LOG_FILENAME).run(main))
