# room-climate

Room climate monitoring around the Winsen MH-Z19C CO2 sensor, in two parts:

- **ESP32 node (Rust / esp-hal)** — measures CO2 and temperature on UART,
  connects to Wi-Fi as a station (credentials provisioned over the USB serial
  console), and serves the latest reading as JSON over HTTP on port 80.
- **Python tools** — identify, diagnose, calibrate and log MH-Z19B/C sensors
  over USB-UART, and build the same diagnostics as standalone binaries.

## Repository layout

- `firmware/` — ESP32 firmware and the `no_std` MH-Z19 protocol crate; see
  [`firmware/README.md`](firmware/README.md) for details.
- `room_climate/` — the Python diagnostics pipeline.
- `room-climate.sh` — flash, provision and monitor helper.
- `binary_builder.py` — builds the standalone diagnostic binaries.
- `map.md` — architecture map.

## Hardware

- An ESP32 board plus one MH-Z19C sensor on UART2:

  | Signal | ESP32 pin | MH-Z19C |
  |---|---|---|
  | ESP RX | GPIO16 | MH-Z19 TX |
  | ESP TX | GPIO17 | MH-Z19 RX |
  | VIN / GND | 5V / GND | VIN / GND |

- For the Python tools: an MH-Z19B/C on a USB-UART adapter (e.g. CH340/FT232).

## Install from a prebuilt release

If you just want to use the device, download a ready build from the
[releases page](https://github.com/bullyrom/room-climate/releases) instead of
compiling. A release contains the flashable firmware image, so **no Rust/esp-rs
toolchain, no `cargo` and no `espup` are needed**. Building from source (next
section) is for development or custom changes and does require that toolchain.

1. Download `room-climate-firmware.bin`, plus `room-climate.sh` and
   `mh_z19_provision` if you want the helper scripts.
2. Flash the merged image to a clean ESP32 at offset **`0x0`** with `esptool` or
   `espflash`:

   ```bash
   # esptool
   esptool --chip esp32 --port /dev/ttyUSB0 write_flash 0x0 room-climate-firmware.bin

   # espflash
   espflash write-bin --port /dev/ttyUSB0 0x0 room-climate-firmware.bin
   ```

   Or use a browser-based ESP web flasher (for example
   [ESP Web Tools](https://esphome.github.io/esp-web-tools/)) and write the
   merged image at offset `0x0`.
3. Provision Wi-Fi over the USB serial console (the first boot prints a prompt):

   ```bash
   ./room-climate.sh wifi      # SSID typed, password hidden
   # or watch the console and enter the two provisioning lines by hand:
   ./room-climate.sh serial
   ```
4. Read the address the firmware prints and check the endpoint:

   ```bash
   curl http://<device-ip>/
   # {"co2":812,"temp":22}
   ```

Put the downloaded assets in one directory and run `./room-climate.sh ...` from
there (`BIN_DIR` defaults to the script's own directory).

### What is in a release

- `room-climate-firmware.bin` — merged full image (bootloader + partition table
  + application) padded to the whole 4 MiB flash; flash it at **`0x0`**. It
  overwrites `nvs`, so it erases any saved Wi-Fi credentials.
- `room-climate-firmware-app.bin` — application-only image; flash it at
  **`0x10000`** to update an already-provisioned board and keep the saved Wi-Fi
  credentials:

  ```bash
  esptool --chip esp32 --port /dev/ttyUSB0 write_flash 0x10000 room-climate-firmware-app.bin
  ```

- `room-climate.sh` — the flash/provision/monitor helper used above.
- `mh_z19_liveness`, `mh_z19_calibrate`, `mh_z19_monitor`, `mh_z19_provision` —
  standalone Python diagnostic binaries (Linux x86_64) that need no Python
  installation; see the Python tools section below.

## ESP32 firmware

Requires the esp-rs Xtensa toolchain:

```bash
cargo install espup
espup install --targets esp32     # installs the `esp` toolchain + GCC
. "$HOME/export-esp.sh"           # every new shell
```

Build and test from `firmware/`:

```bash
cargo test -p mh_z19_protocol                                        # host tests
cargo build -p esp32-firmware --release --target xtensa-esp32-none-elf
```

Create the flashable images (into the artifact directory next to the binaries):

```bash
# Merged full image (bootloader + partition table + app), written at 0x0.
espflash save-image --chip esp32 --merge \
  target/xtensa-esp32-none-elf/release/room-climate-firmware \
  artifacts/room-climate-firmware.bin

# App-only image, written at 0x10000 (for updating an already-flashed board).
esptool --chip esp32 elf2image --output \
  artifacts/room-climate-firmware-app.bin \
  target/xtensa-esp32-none-elf/release/room-climate-firmware
```

### Flash and monitor

Place `room-climate-firmware.bin`, `room-climate-firmware-app.bin`,
`room-climate.sh`, the `mh_z19_*` binaries and (optionally) a static `espflash`
in the same directory, then:

```bash
./room-climate.sh flash     # full merged image at 0x0: use on a clean board
./room-climate.sh update    # app image at 0x10000: keeps the Wi-Fi credentials
./room-climate.sh serial    # watch the USB serial output at 115200 baud
```

`flash` writes `0xFF` over the `nvs` partition and therefore **erases the saved
Wi-Fi credentials**; use `update` for every firmware update after the first
flash. `FLASH_PORT` (default `/dev/ttyUSB0`) and `MONITOR_BAUD` (default
`115200`) override the defaults.

### Wi-Fi provisioning

On first boot the firmware prints a prompt on the USB serial console and waits
for two lines (`wifi <ssid>` and `pass <password>`), stores them in `nvs` and
connects. Provision from the host with:

```bash
./room-climate.sh wifi      # prompts for SSID (typed) and password (hidden)
```

The password is read with hidden input and is never echoed or logged.

### HTTP API

After connecting, the firmware gets an address over DHCP and serves the latest
reading on **port 80**. `GET /` (any path) returns:

```json
{"co2":812,"temp":22}
```

Before the first measurement the body is `{"co2":null,"temp":null}`. Check it
from the local network with `curl http://<device-ip>/`.

## Python tools

### Install

```bash
poetry install
```

Requirements: Python 3.10+ and `pyserial`.

### Identification and calibration

The calibration script is read-only by default. It identifies the sensor,
checks that it is alive, and then decides whether calibration is safe.

```bash
# Identify and diagnose only (no writes)
poetry run python calibrate.py --port /dev/ttyUSB0

# Machine-readable report
poetry run python calibrate.py --port /dev/ttyUSB0 --json

# Actually write the zero-point calibration
poetry run python calibrate.py \
    --port /dev/ttyUSB0 \
    --apply --confirm-reference
```

`--apply` writes the zero-point calibration and `--confirm-reference` is the
explicit acknowledgement that the sensor has been sitting in stable 400 ppm
air (fresh outdoor air) for at least 20 minutes. Calibration is refused for a
dead or unreachable sensor.

#### Calibration safety

- **Never** zero-calibrate in an occupied room: ambient air is not 400 ppm.
- Let the sensor stabilize for at least 20 minutes in the reference air.
- Keep the sensor away from heat sources; the IR source and photo path are
  sensitive to heat and to reversed/high supply voltage.
- Automatic baseline correction (ABC) is on by default on MH-Z19 modules and
  slowly corrects for drift. The report always shows its current state.

### Standalone diagnostic binaries

The diagnostics can also run without a Python environment. Build them with a
`uv`-managed Python that targets glibc 2.17, so the binaries start on older
systems too:

```bash
poetry run python binary_builder.py
```

This produces `mh_z19_liveness`, `mh_z19_calibrate`, `mh_z19_monitor` and
`mh_z19_provision`, and copies them (together with `room-climate.sh`) into the
artifact directory. Set `ARTIFACT_DIR` to choose the output directory
(default: `artifacts/`).

```bash
./artifacts/mh_z19_liveness                          # auto-detect the USB port
./artifacts/mh_z19_liveness --port /dev/ttyUSB0 --samples 5 --interval 2
```

Every run logs to the console **and** to its own timestamped file next to the
binary, e.g. `mh_z19_liveness_20260930_215327.log`, so consecutive runs never
overwrite each other. Exit codes: `0` alive, `3` degraded, `4` dead, `5`
unreachable, `2` port open error, `1` other error. Use `--log-file PATH` to
override the generated name.

Each run begins with a `StartupGuard` banner (time, executable, cwd, argv,
Python/platform) and lists the detected serial ports, so a silent or hanging
run is visible. Every unhandled exception is written to the console **and** the
log with a full traceback, and if the binary's own directory is not writable
the log falls back to the system temp directory. `--list-ports` prints the
detected ports and exits.

#### Calibration binary

`mh_z19_calibrate` identifies the sensor, reports liveness and ABC state, and
can write the zero point and the ABC setting. It writes its own timestamped log
(`mh_z19_calibrate_*.log`).

```bash
./artifacts/mh_z19_calibrate                             # read-only report
./artifacts/mh_z19_calibrate --apply --confirm-reference --disable-abc
```

- Zero-point calibration (`0x87`) anchors the **current air** as 400 ppm, so it
  may only be run with the sensor in stable fresh air (~400 ppm) for at least
  20 minutes; `--confirm-reference` is the explicit acknowledgement.
- `--disable-abc` / `--enable-abc` write the ABC state. ABC is on by default
  and slowly drifts an indoor sensor that never sees fresh air.
- Without `--apply` the run is read-only.

#### Long-term monitoring binary

`mh_z19_monitor` measures CO2 and temperature periodically and logs one line per
sample to its own timestamped file (`mh_z19_monitor_*.log`), so a run can be
left for hours.

```bash
./artifacts/mh_z19_monitor                        # every 10 s until Ctrl+C
./artifacts/mh_z19_monitor --interval 10 --duration 3600
```

Each sample is logged as `sample <n> co2=<ppm> temperature=<C>`, and a final
line gives the count and min/max/average. Lost frames or read errors only skip
a sample, so the run continues.

#### Wi-Fi provisioning binary

`mh_z19_provision` stores the Wi-Fi SSID and password on the ESP32 over the USB
serial console. It drives the ESP32 reset lines (DTR/RTS) itself, so it works
right after a flash even when the chip is still in the serial bootloader stub:
it resets the chip into the application, waits for the firmware's provisioning
prompt, writes the credentials and then reboots the chip once more to confirm
persistence.

```bash
./artifacts/mh_z19_provision                      # auto-detect the port
./artifacts/mh_z19_provision --port /dev/ttyUSB0
```

The SSID is typed and the password is read with hidden input; the password is
never logged. If the device already holds credentials it will not ask for new
ones; erase the `nvs` partition first
(`esptool erase_region 0x9000 0x6000`) and retry.

### room-climate.sh

`room-climate.sh` collects the commands for flashing, provisioning and
monitoring. `BIN_DIR` selects the binary directory (defaults to the script's
own directory) and `INTERVAL_SECONDS` overrides the monitoring interval.

```bash
./room-climate.sh           # long-term CO2 monitoring (default)
./room-climate.sh update    # update the app only (0x10000) - keeps Wi-Fi credentials
./room-climate.sh flash     # full merged image at 0x0 (clean board; wipes nvs/creds)
./room-climate.sh wifi      # reset the ESP32 and store the Wi-Fi credentials
./room-climate.sh serial    # watch the ESP32 USB serial output at 115200 baud
```

For flashing and monitoring, the script uses a bundled `espflash` when one is
present next to the binaries (`$BIN_DIR/espflash`) and otherwise falls back to
`espflash`, `esptool` or `esptool.py` from `PATH` (and to `picocom`, `screen`
or `cat` for the serial monitor).

## Security / limitations

- **Network exposure.** The ESP32 runs as a Wi-Fi **station** and receives its
  address over DHCP, so it sits behind the router/NAT and is not reachable from
  the internet unless that is explicitly forwarded.
- **HTTP only.** The device opens exactly one port, **HTTP/80**, with **no
  authentication and no TLS**. Any host that can reach it on the local network
  can read the latest CO2/temperature JSON. The endpoint is read-only (it does
  not expose control commands), but it should not be exposed to the internet;
  use a firewall rule or a separate VLAN on an untrusted network.
- **Credential storage.** The Wi-Fi SSID and password are stored in the `nvs`
  flash partition in **plain text** (a magic header plus a checksum, not
  encryption). Physical access to the board/flash is therefore trusted:
  re-flashing or dumping the flash reveals the credentials. The provisioning
  password is sent in clear over the (local, physical) USB serial link.
- **Calibration writes.** The Python tools are read-only unless `--apply` (or
  an explicit ABC change) is passed; only then do they modify the sensor.
- **Serial access.** The host tools need permission to open the serial port;
  add your user to the `dialout` group on Linux
  (`sudo usermod -aG dialout "$USER"`, then re-login).

## Liveness verdicts

| Verdict       | Meaning                                                        |
|---------------|----------------------------------------------------------------|
| `alive`       | Valid frames with plausible CO2 and temperature                |
| `degraded`    | Responds, but values are pinned, out of range or never change  |
| `dead`        | Responds, but the sensing element does not work (e.g. light ADC is zero) |
| `unreachable` | No valid frames at all: unpowered, wrong port, or dead module  |

## Architecture

The code follows a one-class-per-file pipeline architecture; see
[`map.md`](map.md).

## Roadmap

- Add an **onboard temperature sensor** so the node is a single self-contained
  device (ESP32 + MH-Z19C + temperature sensor), for example an I2C AHT20/SHT31.
  Merge its reading with the MH-Z19C measurement in the JSON endpoint and the
  logs.
- Configurable threshold rules and notifications (ventilate when CO2 is high,
  warn when temperature or humidity leaves a comfortable band).

## License

MIT — see [`LICENSE`](LICENSE).
