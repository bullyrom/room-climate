//! Persistent Wi-Fi credentials stored in the flash `nvs` partition.
//!
//! The partition table is read to locate the `nvs` data partition; a single
//! record with a magic header and a checksum is written at the start of its
//! first sector. The record is written with NOR-flash semantics (erase the
//! sector, then write word-aligned bytes) so no large temporary buffer is
//! needed on the stack. Only the SSID is ever logged - the password is treated
//! as a secret.

use alloc::format;
use alloc::string::String;
use alloc::vec;

use esp_bootloader_esp_idf::partitions::{
    DataPartitionSubType, FlashStorage, PartitionType, read_partition_table,
    PARTITION_TABLE_MAX_LEN,
};
use crate::console::println;

/// Magic header identifying a credential record.
const RECORD_MAGIC: [u8; 4] = *b"RCW1";
/// Maximum SSID length in bytes.
pub const SSID_MAX_BYTES: usize = 32;
/// Maximum password length in bytes.
pub const PASSWORD_MAX_BYTES: usize = 64;
/// Offset of the stored SSID length byte.
const SSID_LEN_OFFSET: usize = RECORD_MAGIC.len();
/// Offset of the stored password length byte.
const PASSWORD_LEN_OFFSET: usize = SSID_LEN_OFFSET + 1;
/// Offset of the stored SSID bytes.
const SSID_OFFSET: usize = PASSWORD_LEN_OFFSET + 1;
/// Offset of the stored password bytes.
const PASSWORD_OFFSET: usize = SSID_OFFSET + SSID_MAX_BYTES;
/// Offset of the record checksum byte.
const CHECKSUM_OFFSET: usize = PASSWORD_OFFSET + PASSWORD_MAX_BYTES;
/// Total size of the meaningful part of a credential record in bytes.
const RECORD_LENGTH: usize = CHECKSUM_OFFSET + 1;
/// Flash word size; offsets and lengths must be a multiple of this.
const WORD_SIZE: usize = 4;
/// On-flash record size, padded up to a whole number of flash words.
const RECORD_LENGTH_PADDED: usize = RECORD_LENGTH.div_ceil(WORD_SIZE) * WORD_SIZE;
/// Size of one flash sector; the record lives in the first sector of `nvs`.
const SECTOR_SIZE: u32 = 4096;

/// A word-aligned record buffer, so `read_nor`/`write_nor` never allocate the
/// 4096-byte temporary sector buffer on the stack.
#[repr(C, align(4))]
struct Record {
    bytes: [u8; RECORD_LENGTH_PADDED],
}

impl Record {
    /// Return a zeroed record buffer.
    fn zeroed() -> Self {
        Self {
            bytes: [0u8; RECORD_LENGTH_PADDED],
        }
    }
}

/// A word-aligned flash word used by the write self-test.
#[repr(C, align(4))]
struct Word([u8; WORD_SIZE]);

/// Known pattern the self-test writes and reads back.
const SELFTEST_PATTERN: [u8; WORD_SIZE] = [0xA5, 0x5A, 0xC3, 0x3C];

/// Wi-Fi credentials read from or written to persistent storage.
///
/// Deliberately does not derive `Debug`: the password must never be formatted.
#[derive(PartialEq, Eq)]
pub struct Credentials {
    /// Network name (not secret).
    pub ssid: String,
    /// Network password (secret, never logged).
    pub password: String,
}

impl Credentials {
    /// Validate the lengths and build credentials.
    pub fn new(ssid: String, password: String) -> Option<Self> {
        if ssid.is_empty() || ssid.len() > SSID_MAX_BYTES || password.len() > PASSWORD_MAX_BYTES {
            return None;
        }
        Some(Self { ssid, password })
    }

    /// Serialize into the fixed-size on-flash record layout.
    fn encode_into(&self, record: &mut Record) {
        let bytes = &mut record.bytes;
        bytes[..RECORD_MAGIC.len()].copy_from_slice(&RECORD_MAGIC);
        bytes[SSID_LEN_OFFSET] = self.ssid.len() as u8;
        bytes[PASSWORD_LEN_OFFSET] = self.password.len() as u8;
        bytes[SSID_OFFSET..SSID_OFFSET + self.ssid.len()].copy_from_slice(self.ssid.as_bytes());
        bytes[PASSWORD_OFFSET..PASSWORD_OFFSET + self.password.len()]
            .copy_from_slice(self.password.as_bytes());
        bytes[CHECKSUM_OFFSET] = checksum(&bytes[..CHECKSUM_OFFSET]);
    }

    /// Parse a record, returning `None` when it is absent or corrupt.
    fn decode(bytes: &[u8]) -> Option<Self> {
        if bytes.len() < RECORD_LENGTH {
            return None;
        }
        if bytes[..RECORD_MAGIC.len()] != RECORD_MAGIC {
            return None;
        }
        if bytes[CHECKSUM_OFFSET] != checksum(&bytes[..CHECKSUM_OFFSET]) {
            return None;
        }
        let ssid_len = bytes[SSID_LEN_OFFSET] as usize;
        let password_len = bytes[PASSWORD_LEN_OFFSET] as usize;
        if ssid_len == 0 || ssid_len > SSID_MAX_BYTES || password_len > PASSWORD_MAX_BYTES {
            return None;
        }
        let ssid = String::from_utf8(bytes[SSID_OFFSET..SSID_OFFSET + ssid_len].to_vec()).ok()?;
        let password =
            String::from_utf8(bytes[PASSWORD_OFFSET..PASSWORD_OFFSET + password_len].to_vec())
                .ok()?;
        Some(Self { ssid, password })
    }
}

/// Locates the credential record inside the flash `nvs` partition.
pub struct CredentialStore {
    offset: u32,
    capacity: u32,
}

impl CredentialStore {
    /// Read the partition table and find a writable `nvs` data partition.
    pub fn new(flash: &mut FlashStorage<'_>) -> Option<Self> {
        let mut table_buffer = vec![0u8; PARTITION_TABLE_MAX_LEN];
        let table = read_partition_table(flash, &mut table_buffer).ok()?;
        let partition = table
            .find_partition(PartitionType::Data(DataPartitionSubType::Nvs))
            .ok()??;
        if (partition.len() as usize) < RECORD_LENGTH {
            return None;
        }
        Some(Self {
            offset: partition.offset(),
            capacity: partition.len(),
        })
    }

    /// Load credentials, or `None` when none have been stored yet.
    pub fn load(&self, flash: &mut FlashStorage<'_>) -> Option<Credentials> {
        let mut record = Record::zeroed();
        flash.read_nor(self.offset, &mut record.bytes).ok()?;
        Credentials::decode(&record.bytes)
    }

    /// Prove the flash can be erased, written and read back.
    ///
    /// Uses the last sector of the `nvs` partition (separate from the record
    /// in the first sector) so a broken write path is visible before the user
    /// types any credentials.
    pub fn selftest(&self, flash: &mut FlashStorage<'_>) -> Result<(), String> {
        if self.capacity < 2 * SECTOR_SIZE {
            return Err(String::from("nvs partition is too small for a self-test"));
        }
        let offset = self.offset + self.capacity - SECTOR_SIZE;
        println!("flash selftest: erase/write/read at {:#x}", offset);
        flash
            .erase(offset, offset + SECTOR_SIZE)
            .map_err(|error| format!("erase failed: {:?}", error))?;
        let pattern = Word(SELFTEST_PATTERN);
        flash
            .write_nor(offset, &pattern.0)
            .map_err(|error| format!("write failed: {:?}", error))?;
        let mut readback = Word([0u8; WORD_SIZE]);
        flash
            .read_nor(offset, &mut readback.0)
            .map_err(|error| format!("readback failed: {:?}", error))?;
        if readback.0 == SELFTEST_PATTERN {
            Ok(())
        } else {
            Err(format!("readback mismatch: {:02x?}", readback.0))
        }
    }

    /// Persist credentials and verify them by reading the record back.
    ///
    /// Every step prints its own line so the serial console shows exactly where
    /// saving stops when it fails.
    pub fn save(
        &self,
        flash: &mut FlashStorage<'_>,
        credentials: &Credentials,
    ) -> Result<(), String> {
        let mut record = Record::zeroed();
        credentials.encode_into(&mut record);

        println!("wifi: nvs erase sector at {:#x}", self.offset);
        flash
            .erase(self.offset, self.offset + SECTOR_SIZE)
            .map_err(|error| format!("erase failed: {:?}", error))?;
        println!("wifi: nvs erase ok");

        println!("wifi: nvs write {} bytes", record.bytes.len());
        flash
            .write_nor(self.offset, &record.bytes)
            .map_err(|error| format!("write failed: {:?}", error))?;
        println!("wifi: nvs write ok");

        let mut readback = Record::zeroed();
        flash
            .read_nor(self.offset, &mut readback.bytes)
            .map_err(|error| format!("readback failed: {:?}", error))?;
        println!("wifi: nvs readback ok");

        match Credentials::decode(&readback.bytes) {
            Some(stored) if stored == *credentials => Ok(()),
            Some(_) => Err(String::from("readback mismatch")),
            None => Err(String::from("readback decode failed")),
        }
    }
}

/// Wrapping two's-complement checksum over the given bytes.
fn checksum(bytes: &[u8]) -> u8 {
    let sum = bytes.iter().fold(0u8, |accumulator, byte| {
        accumulator.wrapping_add(*byte)
    });
    0u8.wrapping_sub(sum)
}
