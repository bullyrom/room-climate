"""ESP32 Wi-Fi credential provisioning entry point."""

from room_climate.startup_guard import StartupGuard

TOOL_NAME = "mh_z19_provision"
LOG_FILENAME = "mh_z19_provision.log"


def main(argv: list[str]) -> int:
    """Import and run the provisioning CLI."""
    from room_climate.provision_cli import ProvisionCli

    return ProvisionCli().run(argv)


if __name__ == "__main__":
    raise SystemExit(StartupGuard(TOOL_NAME, LOG_FILENAME).run(main))
