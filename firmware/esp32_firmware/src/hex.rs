//! Hexadecimal dump of raw UART traffic for the serial console.

use core::fmt::Write as _;

use crate::write_buffer::WriteBuffer;

/// Maximum length of one hex dump line.
const HEX_LINE_CAPACITY: usize = 256;

/// Print a labelled byte slice as space-separated uppercase hex plus its length.
pub fn print_frame(label: &str, bytes: &[u8]) {
    let mut line = WriteBuffer::<HEX_LINE_CAPACITY>::new();
    let _ = write!(line, "{} ({} bytes):", label, bytes.len());
    for byte in bytes {
        let _ = write!(line, " {:02X}", byte);
    }
    crate::console::write_line(line.as_bytes());
}
