//! Wi-Fi station connection using credentials from persistent storage.

use esp_hal::peripherals::WIFI;
use crate::console::println;
use esp_radio::wifi::{
    AuthenticationMethodConfig, Config, ControllerConfig, Password, Ssid, WifiController,
    sta::StationConfig,
};

use crate::credentials::Credentials;

/// Keeps the Wi-Fi connection alive for as long as it is held.
pub struct WifiLink<'d> {
    _controller: WifiController<'d>,
}

impl<'d> WifiLink<'d> {
    /// Configure the controller from credentials, then connect and wait.
    pub async fn establish(wifi: WIFI<'d>, credentials: &Credentials) -> Option<Self> {
        let authentication = if credentials.password.is_empty() {
            AuthenticationMethodConfig::Open
        } else {
            match Password::try_from(credentials.password.as_str()) {
                Ok(password) => AuthenticationMethodConfig::Wpa2Personal(password),
                Err(_) => {
                    println!("wifi: stored password rejected");
                    return None;
                }
            }
        };

        let ssid = match Ssid::try_from(credentials.ssid.as_str()) {
            Ok(ssid) => ssid,
            Err(_) => {
                println!("wifi: stored ssid rejected");
                return None;
            }
        };

        let station = StationConfig::default()
            .with_ssid(ssid)
            .with_authentication(authentication);
        let config = ControllerConfig::default().with_initial_config(Config::Station(station));

        let mut controller = match WifiController::new(wifi, config) {
            Ok(controller) => controller,
            Err(error) => {
                println!("wifi: controller init failed: {:?}", error);
                return None;
            }
        };

        match controller.connect_async().await {
            Ok(info) => println!("wifi: connected to ssid={}", info.ssid.as_str()),
            Err(error) => {
                println!("wifi: connect failed: {:?}", error);
                return None;
            }
        }

        Some(Self {
            _controller: controller,
        })
    }
}
