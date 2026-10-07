/* AIBENCHMARK_ESW_CANARY_V1_tier1_crc16 */
#include "crc16.h"

uint16_t crc16_update(uint16_t current_crc, uint8_t byte) {
    (void)current_crc;
    (void)byte;
    return 0;
}

uint16_t crc16_ccitt(const uint8_t* data, size_t length) {
    (void)data;
    (void)length;
    return 0;
}
