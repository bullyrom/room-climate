//! Whole-line atomic console output.
//!
//! `esp_println`'s `println!` writes each format piece separately, so two tasks
//! can interleave their characters on the shared UART (seen as
//! `wifi: credep=29C`). Each line is formatted into a fixed stack buffer and
//! written with a single `Printer::write_bytes` call, which holds the critical
//! section for the whole byte slice. The fixed buffer means logging never
//! allocates, so it works even before the heap is initialised.

use core::fmt;
use core::fmt::Write as _;

use esp_println::Printer;

use crate::write_buffer::WriteBuffer;

/// Maximum length of one console line; longer lines are truncated.
const LINE_CAPACITY: usize = 256;

/// Serialises whole-line writes across cores.
///
/// A critical section only masks interrupts on the current core, so two tasks
/// running on different cores could still interleave. This spinlock is global,
/// so every line is written by one core at a time.
static CONSOLE_LOCK: esp_sync::RawMutex = esp_sync::RawMutex::new();

/// Format `args` into one line and write it atomically.
pub fn print_line(args: fmt::Arguments) {
    let mut line = WriteBuffer::<LINE_CAPACITY>::new();
    let _ = line.write_fmt(args);
    line.push_byte(b'\n');
    write_atomic(line.as_bytes());
}

/// Write already-built ASCII bytes as one atomic line (a newline is appended).
#[allow(dead_code)]
pub fn write_line(text: &[u8]) {
    let mut line = WriteBuffer::<LINE_CAPACITY>::new();
    line.push_bytes(text);
    line.push_byte(b'\n');
    write_atomic(line.as_bytes());
}

/// Write one complete line under the global cross-core lock.
fn write_atomic(bytes: &[u8]) {
    CONSOLE_LOCK.lock(|| Printer::write_bytes(bytes));
}

macro_rules! println {
    ($($arg:tt)*) => {
        $crate::console::print_line(format_args!($($arg)*))
    };
}

pub(crate) use println;
