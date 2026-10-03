#!/usr/bin/env bash
#
# Commands to build, flash, provision and monitor the room-climate devices.
#
# Binaries and the firmware images are looked up in `BIN_DIR` (the script's own
# directory by default); per-run logs are written next to them.
#
# Usage:
#   ./room-climate.sh                      # long-term CO2 monitoring (default)
#   ./room-climate.sh update               # update the app only (keeps Wi-Fi creds)
#   ./room-climate.sh flash                # full flash at 0x0 (wipes nvs/creds)
#   ./room-climate.sh serial               # show the ESP32 USB serial output
#   ./room-climate.sh wifi                 # send Wi-Fi SSID/password to the ESP32
#   BIN_DIR=~/room-climate-bin ./room-climate.sh
#   INTERVAL_SECONDS=10 ./room-climate.sh
#   FLASH_PORT=/dev/ttyUSB0 MONITOR_BAUD=115200 ./room-climate.sh update

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${BIN_DIR:-$SCRIPT_DIR}"

LIVENESS="$BIN_DIR/mh_z19_liveness"
CALIBRATE="$BIN_DIR/mh_z19_calibrate"
MONITOR="$BIN_DIR/mh_z19_monitor"
# Merged full image (bootloader + partition table + app), flash at 0x0.
# Flashing it also writes 0xFF over the nvs partition, so saved Wi-Fi
# credentials are erased; use `update` to keep them.
FIRMWARE_BIN="${FIRMWARE_BIN:-$BIN_DIR/room-climate-firmware.bin}"
# App-only image, written at 0x10000; leaves bootloader, partition table and
# nvs (Wi-Fi credentials) untouched.
APP_FIRMWARE_BIN="${APP_FIRMWARE_BIN:-$BIN_DIR/room-climate-firmware-app.bin}"
# Bundled, static, no-install flasher shipped next to the binaries.
BUNDLED_FLASH="$BIN_DIR/espflash"

INTERVAL_SECONDS="${INTERVAL_SECONDS:-10}"
FLASH_PORT="${FLASH_PORT:-/dev/ttyUSB0}"
MONITOR_BAUD="${MONITOR_BAUD:-115200}"
# Images at least this large are the merged full image and go to 0x0; a small
# app-only image goes to the factory application offset.
MERGED_IMAGE_MIN_BYTES=1048576
MERGED_FLASH_OFFSET=0x0
APP_FLASH_OFFSET=0x10000
MODE="${1:-monitor}"

require_binary() {
    if [ ! -x "$1" ]; then
        echo "ERROR: binary not found or not executable: $1" >&2
        echo "Put the binaries next to this script or set BIN_DIR." >&2
        exit 1
    fi
}

run_monitor() {
    require_binary "$MONITOR"
    echo
    echo "=== long-term monitoring (Ctrl+C to stop) ==="
    "$MONITOR" --interval "$INTERVAL_SECONDS"

    # Other tools (uncomment when needed):
    # "$LIVENESS"
    # "$CALIBRATE"
}

flash_offset() {
    # An explicit FLASH_OFFSET always wins.
    if [ -n "${FLASH_OFFSET:-}" ]; then
        printf '%s' "$FLASH_OFFSET"
        return
    fi
    local size
    size=$(wc -c < "$FIRMWARE_BIN" 2>/dev/null || echo 0)
    if [ "$size" -ge "$MERGED_IMAGE_MIN_BYTES" ]; then
        printf '%s' "$MERGED_FLASH_OFFSET"
    else
        printf '%s' "$APP_FLASH_OFFSET"
    fi
}

# Write one image to a flash offset with whichever flasher is available.
write_image() {
    local image="$1"
    local offset="$2"
    if [ ! -f "$image" ]; then
        echo "ERROR: firmware image not found: $image" >&2
        echo "Build the ESP32 firmware first; see firmware/README.md." >&2
        return 1
    fi
    echo "Writing $image to $FLASH_PORT at $offset ..."
    if [ -x "$BUNDLED_FLASH" ]; then
        "$BUNDLED_FLASH" write-bin --port "$FLASH_PORT" "$offset" "$image"
    elif command -v espflash >/dev/null 2>&1; then
        espflash write-bin --port "$FLASH_PORT" "$offset" "$image"
    elif command -v esptool >/dev/null 2>&1; then
        esptool --chip esp32 --port "$FLASH_PORT" write_flash \
            "$offset" "$image"
    elif command -v esptool.py >/dev/null 2>&1; then
        esptool.py --chip esp32 --port "$FLASH_PORT" write_flash \
            "$offset" "$image"
    else
        echo "ERROR: no flasher found (looked for $BUNDLED_FLASH, espflash, esptool)" >&2
        return 1
    fi
}

# Full flash from 0x0: also resets the bootloader, partition table and nvs.
flash_firmware() {
    write_image "$FIRMWARE_BIN" "$(flash_offset)"
}

# App-only update at 0x10000: keeps the bootloader, partition table and the
# saved Wi-Fi credentials in nvs.
update_firmware() {
    write_image "$APP_FIRMWARE_BIN" "$APP_FLASH_OFFSET"
    echo "Application updated; saved Wi-Fi credentials were left untouched."
}

serial_monitor() {
    echo "Watching $FLASH_PORT at $MONITOR_BAUD baud (Ctrl+C to stop)."
    echo "If no ESP32 output appears, press CTRL+R in the monitor to reset the chip."
    if [ -x "$BUNDLED_FLASH" ]; then
        "$BUNDLED_FLASH" monitor --port "$FLASH_PORT" --monitor-baud "$MONITOR_BAUD"
    elif command -v espflash >/dev/null 2>&1; then
        espflash monitor --port "$FLASH_PORT" --monitor-baud "$MONITOR_BAUD"
    elif command -v picocom >/dev/null 2>&1; then
        picocom -b "$MONITOR_BAUD" "$FLASH_PORT"
    elif command -v screen >/dev/null 2>&1; then
        screen "$FLASH_PORT" "$MONITOR_BAUD"
    else
        echo "Falling back to raw cat; exit with Ctrl+C." >&2
        stty -F "$FLASH_PORT" "$MONITOR_BAUD" raw -echo
        cat "$FLASH_PORT"
    fi
}

# Wi-Fi provisioning is done by the bundled `mh_z19_provision` binary: it
# drives the ESP32 reset lines (DTR/RTS) itself so the application is running
# even right after a flash, waits for the firmware provisioning prompt, writes
# the credentials and then reboots the chip to confirm the record was really
# stored (the `stored credentials found` boot line is read back from flash, so
# interleaved console lines cannot cause a false failure). The password is read
# with hidden input and is never logged.
provision_wifi() {
    local provision="$BIN_DIR/mh_z19_provision"
    require_binary "$provision"
    "$provision" --port "$FLASH_PORT"
}

echo "Using binaries from: $BIN_DIR"

case "$MODE" in
    monitor) run_monitor ;;
    update) update_firmware || exit 1 ;;
    flash) flash_firmware || exit 1 ;;
    serial) serial_monitor ;;
    wifi) provision_wifi || exit 1 ;;
    *)
        echo "usage: $0 [monitor|update|flash|serial|wifi]" >&2
        exit 2
        ;;
esac

echo
echo "Done. Log files were written to $BIN_DIR."
