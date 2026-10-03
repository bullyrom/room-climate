//! MH-Z19 sampling task.
//!
//! Reads the sensor periodically and publishes every measurement through
//! [`Telemetry`] so the HTTP server can serve it. The Wi-Fi/network tasks keep
//! running between reads.

use embassy_time::{Duration, Timer};
use crate::console::println;

use crate::config;
use crate::mh_z19::MhZ19;
use crate::telemetry::Telemetry;

/// Sample the MH-Z19 forever, publishing each valid measurement.
#[embassy_executor::task]
pub async fn sensor_task(mut sensor: MhZ19<'static>) {
    println!(
        "mhz19 ready: rx=gpio{} tx=gpio{} baud={}",
        config::MHZ19_RX_GPIO,
        config::MHZ19_TX_GPIO,
        config::MHZ19_BAUD_RATE,
    );

    loop {
        let frame = sensor.read(config::MHZ19_READ_ATTEMPTS);
        #[cfg(feature = "mhz19-debug")]
        {
            crate::hex::print_frame("mhz19 tx", &frame.command);
            crate::hex::print_frame("mhz19 rx", frame.received());
            if let Some(error) = frame.error {
                println!("mhz19 uart error: {}", error);
            }
        }
        match frame.measurement() {
            Some(measurement) => {
                println!(
                    "MEASUREMENT co2={}ppm temp={}C",
                    measurement.co2_ppm, measurement.temperature_celsius
                );
                Telemetry::publish(measurement.co2_ppm, measurement.temperature_celsius);
            }
            None => println!("sample incomplete: no valid MH-Z19 frame"),
        }
        Timer::after(Duration::from_millis(config::SAMPLE_INTERVAL_MS as u64)).await;
    }
}
