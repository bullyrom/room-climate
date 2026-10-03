//! room-climate ESP32 firmware.
//!
//! Connects to Wi-Fi (credentials provisioned over the USB serial console and
//! stored in flash), samples the MH-Z19C on UART2 and serves the latest CO2 and
//! temperature as JSON over HTTP on port 80. Wi-Fi, sampling and the HTTP
//! server run as separate async tasks. The password is never logged.

#![no_std]
#![no_main]

extern crate alloc;

use embassy_executor::Spawner;
use embassy_net::{Config as NetConfig, StackResources};
use embassy_time::{Duration, Timer};
use esp_backtrace as _;
use esp_hal::clock::CpuClock;
use esp_hal::rng::Rng;
use esp_hal::timer::timg::TimerGroup;
use esp_hal::uart::{Config as UartConfig, Uart};
use crate::console::println;
use static_cell::StaticCell;

mod config;
mod console;
mod credentials;
#[cfg(feature = "mhz19-debug")]
mod hex;
mod http_server;
mod mh_z19;
mod provisioning;
mod sensor;
mod telemetry;
mod wifi_link;
mod write_buffer;

esp_bootloader_esp_idf::esp_app_desc!();

/// Internal-RAM heap for the Wi-Fi stack, the network buffers and the tasks.
const HEAP_SIZE_BYTES: usize = 128 * 1024;
/// Baud rate of the USB serial console used for provisioning.
const CONSOLE_BAUD_RATE: u32 = 115_200;
/// TCP sockets the embassy-net stack may use.
const NET_SOCKET_COUNT: usize = 3;

/// Static storage for the embassy-net socket pool.
static NET_RESOURCES: StaticCell<StackResources<NET_SOCKET_COUNT>> = StaticCell::new();

#[esp_hal::main]
async fn main(spawner: Spawner) -> ! {
    let hardware_config = esp_hal::Config::default().with_cpu_clock(CpuClock::max());
    let peripherals = esp_hal::init(hardware_config);

    // Initialise the heap before anything can allocate: `heap_allocator!` adds
    // its region at runtime, and Wi-Fi/HTTP need it. The console itself no
    // longer allocates, so the banner prints even if this were late.
    esp_alloc::heap_allocator!(size: HEAP_SIZE_BYTES);

    println!("room-climate firmware (WiFi+HTTP) starting");

    // Credentials live in a dedicated flash partition; provision over serial
    // only when they are missing.
    // Auto-park the second core while writing flash (the default strategy
    // refuses to write when another core is running).
    let mut flash = esp_bootloader_esp_idf::partitions::FlashStorage::new(peripherals.FLASH)
        .multicore_auto_park();
    let store = credentials::CredentialStore::new(&mut flash);
    let stored = store.as_ref().and_then(|store| store.load(&mut flash));
    let credentials = match stored {
        Some(credentials) => {
            println!(
                "wifi: stored credentials found for ssid={}",
                credentials.ssid
            );
            credentials
        }
        None => {
            // Prove the flash write path works before asking for credentials.
            match store.as_ref() {
                Some(store) => match store.selftest(&mut flash) {
                    Ok(()) => println!("flash selftest: ok"),
                    Err(reason) => println!("flash selftest failed: {}", reason),
                },
                None => println!("flash selftest skipped: no nvs partition"),
            }

            // UART0 is the USB serial console: TX = GPIO1, RX = GPIO3. The RX
            // pin must be assigned explicitly, otherwise the UART never
            // receives anything (esp-println prints without the RX signal).
            let serial = Uart::new(
                peripherals.UART0,
                UartConfig::default().with_baudrate(CONSOLE_BAUD_RATE),
            )
            .unwrap()
            .with_tx(peripherals.GPIO1)
            .with_rx(peripherals.GPIO3);
            println!(
                "wifi: console uart0 rx=gpio3 tx=gpio1 baud={}",
                CONSOLE_BAUD_RATE,
            );
            let mut provisioner = provisioning::SerialProvisioner::new(serial);
            let credentials = provisioner.collect();
            println!("wifi: saving credentials");
            match store {
                Some(store) => match store.save(&mut flash, &credentials) {
                    Ok(()) => println!(
                        "wifi: credentials saved for ssid={}",
                        credentials.ssid
                    ),
                    Err(reason) => {
                        println!("wifi: could not save credentials: {}", reason)
                    }
                },
                None => println!("wifi: no nvs partition; credentials not saved"),
            }
            credentials
        }
    };

    // Start the RTOS scheduler the radio driver needs, then connect.
    let timg0 = TimerGroup::new(peripherals.TIMG0);
    esp_rtos::start(timg0.timer0, peripherals.FROM_CPU_INTR0);

    // Wi-Fi network device (embassy-net driver) and the station connection.
    let wifi_interface = esp_radio::wifi::Interface::station();
    let _wifi = wifi_link::WifiLink::establish(peripherals.WIFI, &credentials).await;
    if _wifi.is_none() {
        println!("wifi: continuing without a connection");
    }

    // IP stack. DHCP is fine because the router hands out a fixed reservation.
    let rng = Rng::new();
    let seed = ((rng.random() as u64) << 32) | (rng.random() as u64);
    let resources = NET_RESOURCES.init(StackResources::new());
    let (stack, runner) = embassy_net::new(
        wifi_interface,
        NetConfig::dhcpv4(Default::default()),
        resources,
        seed,
    );
    spawner.spawn(http_server::network_runner_task(runner).unwrap());
    spawner.spawn(http_server::http_server_task(stack).unwrap());

    // MH-Z19C on UART2, 9600 baud: ESP32 RX = GPIO16, ESP32 TX = GPIO17.
    let sensor_uart = Uart::new(
        peripherals.UART2,
        UartConfig::default().with_baudrate(config::MHZ19_BAUD_RATE),
    )
    .unwrap()
    .with_tx(peripherals.GPIO17)
    .with_rx(peripherals.GPIO16);
    spawner.spawn(sensor::sensor_task(mh_z19::MhZ19::new(sensor_uart)).unwrap());

    // Report the address once DHCP has a lease.
    stack.wait_config_up().await;
    match stack.config_v4() {
        Some(config) => println!("http: serving on http://{}/", config.address),
        None => println!("http: no IPv4 address"),
    }

    loop {
        Timer::after(Duration::from_secs(3600)).await;
    }
}
