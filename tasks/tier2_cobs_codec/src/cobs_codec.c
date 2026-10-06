#include "cobs_codec.h"

cobs_status_t cobs_encode(const uint8_t *src, size_t src_len,
                          uint8_t *dst, size_t dst_capacity, size_t *written) {
    (void)src; (void)src_len; (void)dst; (void)dst_capacity;
    if (written != NULL) *written = 0;
    return COBS_INVALID_ARGUMENT;
}

cobs_status_t cobs_decode(const uint8_t *src, size_t src_len,
                          uint8_t *dst, size_t dst_capacity, size_t *written) {
    (void)src; (void)src_len; (void)dst; (void)dst_capacity;
    if (written != NULL) *written = 0;
    return COBS_INVALID_ARGUMENT;
}
