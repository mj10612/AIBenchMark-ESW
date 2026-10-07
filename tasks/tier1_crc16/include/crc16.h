/* AIBENCHMARK_ESW_CANARY_V1_tier1_crc16 */
#ifndef CRC16_H
#define CRC16_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

uint16_t crc16_update(uint16_t current_crc, uint8_t byte);
uint16_t crc16_ccitt(const uint8_t* data, size_t length);

#ifdef __cplusplus
}
#endif

#endif /* CRC16_H */
