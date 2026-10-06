#ifndef COBS_CODEC_H
#define COBS_CODEC_H

#include <stddef.h>
#include <stdint.h>

typedef enum {
    COBS_OK = 0,
    COBS_INVALID_ARGUMENT,
    COBS_NO_SPACE,
    COBS_MALFORMED
} cobs_status_t;

cobs_status_t cobs_encode(const uint8_t *src, size_t src_len,
                          uint8_t *dst, size_t dst_capacity, size_t *written);
cobs_status_t cobs_decode(const uint8_t *src, size_t src_len,
                          uint8_t *dst, size_t dst_capacity, size_t *written);

#endif
