# Contract — firmware `tools/esp32s3_hci_usb`

- **Rol**: controlador Bluetooth LE HCI (Bluetooth Core 5.0, Espressif) expuesto por el USB‑Serial‑JTAG nativo del ESP32‑S3 (VID 303a / PID 1001; en macOS `/dev/cu.usbmodemNNNN`).
- **Framing**: H4 en ambos sentidos (`0x01` cmd, `0x02` ACL, `0x04` evt, `0x05` ISO). Sin flow control por hardware; el firmware respeta `esp_vhci_host_check_send_available()` y encola hacia el host en un ring buffer (8 KiB) — descarta con aviso si el host no lee.
- **Consola**: UART0 (nunca por USB). Sin NVS de usuario, sin Wi‑Fi, sin bonding persistente.
- **Uso**: `bumble` transporte `serial:<puerto>,115200` (baud ignorado). Verificación mínima: `HCI Reset` + `Read Local Version` responden (`hci_version=5.0`, `company_identifier=741`).
- **Entregables en el repo**: `CMakeLists.txt`, `sdkconfig.defaults`, `main/CMakeLists.txt`, `main/main.c`, `README.md` (requisitos, `idf.py set-target esp32s3 && idf.py build`, `erase_flash` + `flash`, verificación), `idf_env.example.sh`. **Sin** `build/`, `.bin`, `sdkconfig` generado ni puertos/MACs reales.
