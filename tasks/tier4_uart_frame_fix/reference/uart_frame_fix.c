/* AIBENCHMARK_ESW_CANARY_V1_tier4_uart_frame_fix */
#include "uart_frame_fix.h"

int uart_receive(const uart_hal_t *hal, uint8_t *output, size_t capacity, size_t *length, uint32_t max_polls) {
    if (hal == NULL || hal->read_byte == NULL || hal->reset == NULL || output == NULL || length == NULL || max_polls == 0) return UART_ARGUMENT;
    uint8_t buffer[32];
    size_t count = 0;
    uint8_t expected = 0, checksum = 0, state = 0;
    int error = UART_TIMEOUT;
    for (uint32_t poll = 0; poll < max_polls; ++poll) {
        uint8_t byte = 0;
        int rc = hal->read_byte(hal->ctx, &byte);
        if (rc < 0) { error = UART_IO; break; }
        if (rc == 0) continue;
        if (state == 0) {
            if (byte == 0xA5) state = 1;
        } else if (state == 1) {
            if (byte == 0 || byte > 32) { error = UART_FRAME; break; }
            if (byte > capacity) { error = UART_SPACE; break; }
            expected = byte;
            checksum = byte;
            state = 2;
        } else if (state == 2) {
            buffer[count++] = byte;
            checksum ^= byte;
            if (count == expected) state = 3;
        } else {
            if (byte != checksum) { error = UART_FRAME; break; }
            for (size_t i = 0; i < count; ++i) output[i] = buffer[i];
            *length = count;
            return UART_OK;
        }
    }
    hal->reset(hal->ctx);
    return error;
}
