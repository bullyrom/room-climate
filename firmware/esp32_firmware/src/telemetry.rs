//! Latest sensor reading shared between the MH-Z19 task and the HTTP server.
//!
//! The values are plain atomics so the sensor task can publish a sample and
//! the HTTP task can read the latest one without any locking.

use core::sync::atomic::{AtomicBool, AtomicI16, AtomicU16, Ordering};

/// Shared, lock-free snapshot of the most recent measurement.
pub struct Telemetry;

static CO2_PPM: AtomicU16 = AtomicU16::new(0);
static TEMPERATURE_CELSIUS: AtomicI16 = AtomicI16::new(0);
static HAS_READING: AtomicBool = AtomicBool::new(false);

impl Telemetry {
    /// Store a fresh measurement.
    pub fn publish(co2_ppm: u16, temperature_celsius: i16) {
        CO2_PPM.store(co2_ppm, Ordering::Relaxed);
        TEMPERATURE_CELSIUS.store(temperature_celsius, Ordering::Relaxed);
        HAS_READING.store(true, Ordering::Release);
    }

    /// Return the latest measurement, or `None` before the first one.
    pub fn latest() -> Option<(u16, i16)> {
        if HAS_READING.load(Ordering::Acquire) {
            Some((
                CO2_PPM.load(Ordering::Relaxed),
                TEMPERATURE_CELSIUS.load(Ordering::Relaxed),
            ))
        } else {
            None
        }
    }
}
