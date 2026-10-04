# ESP32 firmware (Rust / esp-hal)

Firmware for the room-climate node. ESP32 powered over USB, one **MH-Z19C CO2**
sensor on UART, measurements printed to the USB serial console, a **Wi-Fi
station** connection whose credentials are provisioned over that same USB
serial console, and an **HTTP server** that serves the latest CO2/temperature
reading as JSON on port 80. An onboard I2C temperature/humidity sensor
(AHT20/SHT31) for a single self-contained device is a future stage.

The Wi-Fi stack links Espressif's precompiled radio blob (`libnet80211.a`,
`libpp.a`, `libcore.a`). It is only linked into the image and executes solely on
the ESP32; it never runs on the host.

## Layout

- `mh_z19_protocol/` — `no_std` MH-Z19C frame building/parsing; unit-tested on
  the host (`cargo test -p mh_z19_protocol`).
- `esp32_firmware/` — the ESP32 binary `room-climate-firmware`: reads the UART
  sensor, prints to serial and connects to Wi-Fi.
- `esp32_firmware/src/credentials.rs` — SSID/password record in the flash `nvs`
  partition (magic + checksum, password never logged).
- `esp32_firmware/src/provisioning.rs` — serial `wifi <ssid>` / `pass <password>`
  input when no credentials are stored.
- `esp32_firmware/src/wifi_link.rs` — builds the station config and connects.
- `esp32_firmware/src/telemetry.rs` — latest reading shared between tasks.
- `esp32_firmware/src/sensor.rs` — MH-Z19 sampling task.
- `esp32_firmware/src/http_server.rs` — embassy-net runner and the HTTP task.

## Wiring (defaults)

| Signal | ESP32 pin | MH-Z19C |
|---|---|---|
| ESP RX | GPIO16 | MH-Z19 TX |
| ESP TX | GPIO17 | MH-Z19 RX |
| VIN / GND | 5V / GND | VIN / GND |

## Build

Requires the esp-rs Xtensa toolchain:

```bash
cargo install espup
espup install --targets esp32     # installs the `esp` toolchain + GCC
. "$HOME/export-esp.sh"           # every new shell
```

Then, from `firmware/`:

```bash
cargo test -p mh_z19_protocol          # host unit tests, no board needed
cargo build -p esp32-firmware --release --target xtensa-esp32-none-elf

# Optional: print the raw MH-Z19 command/response bytes and UART errors.
cargo build -p esp32-firmware --release --target xtensa-esp32-none-elf \
  --features mhz19-debug
```

The default build logs only `MEASUREMENT co2=... temp=...` and the start-up
lines; the raw wire traffic is compiled out unless `mhz19-debug` is enabled.

The `.cargo/config.toml` passes `-Tlinkall.x` and builds `core`/`alloc` from
`rust-src` (`build-std`), which Xtensa needs. The provisioning read loop must
actually return after both credentials arrive; if it never returns the
optimizer correctly removes the whole save path as dead code (this once
happened because `collect` unconditionally `take()`-ed the two `Option`s).

Flash writes require interrupts disabled and the second core parked; the
firmware enables `esp-storage/critical-section` (esp-bootloader otherwise builds
it with `default-features = false`) and calls `multicore_auto_park()`.

Create the flashable images and publish them:

```bash
# Merged full image (bootloader + partition table + app), flash at 0x0.
# This is what a clean ESP32 needs; published as room-climate-firmware.bin.
espflash save-image --chip esp32 --merge \
  target/xtensa-esp32-none-elf/release/room-climate-firmware \
  artifacts/room-climate-firmware.bin

# App-only image, flash at 0x10000 (for updating an already-flashed board).
esptool --chip esp32 elf2image --output \
  artifacts/room-climate-firmware-app.bin \
  target/xtensa-esp32-none-elf/release/room-climate-firmware
```

## Flash and monitor

`room-climate.sh` uses a bundled static `espflash` when one is present next to
the images (`$BIN_DIR/espflash`); otherwise it falls back to `espflash`,
`esptool` or `esptool.py` from `PATH`. With `BIN_DIR` pointing at the artifact
directory:

```bash
cd artifacts
./room-climate.sh update    # update the app only (keeps Wi-Fi credentials)
./room-climate.sh flash     # full merged image at 0x0 (use on a clean board)
./room-climate.sh serial    # watch the USB serial output at 115200 baud (Ctrl+C to exit)
```

Equivalent raw commands:

```bash
./espflash write-bin --port /dev/ttyUSB0 0x10000 room-climate-firmware-app.bin
./espflash write-bin --port /dev/ttyUSB0 0x0     room-climate-firmware.bin
./espflash monitor   --port /dev/ttyUSB0 --monitor-baud 115200
```

`room-climate-firmware.bin` is a **merged full image** (bootloader + partition
table + app) padded to the whole 4 MiB flash and written at `0x0`. Because it
covers the entire flash, it also writes `0xFF` over the `nvs` partition
(`0x9000`) and **erases the saved Wi-Fi credentials** — use it on a fresh board.

`room-climate-firmware-app.bin` is the **app-only** image. Written at `0x10000`
it leaves the bootloader, partition table and `nvs` untouched, so **saved Wi-Fi
credentials survive**. That is what `./room-climate.sh update` runs; use it for
every firmware update after the first flash.

`FLASH_PORT` (default `/dev/ttyUSB0`) and `MONITOR_BAUD` (default `115200`)
override the defaults. If the port is not accessible, add your user to the
`dialout` group (`sudo usermod -aG dialout "$USER"`, then re-login).

Serial output looks like:

```
room-climate firmware (WiFi+HTTP) starting
wifi: stored credentials found for ssid=my-network
wifi: connected to ssid=my-network
mhz19 ready: rx=gpio16 tx=gpio17 baud=9600
MEASUREMENT co2=812ppm temp=22C
http: serving on http://<device-ip>/
```

## Wi-Fi provisioning

On first boot (or whenever the `nvs` partition holds no credential record) the
firmware waits on the USB serial console for two lines:

```
wifi <ssid>
pass <password>
```

The lines arrive on **UART0** (`RX = GPIO3`, `TX = GPIO1`, 115200 baud) — the
same USB serial console used for the log (the firmware connects the RX pin
explicitly, or it would only print). It stores them in the `nvs` flash
partition and then connects; later boots connect immediately. The password is
never echoed, logged or written anywhere except the flash record. The
credentials are provisioned from the laptop with `room-climate.sh`:

```bash
cd artifacts
./room-climate.sh flash        # flash the merged image, then the board asks for Wi-Fi
./room-climate.sh wifi         # asks for SSID (typed) and password (hidden) and sends them
./room-climate.sh serial       # watch the connection result
```

`room-climate.sh wifi` runs the bundled `mh_z19_provision` binary, which reads
the SSID normally and the password with hidden input and never logs the
password. It drives the ESP32 reset lines (DTR/RTS) itself, so it resets the
chip into the application even when it is still in the serial bootloader stub
after a flash, waits for the firmware's provisioning prompt before writing, and
then reboots the chip and waits for the `wifi: stored credentials found for
ssid=...` boot line (retrying once). The firmware reads the record back from
flash at boot, so this confirmation is proof by fact and does not depend on the
order in which the save log lines arrive. If the board already has credentials
and you want to change them, erase the `nvs` partition first
(`esptool erase_region 0x9000 0x6000`) and reboot.

## HTTP API

After Wi-Fi connects, the firmware brings up an IP stack (`embassy-net`,
DHCP) and serves HTTP on **port 80** as a separate task, so Wi-Fi and the
MH-Z19 sampling keep running. `GET /` (any path) returns the latest reading:

```json
{"co2":812,"temp":22}
```

Before the first measurement the body is `{"co2":null,"temp":null}`. The
address is printed at boot, e.g. `http: serving on http://<device-ip>/`. Give
the router a DHCP reservation (or a static lease) so that address is stable,
then check it from the local network:

```bash
curl http://<device-ip>/
# {"co2":812,"temp":22}
```

## Diagnostics

The normal build logs only the start-up lines and `MEASUREMENT co2=... temp=...`
(or `sample incomplete: no valid MH-Z19 frame`). Build with `--features
mhz19-debug` to also log the raw command (`mhz19 tx`), the raw response
(`mhz19 rx`) and, when the UART reports one, `mhz19 uart error: <kind>`. Read
those lines as follows:

| Serial output | Meaning |
|---|---|
| `mhz19 rx (0 bytes)` with a `mhz19 uart error` | Noise or wrong baud on RX: the line is floating/short. Check the sensor TX -> GPIO16 wire, the common ground and start-up. |
| `mhz19 rx (0 bytes)` and no error | The RX line sits clean but the sensor never replies: bad wiring, no 5V on VIN, or the sensor is still warming up (first reading can take up to ~3 min). |
| Checked bytes but `sample incomplete` | Something arrives, but not a valid `FF 86 ...` frame with a matching checksum. Compare the hex against the table below. |
| `mhz19 uart error: frame format violated` | The RX level or baud rate does not match (often a floating line or a clone that rejects the 3.3V ESP32 TX level). |

Known **clones** (the identification tool flags a 10000 ppm range) sometimes do
not accept the ESP32's 3.3V TX as a valid HIGH on their RX pin and therefore
never answer. The software cannot fix this; use a 5V logic level shifter (or a
5V-tolerant buffer) between ESP32 GPIO17 and the sensor RX, keep VIN on 5V,
and keep the grounds common. Genuine MH-Z19C modules accept 3.3V logic.

Console output is on UART0 (`esp-println`), i.e. GPIO1 TX / GPIO3 RX, at
**115200 baud** — the same UART used for flashing. If the monitor connects but
shows nothing, the chip did not restart into the app: press **CTRL+R** in the
monitor (or the board's EN/RESET button, or re-plug USB). The firmware prints
its banner before any peripheral setup, so total silence means no reset or a
console wiring issue, not a silent panic.

## Note on versions

The exact `esp-hal` / `esp-println` / `esp-backtrace` /
`esp-bootloader-esp-idf` versions and some HAL builder calls (`Uart::new`) must
match the installed espup toolchain; run `cargo add` and adjust if the API
differs. The Wi-Fi stack uses `esp-radio` (the renamed `esp-wifi`) together with
`esp-rtos`; `esp-radio` version `1.0.0-beta.1` is the release that matches
`esp-hal` 1.2.x (the older `esp-radio` 0.17 requires `xtensa-lx-rt` 0.21, which
conflicts with `esp-hal` 1.2).
