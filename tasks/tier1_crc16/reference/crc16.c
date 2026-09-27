#include "crc16.h"

uint16_t crc16_update(uint16_t current_crc, uint8_t byte) {
    uint16_t crc = current_crc ^ (uint16_t)((uint16_t)byte << 8);
    for (int i = 0; i < 8; i++) {
        if ((crc & 0x8000U) != 0U) {
            crc = (uint16_t)((crc << 1) ^ 0x1021U);
        } else {
            crc = (uint16_t)(crc << 1);
        }
    }
    return crc;
}

uint16_t crc16_ccitt(const uint8_t* data, size_t length) {
    if (data == NULL && length > 0) {
        return 0;
    }
    uint16_t crc = 0xFFFFU;
    for (size_t i = 0; i < length; i++) {
        crc = crc16_update(crc, data[i]);
    }
    return crc;
}
