//! MH-Z19C driver over UART2.
//!
//! On top of the plain read loop this keeps the raw command and response bytes
//! (and the first UART error); the `mhz19-debug` cargo feature prints them to
//! the serial console so a missing or garbled reply is visible on the wire.

use embedded_io::Write;
use esp_hal::delay::Delay;
use esp_hal::time::{Duration, Instant};
use esp_hal::uart::{RxError, Uart};
use esp_hal::Blocking;
use mh_z19_protocol::{build_read_command, parse_response, Measurement, FRAME_LENGTH};

use crate::config;

/// One command/response cycle with the raw wire data kept for diagnostics.
pub struct Frame {
    /// The command sent to the sensor (used by the `mhz19-debug` output).
    #[cfg_attr(not(feature = "mhz19-debug"), allow(dead_code))]
    pub command: [u8; FRAME_LENGTH],
    /// Raw response bytes, zero-padded up to `FRAME_LENGTH`.
    pub bytes: [u8; FRAME_LENGTH],
    /// Number of valid bytes in `bytes`.
    pub length: usize,
    /// First UART error seen while collecting the response (used by the
    /// `mhz19-debug` output).
    #[cfg_attr(not(feature = "mhz19-debug"), allow(dead_code))]
    pub error: Option<RxError>,
}

impl Frame {
    /// The received bytes without the zero padding (used by the `mhz19-debug`
    /// output).
    #[cfg_attr(not(feature = "mhz19-debug"), allow(dead_code))]
    pub fn received(&self) -> &[u8] {
        &self.bytes[..self.length]
    }

    /// Decode the response, or `None` when it is incomplete or malformed.
    pub fn measurement(&self) -> Option<Measurement> {
        if self.length == FRAME_LENGTH {
            parse_response(&self.bytes)
        } else {
            None
        }
    }
}

/// Blocking MH-Z19C driver owning its UART link.
pub struct MhZ19<'d> {
    uart: Uart<'d, Blocking>,
    delay: Delay,
}

impl<'d> MhZ19<'d> {
    /// Wrap an already configured UART link.
    pub fn new(uart: Uart<'d, Blocking>) -> Self {
        Self {
            uart,
            delay: Delay::new(),
        }
    }

    /// Read one measurement, retrying malformed frames up to `attempts` times.
    ///
    /// Returns the last attempt, so the caller can log its raw bytes and error
    /// even when no valid frame was received.
    pub fn read(&mut self, attempts: u8) -> Frame {
        let mut last = self.read_once();
        let mut remaining = attempts.saturating_sub(1);
        while remaining > 0 && last.measurement().is_none() {
            last = self.read_once();
            remaining -= 1;
        }
        last
    }

    /// Send the read command and collect a response within a bounded timeout.
    fn read_once(&mut self) -> Frame {
        let command = build_read_command();
        let _ = self.uart.write_all(&command);
        let _ = self.uart.flush();

        let mut bytes = [0u8; FRAME_LENGTH];
        let mut length = 0usize;
        let mut error = None;
        let start = Instant::now();
        let timeout = Duration::from_millis(config::MHZ19_FRAME_TIMEOUT_MS);

        while length < FRAME_LENGTH && start.elapsed() < timeout {
            match self.uart.read_buffered(&mut bytes[length..]) {
                Ok(0) => {}
                Ok(read) => length += read,
                Err(rx_error) => {
                    if error.is_none() {
                        error = Some(rx_error);
                    }
                }
            }
            if length < FRAME_LENGTH {
                self.delay.delay_millis(config::MHZ19_POLL_INTERVAL_MS);
            }
        }

        Frame {
            command,
            bytes,
            length,
            error,
        }
    }
}
