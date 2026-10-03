# Project rules

`room-climate` is a CO2/room-climate monitoring toolkit: Python diagnostics for
the Winsen MH-Z19 family (MH-Z19B/C) over USB-UART, and an ESP32 firmware
(Rust / esp-hal) that reads the sensor and serves the latest reading over HTTP.

## Build and run

- Python tools: `poetry install`, then `poetry run python <tool>.py --help`.
- User-side binaries: `poetry run python binary_builder.py` builds
  `mh_z19_liveness`, `mh_z19_calibrate`, `mh_z19_monitor` and
  `mh_z19_provision` and copies `room-climate.sh` next to them. Set
  `ARTIFACT_DIR` to choose the output directory (default: `artifacts/`).
- ESP32 firmware: see `firmware/README.md`.

## Flashing and provisioning

- `./room-climate.sh flash` writes the merged full image at `0x0`; it also
  overwrites the `nvs` partition, so it **erases the saved Wi-Fi credentials**.
  Use it on a clean board only.
- `./room-climate.sh update` writes only the app image at `0x10000`, so the
  bootloader, partition table and saved Wi-Fi credentials survive. Use it for
  every firmware update after the first flash.
- `./room-climate.sh wifi` provisions the Wi-Fi SSID/password over the USB
  serial console; the password is read with hidden input and never logged.
- `./room-climate.sh serial` watches the ESP32 USB serial output.

## Conventions

- Python: one class per file, a pipeline of single-responsibility steps, full
  type hints and English docstrings. See `map.md`.
- Do not hard-code numeric literals in code; use named constants.
- Keep the architecture map (`map.md`) and `RELEASE_NOTES.md` up to date.
