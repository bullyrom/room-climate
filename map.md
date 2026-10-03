# Architecture map

The project is a pipeline of single-responsibility steps. Each step receives its
inputs as arguments and returns value objects; there is no shared global state.

## Calibration pipeline

Order: `SensorIdentifier` → `SensorLiveness` → `SensorCalibrator`, coordinated
by `CalibrationPipeline`, formatted by `ReportFormatter` and logged by
`DiagnosticLogger`.

| File | Class | Responsibility | Input | Output |
|---|---|---|---|---|
| `room_climate/mh_z19_protocol.py` | `MhZ19Protocol` | Build and parse 9-byte MH-Z19 frames, compute checksum | command code, bytes / raw frame | command `bytes` / `MhZ19Response` |
| `room_climate/mh_z19_response.py` | `MhZ19Response` | Typed access to response payload fields | command, 6 payload bytes | `co2_ppm`, `temperature_celsius`, `firmware_version`, `detection_range_ppm`, `abc_enabled`, raw diagnostics |
| `room_climate/serial_transport.py` | `SerialTransport` | Own the pyserial connection and exchange frames | port, baud rate, request, length | response `bytes` |
| `room_climate/mh_z19_client.py` | `MhZ19Client` | High-level MH-Z19 commands over the transport | transport | `MhZ19Response` / `str` / `int` / `bool` |
| `room_climate/sensor_identifier.py` | `SensorIdentifier` | Identify the attached sensor family | `MhZ19Client` | `SensorIdentity` |
| `room_climate/sensor_identity.py` | `SensorIdentity` | Identity value object | — | — |
| `room_climate/sensor_liveness.py` | `SensorLiveness` | Sample the sensor and decide health | `MhZ19Client`, sample count/interval | `LivenessReport` |
| `room_climate/liveness_verdict.py` | `LivenessVerdict` | Enum of health states | — | — |
| `room_climate/liveness_report.py` | `LivenessReport` | Liveness value object | — | — |
| `room_climate/sensor_calibrator.py` | `SensorCalibrator` | Run calibration and ABC commands | `MhZ19Client` | `CalibrationResult` / `bool` |
| `room_climate/calibration_outcome.py` | `CalibrationOutcome` | Enum of operation outcomes | — | — |
| `room_climate/calibration_result.py` | `CalibrationResult` | Single operation result | — | — |
| `room_climate/calibration_pipeline.py` | `CalibrationPipeline` | Coordinate steps, optional ABC change and zero point calibration, apply safety rules | identifier, liveness, calibrator, flags | `CalibrationSummary` |
| `room_climate/calibration_summary.py` | `CalibrationSummary` | Combined result value object | — | — |
| `room_climate/report_formatter.py` | `ReportFormatter` | Render a calibration summary or liveness report as text or JSON | `CalibrationSummary` / `LivenessReport` | `str` |
| `room_climate/calibration_cli.py` | `CalibrationCli` | Parse arguments, wire the pipeline, log to console and file | `argv` | exit code |

Entry point: `calibrate.py` → `StartupGuard` → `CalibrationCli` (built as
`mh_z19_calibrate`).

## Liveness diagnostic (user-side binary)

Order: `SerialPortFinder` → `SensorLiveness`, coordinated by `LivenessCli`,
rendered by `ReportFormatter` and written to console and file by
`DiagnosticLogger`.

| File | Class | Responsibility | Input | Output |
|---|---|---|---|---|
| `room_climate/startup_guard.py` | `StartupGuard` | Announce the environment, guarantee a log file and report early failures | tool name, argv | exit code |
| `room_climate/serial_port_finder.py` | `SerialPortFinder` | Resolve the serial port, preferring USB-UART adapters, and list ports | explicit port | port `str`, port list |
| `room_climate/diagnostic_logger.py` | `DiagnosticLogger` | Configure console and per-run timestamped file logging with a temp-dir fallback | filename | `logging.Logger` |
| `room_climate/liveness_cli.py` | `LivenessCli` | Parse arguments, run the diagnosis, map verdicts to exit codes | `argv` | exit code |
| `portable_toolchain.py` | `PortableToolchain` | Provision a `uv`-managed Python (glibc 2.17) for the build | toolchain dir | interpreter `Path` |
| `binary_builder.py` | `BinaryBuilder` | Build `mh_z19_liveness`, `mh_z19_calibrate`, `mh_z19_monitor` and `mh_z19_provision` through the portable toolchain and publish them to the artifact directory | — | binary `Path` list |

Entry point: `diagnose.py` → `StartupGuard` → `LivenessCli`. The `LivenessReport`
is rendered by `ReportFormatter.format_liveness`, which the calibration report
also reuses.

## Long-term monitoring (user-side binary)

Order: `MonitoringSession` polls `MhZ19Client` and logs every sample through
`DiagnosticLogger`, coordinated by `MonitoringCli`.

| File | Class | Responsibility | Input | Output |
|---|---|---|---|---|
| `room_climate/monitoring_sample.py` | `MonitoringSample` | Timestamped measurement value object | — | — |
| `room_climate/monitoring_session.py` | `MonitoringSession` | Poll the sensor periodically, log each sample and a summary, keep going on read errors | client, logger, interval, duration | exit code |
| `room_climate/monitoring_cli.py` | `MonitoringCli` | Parse arguments (port, interval, duration), run the session | `argv` | exit code |

Entry point: `monitor.py` → `StartupGuard` → `MonitoringCli` (built as
`mh_z19_monitor`).

## Wi-Fi provisioning (user-side binary)

Order: `WifiProvisioner` resets the ESP32 with DTR/RTS, waits for the firmware
prompt, writes the credentials and then reboots the chip and confirms the record
by reading the `stored credentials found` boot line, coordinated by
`ProvisionCli`.

| File | Class | Responsibility | Input | Output |
|---|---|---|---|---|
| `room_climate/provision_outcome.py` | `ProvisionOutcome` | Enum of provisioning results | — | — |
| `room_climate/wifi_provisioner.py` | `WifiProvisioner` | Reset the chip into the app, wait for the prompt, send the credentials, reboot and confirm by fact (the stored record read back from flash) | open serial connection, ssid, password | `ProvisionOutcome` |
| `room_climate/provision_cli.py` | `ProvisionCli` | Parse arguments (ready/confirm/verify timeouts), prompt for the SSID/password (hidden), run the provisioner, log the device output | `argv` | exit code |

Entry point: `provision.py` → `StartupGuard` → `ProvisionCli` (built as
`mh_z19_provision`). The password is read with `getpass` and never logged.

## Dependencies

- `pyserial` — serial transport.
- `uv` — provisions the glibc-2.17 build interpreter (installs `pyinstaller`
  and `pyserial` into `.build-toolchain/`).

## Standalone diagnostic binaries

`mh_z19_liveness`, `mh_z19_calibrate`, `mh_z19_monitor` and
`mh_z19_provision` are built with a `uv`-managed Python that only needs glibc
2.17, so they run on systems with an older glibc, and are published to the
artifact directory (override with `ARTIFACT_DIR`). Each run starts with a
`StartupGuard` banner on the console, writes its own timestamped log next to the
binary (`mh_z19_<tool>_<timestamp>.log`) and falls back to the temp directory if
that location is not writable. All CLIs log the detected serial ports and catch
every exception with a traceback, and `--list-ports` prints the available ports
and exits. See `README.md`.

## Tests

- `tests/test_mh_z19_protocol.py` — checksum, frame building, response parsing.
- `tests/test_sensor_liveness.py` — liveness verdicts.
- `tests/test_calibration_pipeline.py` — calibration safety, ABC and decision logic.
- `tests/test_liveness_cli.py` — exit codes, report formatting, port fallback.
- `tests/test_monitoring_session.py` — periodic sampling loop and summary.
- `tests/test_diagnostic_logger.py` — console and file logging.
- `tests/test_startup_guard.py` — startup banner, log injection and crash reporting.
- `tests/test_portable_toolchain.py` — build toolchain interpreter path.
- `tests/test_wifi_provisioner.py` — provisioning prompt, save confirmation and retry logic.
