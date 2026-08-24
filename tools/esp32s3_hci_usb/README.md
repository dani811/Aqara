# esp32s3_hci_usb — an ESP32‑S3 as a Bluetooth LE HCI controller over USB

Turns a bare ESP32‑S3 into the **external HCI controller** that
`aqara_ble.BumbleTransport` drives. This is the route that exposes every
low‑level primitive the U200 pre‑auth uses (LE Read Remote Features, ATT MTU,
Read‑By‑Type GATT‑caching preamble, connection‑parameter update) — the host's
native stack (bleak/CoreBluetooth) omits them.

**What it is**: Espressif's BLE controller in *controller‑only* mode, bridged
with **H4 framing** over the chip's native **USB‑Serial‑JTAG** port (VID
`303a`, PID `1001`; `/dev/cu.usbmodemNNNN` on macOS, `/dev/ttyACM*` on Linux).
Logs stay on UART0, so the USB stream carries only HCI. No Wi‑Fi, no NVS
data, no bonding. ~150 lines: [`main/main.c`](main/main.c).

Verified 2026‑08‑17: `HCI Reset` + `Read Local Version` → Bluetooth Core 5.0,
company id 741 (Espressif); full U200 flow (connect, discovery, MTU 247,
Read‑By‑Type `0x2A01`/`0x2B2A`, connection update, CCCDs, cloud) via Bumble.

## Requirements

- ESP‑IDF **v5.3.x** (built with 5.3.3). Any ESP32‑S3 module/devkit with its
  native USB wired to a USB port (the "USB" connector, not the "UART" one).
- Python venv of this repo with the `bumble` extra: `pip install -e '.[bumble]'`.

## Build, erase, flash

```bash
cd tools/esp32s3_hci_usb
cp idf_env.example.sh idf_env.sh   # edit IDF_PATH / IDF_TOOLS_PATH
source ./idf_env.sh
idf.py set-target esp32s3
idf.py build

PORT=/dev/cu.usbmodemNNNN            # ls /dev/cu.usbmodem*  (macOS) | /dev/ttyACM0 (Linux)
python -m esptool --chip esp32s3 -p "$PORT" erase_flash          # "format": wipes whatever was there
python -m esptool --chip esp32s3 -p "$PORT" -b 460800 --before default_reset --after hard_reset \
  write_flash --flash_mode dio --flash_size 4MB --flash_freq 80m \
  0x0 build/bootloader/bootloader.bin 0x8000 build/partition_table/partition-table.bin \
  0x10000 build/esp32s3_hci_usb.bin
```

The board re‑enumerates on the same port after the reset. `--flash_size 4MB`
is fine on bigger chips (the app is ~400 KB).

## Verify the controller answers

```bash
.venv/bin/python tools/hci_smoke.py serial:$PORT,115200
# local version: hci_version BLUETOOTH_CORE_5_0 ... company_identifier 741
```

## Use it

Put the port in your git‑ignored `.env`:

```
AQARA_ESP32_PORT=serial:/dev/cu.usbmodemNNNN,115200
```

(the baud rate is ignored on USB but Bumble's `serial:` spec wants it), then

```bash
.venv/bin/python examples/lock_cli.py --transport bumble scan
.venv/bin/python examples/lock_cli.py --transport bumble lock
```

## Gotchas (all observed live)

- The U200 **does not support bonding**: any SMP request makes it drop the
  link. `BumbleTransport` never pairs.
- The U200 **rejects an immediate reconnect** ("DISCONNECTION COMPLETE: unknown
  handle" during service discovery). Wait ~5 s between attempts.
- Bumble's `connection.disconnect()` can hang if the link already dropped; the
  transport bounds it with a 5 s timeout.
- The USB‑Serial‑JTAG port also serves esptool: opening it with DTR/RTS toggling
  in the esptool pattern resets the chip. pyserial's default open (both
  asserted) does not.
- If the host stops reading, the firmware drops controller→host bytes after a
  1 s write timeout instead of blocking the controller (see `usb_tx_task`).

## Layout

```
CMakeLists.txt        # project
sdkconfig.defaults    # BT controller-only, console on UART0, 4MB single-app
main/CMakeLists.txt
main/main.c           # VHCI <-> USB-Serial-JTAG H4 bridge
idf_env.example.sh    # env recipe (copy to idf_env.sh, git-ignored)
```
No binaries, no generated `sdkconfig`, no ports/MACs are committed.
