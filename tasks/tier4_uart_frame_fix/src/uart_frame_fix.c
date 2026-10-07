/* AIBENCHMARK_ESW_CANARY_V1_tier4_uart_frame_fix */
#include "uart_frame_fix.h"
/* Repair these defects: premature publication, ignored checksum, per-byte
   timeout renewal and missing peripheral reset after every error. */
static int next_byte(const uart_hal_t *hal, uint8_t *byte, uint32_t polls) {
    for (uint32_t i = 0; i < polls; ++i) {
        int rc = hal->read_byte(hal->ctx, byte);
        if (rc < 0) return UART_IO;
        if (rc == 1) return UART_OK;
    }
    return UART_TIMEOUT;
}
int uart_receive(const uart_hal_t *hal, uint8_t *out, size_t cap, size_t *length, uint32_t polls) {
    if (hal == NULL || hal->read_byte == NULL || out == NULL || length == NULL || polls == 0) return UART_ARGUMENT;
    uint8_t byte = 0, count = 0;
    int rc = next_byte(hal, &byte, polls);
    if (rc != UART_OK) return rc;
    if (byte != 0xA5) return UART_FRAME;
    rc = next_byte(hal, &count, polls);
    if (rc != UART_OK) return rc;
    if (count == 0 || count > 32) return UART_FRAME;
    if (count > cap) return UART_SPACE;
    *length = count;
    for (size_t i = 0; i < count; ++i) {
        rc = next_byte(hal, &out[i], polls);
        if (rc != UART_OK) return rc;
    }
    return next_byte(hal, &byte, polls);
}
