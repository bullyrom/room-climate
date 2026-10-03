//! Board wiring and runtime configuration.
//!
//! Current milestone (USB/Serial only): ESP32 powered over USB, one MH-Z19C
//! CO2 sensor on UART2.
//!
//! - MH-Z19C UART2: ESP32 RX = GPIO16, ESP32 TX = GPIO17, VIN -> 5V, GND -> GND

/// MH-Z19C: ESP32 RX pin (sensor TX).
pub const MHZ19_RX_GPIO: u8 = 16;
/// MH-Z19C: ESP32 TX pin (sensor RX).
pub const MHZ19_TX_GPIO: u8 = 17;
/// MH-Z19C default baud rate.
pub const MHZ19_BAUD_RATE: u32 = 9_600;
/// How many times to retry a malformed frame before giving up.
pub const MHZ19_READ_ATTEMPTS: u8 = 3;
/// How long to collect response bytes before declaring the frame incomplete.
pub const MHZ19_FRAME_TIMEOUT_MS: u64 = 100;
/// Pause between UART polls while collecting a response.
pub const MHZ19_POLL_INTERVAL_MS: u32 = 1;

/// Delay between measurement cycles.
pub const SAMPLE_INTERVAL_MS: u32 = 10_000;
