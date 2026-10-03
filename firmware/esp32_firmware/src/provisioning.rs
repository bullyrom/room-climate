//! Wi-Fi credential provisioning over the USB serial console.
//!
//! When no credentials are stored, the firmware waits for two lines from the
//! serial port (`wifi <ssid>` and `pass <password>`), keeps them in memory and
//! never echoes the password back.

use alloc::string::String;
use alloc::vec::Vec;

use esp_hal::Blocking;
use esp_hal::uart::Uart;
use crate::console::println;

use crate::credentials::Credentials;

/// Line prefix that introduces the SSID.
const SSID_COMMAND: &str = "wifi ";
/// Line prefix that introduces the password.
const PASSWORD_COMMAND: &str = "pass ";
/// Maximum raw line length kept in memory (a little above the password limit).
const LINE_MAX_BYTES: usize = 160;

/// Reads credentials from a serial console.
pub struct SerialProvisioner<'d> {
    serial: Uart<'d, Blocking>,
    line: Vec<u8>,
}

impl<'d> SerialProvisioner<'d> {
    /// Wrap the USB serial console UART.
    pub fn new(serial: Uart<'d, Blocking>) -> Self {
        Self {
            serial,
            line: Vec::new(),
        }
    }

    /// Prompt for and collect a complete credential pair.
    pub fn collect(&mut self) -> Credentials {
        println!("wifi: no credentials stored");
        println!("wifi: send 'wifi <ssid>' then 'pass <password>'");
        let mut ssid: Option<String> = None;
        let mut password: Option<String> = None;
        loop {
            let line = self.read_line();
            if let Some(value) = line.strip_prefix(SSID_COMMAND) {
                ssid = Some(String::from(value));
                println!("wifi: ssid accepted");
            } else if let Some(value) = line.strip_prefix(PASSWORD_COMMAND) {
                password = Some(String::from(value));
                println!("wifi: password accepted");
            } else {
                println!("wifi: send 'wifi <ssid>' then 'pass <password>'");
            }

            // Only consume the values once both are present. Taking them as a
            // tuple unconditionally would discard the first credential on the
            // next iteration, so the pair would never be complete.
            match (ssid.take(), password.take()) {
                (Some(ssid_value), Some(password_value)) => {
                    match Credentials::new(ssid_value, password_value) {
                        Some(credentials) => return credentials,
                        None => println!("wifi: credentials invalid or too long, start again"),
                    }
                }
                (ssid_slot, password_slot) => {
                    ssid = ssid_slot;
                    password = password_slot;
                }
            }
        }
    }

    /// Block until a full line is received, returning it without the newline.
    fn read_line(&mut self) -> String {
        loop {
            let mut byte = [0u8; 1];
            if self.serial.read(&mut byte).is_err() {
                continue;
            }
            match byte[0] {
                b'\n' => {
                    let bytes = core::mem::take(&mut self.line);
                    return String::from_utf8_lossy(&bytes).into_owned();
                }
                b'\r' => {}
                value => {
                    if self.line.len() < LINE_MAX_BYTES {
                        self.line.push(value);
                    }
                }
            }
        }
    }
}
