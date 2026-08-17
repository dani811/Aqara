/* ESP32-S3 as a plain Bluetooth LE HCI controller over its native USB-Serial-JTAG
 * port. H4 framing (packet-type byte + HCI packet) in both directions, exactly
 * what Bumble's `serial:/dev/cu.usbmodemXXXX,115200` transport expects (baud is
 * ignored on USB). Console/logs stay on UART0 so the USB stream is pure HCI.
 */
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "freertos/ringbuf.h"
#include "esp_bt.h"
#include "esp_log.h"
#include "nvs_flash.h"
#include "driver/usb_serial_jtag.h"

static const char *TAG = "hci_usb";
static RingbufHandle_t s_tx_ring;          // controller -> host bytes
static SemaphoreHandle_t s_send_avail;     // controller ready for another packet

/* Controller can accept a new packet from the host. */
static void ctrl_send_ready(void)
{
    xSemaphoreGive(s_send_avail);
}

/* Controller emitted a packet (already H4-framed: data[0] is the packet type). */
static int host_recv_pkt(uint8_t *data, uint16_t len)
{
    if (xRingbufferSend(s_tx_ring, data, len, pdMS_TO_TICKS(100)) != pdTRUE) {
        ESP_LOGW(TAG, "tx ring full, dropped %u bytes", len);
    }
    return 0;
}

static esp_vhci_host_callback_t s_vhci_cb = { ctrl_send_ready, host_recv_pkt };

static void usb_tx_task(void *arg)
{
    for (;;) {
        size_t n = 0;
        uint8_t *item = xRingbufferReceive(s_tx_ring, &n, portMAX_DELAY);
        if (!item) continue;
        size_t off = 0;
        while (off < n) {
            int w = usb_serial_jtag_write_bytes(item + off, n - off, pdMS_TO_TICKS(1000));
            if (w <= 0) { ESP_LOGW(TAG, "usb write timeout (host not reading?)"); break; }
            off += w;
        }
        vRingbufferReturnItem(s_tx_ring, item);
    }
}

/* Length of the H4 packet header (after the type byte) and where the payload
 * length lives, per packet type. Returns 0 for unknown types (resync). */
static int h4_header_len(uint8_t type)
{
    switch (type) {
    case 0x01: return 3;  // CMD: opcode(2) len(1)
    case 0x02: return 4;  // ACL: handle(2) len(2)
    case 0x03: return 3;  // SCO: handle(2) len(1)
    case 0x04: return 2;  // EVT: code(1) len(1)
    case 0x05: return 4;  // ISO: handle(2) len(2, 14 bits)
    default:   return 0;
    }
}

static uint32_t h4_payload_len(const uint8_t *pkt)
{
    switch (pkt[0]) {
    case 0x01: return pkt[3];
    case 0x02: return pkt[3] | (pkt[4] << 8);
    case 0x03: return pkt[3];
    case 0x04: return pkt[2];
    case 0x05: return (pkt[3] | (pkt[4] << 8)) & 0x3FFF;
    default:   return 0;
    }
}

static void usb_rx_task(void *arg)
{
    static uint8_t pkt[1024 + 5];
    size_t have = 0;       // bytes accumulated in pkt
    for (;;) {
        // Read at least one byte, blocking.
        int r = usb_serial_jtag_read_bytes(pkt + have, 1, portMAX_DELAY);
        if (r <= 0) continue;
        have += r;
        if (h4_header_len(pkt[0]) == 0) {   // unknown type: resync
            ESP_LOGW(TAG, "bad H4 type 0x%02x, resync", pkt[0]);
            have = 0;
            continue;
        }
        size_t hdr = 1 + h4_header_len(pkt[0]);
        while (have < hdr) {
            r = usb_serial_jtag_read_bytes(pkt + have, hdr - have, portMAX_DELAY);
            if (r > 0) have += r;
        }
        size_t total = hdr + h4_payload_len(pkt);
        if (total > sizeof(pkt)) { ESP_LOGW(TAG, "oversize pkt %u", (unsigned)total); have = 0; continue; }
        while (have < total) {
            r = usb_serial_jtag_read_bytes(pkt + have, total - have, portMAX_DELAY);
            if (r > 0) have += r;
        }
        // Wait until the controller can take it, then hand it over.
        while (!esp_vhci_host_check_send_available()) {
            xSemaphoreTake(s_send_avail, pdMS_TO_TICKS(50));
        }
        esp_vhci_host_send_packet(pkt, total);
        have = 0;
    }
}

void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ESP_ERROR_CHECK(nvs_flash_init());
    }

    s_tx_ring = xRingbufferCreate(8192, RINGBUF_TYPE_NOSPLIT);
    s_send_avail = xSemaphoreCreateBinary();

    usb_serial_jtag_driver_config_t usb_cfg = { .tx_buffer_size = 4096, .rx_buffer_size = 4096 };
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb_cfg));

    esp_bt_controller_config_t bt_cfg = BT_CONTROLLER_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_bt_controller_init(&bt_cfg));
    ESP_ERROR_CHECK(esp_bt_controller_enable(ESP_BT_MODE_BLE));
    ESP_ERROR_CHECK(esp_vhci_host_register_callback(&s_vhci_cb));

    xTaskCreatePinnedToCore(usb_tx_task, "usb_tx", 4096, NULL, 10, NULL, 0);
    xTaskCreatePinnedToCore(usb_rx_task, "usb_rx", 4096, NULL, 10, NULL, 0);
    ESP_LOGI(TAG, "BLE HCI over USB-Serial-JTAG ready (H4)");
}
