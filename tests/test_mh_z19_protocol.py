"""Tests for the MH-Z19 protocol framing and parsing."""

from __future__ import annotations

from room_climate.mh_z19_protocol import (
    COMMAND_AUTO_BASELINE_CORRECTION,
    COMMAND_CALIBRATE_ZERO,
    COMMAND_READ_CO2,
    START_BYTE,
    MhZ19Protocol,
)


def reference_checksum(payload: bytes) -> int:
    """Independent checksum implementation used to validate the protocol."""
    return (0xFF - (sum(payload) % 0x100) + 1) & 0xFF


def test_read_command_frame_matches_datasheet() -> None:
    frame = MhZ19Protocol.build_command(COMMAND_READ_CO2)
    assert frame == bytes([0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79])


def test_zero_calibration_frame_matches_datasheet() -> None:
    frame = MhZ19Protocol.build_command(COMMAND_CALIBRATE_ZERO)
    assert frame == bytes([0xFF, 0x01, 0x87, 0x00, 0x00, 0x00, 0x00, 0x00, 0x78])


def test_abc_on_frame_has_expected_checksum() -> None:
    frame = MhZ19Protocol.build_command(COMMAND_AUTO_BASELINE_CORRECTION, bytes([0xA0]))
    assert frame == bytes([0xFF, 0x01, 0x79, 0xA0, 0x00, 0x00, 0x00, 0x00, 0xE6])


def test_span_frame_encodes_reference_ppm() -> None:
    frame = MhZ19Protocol.build_command(0x88, (2000).to_bytes(2, "big"))
    assert frame[:5] == bytes([0xFF, 0x01, 0x88, 0x07, 0xD0])
    assert frame[-1] == reference_checksum(frame[1:8])


def test_parse_valid_measurement_response() -> None:
    data = bytes([0x03, 0xE8, 0x41, 0x00, 0x00, 0x00])
    body = bytes([START_BYTE, COMMAND_READ_CO2]) + data
    frame = body + bytes([MhZ19Protocol.checksum(body[1:])])
    response = MhZ19Protocol.parse_response(frame, COMMAND_READ_CO2)
    assert response is not None
    assert response.co2_ppm == 1000
    assert response.temperature_celsius == 25


def test_parse_rejects_bad_checksum() -> None:
    data = bytes([0x03, 0xE8, 0x41, 0x00, 0x00, 0x00])
    body = bytes([START_BYTE, COMMAND_READ_CO2]) + data
    frame = body + bytes([0x00])
    assert MhZ19Protocol.parse_response(frame, COMMAND_READ_CO2) is None


def test_parse_rejects_wrong_command() -> None:
    data = bytes([0x03, 0xE8, 0x41, 0x00, 0x00, 0x00])
    body = bytes([START_BYTE, COMMAND_READ_CO2]) + data
    frame = body + bytes([MhZ19Protocol.checksum(body[1:])])
    assert MhZ19Protocol.parse_response(frame, 0x85) is None


def test_parse_rejects_wrong_length() -> None:
    assert MhZ19Protocol.parse_response(b"\xFF\x86\x00", COMMAND_READ_CO2) is None


def test_abc_status_response() -> None:
    data = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x01])
    body = bytes([START_BYTE, 0x7D]) + data
    frame = body + bytes([MhZ19Protocol.checksum(body[1:])])
    response = MhZ19Protocol.parse_response(frame, 0x7D)
    assert response is not None
    assert response.abc_enabled is True


def test_firmware_and_range_responses() -> None:
    firmware_body = bytes([START_BYTE, 0xA0]) + b"0430" + b"\x00\x00"
    firmware_frame = firmware_body + bytes([MhZ19Protocol.checksum(firmware_body[1:])])
    firmware = MhZ19Protocol.parse_response(firmware_frame, 0xA0)
    assert firmware is not None and firmware.firmware_version == "0430"

    range_body = bytes([START_BYTE, 0x9B]) + (5000).to_bytes(4, "big") + b"\x00\x00"
    range_frame = range_body + bytes([MhZ19Protocol.checksum(range_body[1:])])
    detection_range = MhZ19Protocol.parse_response(range_frame, 0x9B)
    assert detection_range is not None and detection_range.detection_range_ppm == 5000
