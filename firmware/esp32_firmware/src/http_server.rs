//! Minimal HTTP server exposing the latest sensor reading as JSON.
//!
//! `GET /` (any path) returns `{"co2":<ppm>,"temp":<C>}`. The server is a
//! separate embassy task so Wi-Fi and the MH-Z19 sampling keep running. The
//! response is built in fixed stack buffers, so serving a request never
//! allocates.

use core::fmt::Write as _;

use embassy_net::{Runner, Stack, tcp::TcpSocket};
use embassy_time::{Duration, Timer};

use crate::console::println;
use crate::telemetry::Telemetry;
use crate::write_buffer::WriteBuffer;

/// TCP port the HTTP server listens on.
const HTTP_PORT: u16 = 80;
/// How long a single connection may stay open.
const SOCKET_TIMEOUT_SECONDS: u64 = 10;
/// Per-connection socket buffers.
const SOCKET_BUFFER_LENGTH: usize = 1024;
/// Size of the buffer that captures the request head.
const REQUEST_BUFFER_LENGTH: usize = 512;
/// Capacity of the JSON body buffer.
const BODY_CAPACITY: usize = 64;
/// Capacity of the full response buffer.
const RESPONSE_CAPACITY: usize = 256;
/// Delay after closing so the stack can flush the FIN before the socket drops.
const CLOSE_FLUSH_MILLIS: u64 = 50;
/// Back-off before retrying a failed `accept`.
const ACCEPT_RETRY_MILLIS: u64 = 100;

/// Drive the embassy-net stack forever.
#[embassy_executor::task]
pub async fn network_runner_task(mut runner: Runner<'static, esp_radio::wifi::Interface>) {
    runner.run().await
}

/// Accept HTTP connections and answer with the current reading.
#[embassy_executor::task]
pub async fn http_server_task(stack: Stack<'static>) {
    println!("http: listening on port {}", HTTP_PORT);
    loop {
        let mut rx_buffer = [0u8; SOCKET_BUFFER_LENGTH];
        let mut tx_buffer = [0u8; SOCKET_BUFFER_LENGTH];
        let mut socket = TcpSocket::new(stack, &mut rx_buffer, &mut tx_buffer);
        socket.set_timeout(Some(Duration::from_secs(SOCKET_TIMEOUT_SECONDS)));

        if socket.accept(HTTP_PORT).await.is_err() {
            // No address yet or a transient failure; back off briefly instead
            // of spinning hot.
            Timer::after(Duration::from_millis(ACCEPT_RETRY_MILLIS)).await;
            continue;
        }

        let mut request = [0u8; REQUEST_BUFFER_LENGTH];
        let _ = socket.read(&mut request).await;

        let mut response = WriteBuffer::<RESPONSE_CAPACITY>::new();
        build_response(&mut response);
        write_response(&mut socket, response.as_bytes()).await;

        socket.close();
        Timer::after(Duration::from_millis(CLOSE_FLUSH_MILLIS)).await;
    }
}

/// Write the whole response, tolerating a peer that disconnects early.
async fn write_response(socket: &mut TcpSocket<'_>, mut bytes: &[u8]) {
    while !bytes.is_empty() {
        match socket.write(bytes).await {
            Ok(0) => break,
            Ok(written) => bytes = &bytes[written..],
            Err(_) => break,
        }
    }
    let _ = socket.flush().await;
}

/// Render the latest reading as a complete HTTP response, without allocating.
fn build_response(response: &mut WriteBuffer<RESPONSE_CAPACITY>) {
    let mut body = WriteBuffer::<BODY_CAPACITY>::new();
    match Telemetry::latest() {
        Some((co2_ppm, temperature_celsius)) => {
            let _ = write!(
                body,
                r#"{{"co2":{},"temp":{}}}"#,
                co2_ppm, temperature_celsius
            );
        }
        None => {
            let _ = body.write_str(r#"{"co2":null,"temp":null}"#);
        }
    }
    let _ = write!(
        response,
        "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n",
        body.len(),
    );
    response.push_bytes(body.as_bytes());
}
