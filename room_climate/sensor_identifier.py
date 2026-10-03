"""Identification of the attached CO2 sensor."""

from __future__ import annotations

from .mh_z19_client import MhZ19Client
from .sensor_identity import SensorIdentity

UNKNOWN_FAMILY = "Unknown"
WINSEN_FAMILY = "Winsen MH-Z19 family (UART, operation mode 0)"
KNOWN_FAKE_FIRMWARE = frozenset({"0436"})
FAKE_DETECTION_RANGE_PPM = 10000


class SensorIdentifier:
    """Probes the port and reports which CO2 sensor family is present."""

    def __init__(self, client: MhZ19Client) -> None:
        """Store the client used to query the sensor."""
        self._client = client

    def identify(self) -> SensorIdentity:
        """Return the identified sensor family and its properties."""
        if self._client.read_measurement() is None:
            return SensorIdentity(
                detected=False,
                family=UNKNOWN_FAMILY,
                firmware_version=None,
                detection_range_ppm=None,
                warnings=("No valid MH-Z19 response on this port",),
            )
        firmware_version = self._client.read_firmware_version()
        detection_range_ppm = self._client.read_detection_range()
        return SensorIdentity(
            detected=True,
            family=WINSEN_FAMILY,
            firmware_version=firmware_version,
            detection_range_ppm=detection_range_ppm,
            warnings=self._collect_warnings(firmware_version, detection_range_ppm),
        )

    @staticmethod
    def _collect_warnings(
        firmware_version: str | None, detection_range_ppm: int | None
    ) -> tuple[str, ...]:
        """Return authenticity warnings for the reported firmware and range."""
        warnings: list[str] = []
        if firmware_version is None:
            warnings.append("Firmware version query did not answer")
        elif firmware_version in KNOWN_FAKE_FIRMWARE:
            warnings.append(
                f"Firmware {firmware_version} is typical for clone/black-PCB sensors"
            )
        if detection_range_ppm == FAKE_DETECTION_RANGE_PPM:
            warnings.append(
                "Reported 10000 ppm range is unusual for original MH-Z19B modules"
            )
        return tuple(warnings)
