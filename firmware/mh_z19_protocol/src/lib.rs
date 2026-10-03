//! MH-Z19C UART protocol: frame building and parsing.
//!
//! This crate is `no_std` and free of hardware dependencies, so it can be
//! unit-tested on the host with `cargo test -p mh_z19_protocol`.

#![no_std]

/// Length of an MH-Z19 operation-mode-0 frame in bytes.
pub const FRAME_LENGTH: usize = 9;
/// First byte of every frame.
pub const START_BYTE: u8 = 0xFF;
/// Sensor address used in command frames.
pub const SENSOR_ADDRESS: u8 = 0x01;
/// Command that reads the final CO2 concentration and temperature.
pub const COMMAND_READ_CO2: u8 = 0x86;
/// The temperature byte is offset by this many degrees.
pub const TEMPERATURE_OFFSET_CELSIUS: u8 = 40;

/// One decoded `0x86` measurement.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Measurement {
    /// CO2 concentration in ppm.
    pub co2_ppm: u16,
    /// Sensor-internal temperature in degrees Celsius.
    pub temperature_celsius: i16,
}

impl Measurement {
    /// Return the temperature in tenths of a degree (avoids floats on device).
    pub fn temperature_deci_celsius(self) -> i32 {
        self.temperature_celsius as i32 * 10
    }
}

/// Return the MH-Z19 checksum for the given payload bytes.
pub fn checksum(payload: &[u8]) -> u8 {
    let sum = payload
        .iter()
        .fold(0u8, |accumulator, byte| accumulator.wrapping_add(*byte));
    0xFFu8.wrapping_sub(sum).wrapping_add(1)
}

/// Build the 9-byte read-CO2 command (`FF 01 86 00 00 00 00 00 79`).
pub fn build_read_command() -> [u8; FRAME_LENGTH] {
    let mut frame = [0u8; FRAME_LENGTH];
    frame[0] = START_BYTE;
    frame[1] = SENSOR_ADDRESS;
    frame[2] = COMMAND_READ_CO2;
    frame[FRAME_LENGTH - 1] = checksum(&frame[1..FRAME_LENGTH - 1]);
    frame
}

/// Parse a 9-byte `0x86` response, returning `None` when it is malformed.
pub fn parse_response(frame: &[u8]) -> Option<Measurement> {
    if frame.len() != FRAME_LENGTH {
        return None;
    }
    if frame[0] != START_BYTE || frame[1] != COMMAND_READ_CO2 {
        return None;
    }
    if frame[FRAME_LENGTH - 1] != checksum(&frame[1..FRAME_LENGTH - 1]) {
        return None;
    }
    let co2_ppm = u16::from_be_bytes([frame[2], frame[3]]);
    let temperature_celsius = frame[4] as i16 - TEMPERATURE_OFFSET_CELSIUS as i16;
    Some(Measurement {
        co2_ppm,
        temperature_celsius,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn build_read_command_matches_datasheet() {
        assert_eq!(
            build_read_command(),
            [0xFF, 0x01, 0x86, 0x00, 0x00, 0x00, 0x00, 0x00, 0x79]
        );
    }

    #[test]
    fn parse_valid_response() {
        let frame = [0xFF, 0x86, 0x03, 0x2C, 0x3E, 0x00, 0x00, 0x00, 0x0D];
        assert_eq!(
            parse_response(&frame),
            Some(Measurement {
                co2_ppm: 0x032C,
                temperature_celsius: 0x3E - 40,
            })
        );
    }

    #[test]
    fn reject_bad_checksum() {
        let frame = [0xFF, 0x86, 0x03, 0x2C, 0x3E, 0x00, 0x00, 0x00, 0x00];
        assert_eq!(parse_response(&frame), None);
    }

    #[test]
    fn reject_wrong_command() {
        let frame = [0xFF, 0x85, 0x03, 0x2C, 0x3E, 0x00, 0x00, 0x00, 0x0E];
        assert_eq!(parse_response(&frame), None);
    }
}
