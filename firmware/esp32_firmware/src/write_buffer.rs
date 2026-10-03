//! A fixed-size, allocation-free [`core::fmt::Write`] target.
//!
//! Used by the console and the HTTP server so neither the start-up banner nor
//! a request can ever fail because the heap is empty or exhausted.

use core::fmt;

/// A stack-allocated byte buffer that implements [`fmt::Write`].
///
/// Writes past the end are truncated instead of allocating.
pub struct WriteBuffer<const N: usize> {
    bytes: [u8; N],
    length: usize,
}

impl<const N: usize> WriteBuffer<N> {
    /// Create an empty buffer.
    pub const fn new() -> Self {
        Self {
            bytes: [0; N],
            length: 0,
        }
    }

    /// The bytes written so far.
    pub fn as_bytes(&self) -> &[u8] {
        &self.bytes[..self.length]
    }

    /// The number of bytes written so far.
    pub fn len(&self) -> usize {
        self.length
    }

    /// Append raw bytes, truncating at the end of the buffer.
    pub fn push_bytes(&mut self, bytes: &[u8]) {
        let remaining = N - self.length;
        let count = bytes.len().min(remaining);
        self.bytes[self.length..self.length + count].copy_from_slice(&bytes[..count]);
        self.length += count;
    }

    /// Append a single byte if there is room.
    pub fn push_byte(&mut self, byte: u8) {
        if self.length < N {
            self.bytes[self.length] = byte;
            self.length += 1;
        }
    }
}

impl<const N: usize> fmt::Write for WriteBuffer<N> {
    fn write_str(&mut self, text: &str) -> fmt::Result {
        self.push_bytes(text.as_bytes());
        Ok(())
    }
}
