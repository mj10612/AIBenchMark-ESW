/* AIBENCHMARK_ESW_CANARY_V1_tier2_cobs_codec */
#include "cobs_codec.h"

cobs_status_t cobs_encode(const uint8_t *src, size_t src_len,
                          uint8_t *dst, size_t dst_capacity, size_t *written) {
    size_t input = 0, output = 0;
    if (written == NULL) return COBS_INVALID_ARGUMENT;
    *written = 0;
    if ((src == NULL && src_len != 0) || (dst == NULL && dst_capacity != 0))
        return COBS_INVALID_ARGUMENT;
    for (;;) {
        size_t block = 0;
        while (block < 254 && block < src_len - input && src[input + block] != 0)
            ++block;
        if (block + 1 > dst_capacity - output) return COBS_NO_SPACE;
        dst[output++] = (uint8_t)(block + 1);
        for (size_t i = 0; i < block; ++i) dst[output++] = src[input++];
        if (block == 254) {
            if (input == src_len) break;
            continue;
        }
        if (input == src_len) break;
        ++input; /* Consume the zero; a terminal zero needs a final empty block. */
    }
    *written = output;
    return COBS_OK;
}

cobs_status_t cobs_decode(const uint8_t *src, size_t src_len,
                          uint8_t *dst, size_t dst_capacity, size_t *written) {
    size_t input = 0, output = 0;
    if (written == NULL) return COBS_INVALID_ARGUMENT;
    *written = 0;
    if ((src == NULL && src_len != 0) || (dst == NULL && dst_capacity != 0))
        return COBS_INVALID_ARGUMENT;
    if (src_len == 0) return COBS_MALFORMED;
    while (input < src_len) {
        uint8_t code = src[input++];
        if (code == 0) return COBS_MALFORMED;
        size_t count = (size_t)code - 1;
        if (count > src_len - input) return COBS_MALFORMED;
        if (count > dst_capacity - output) return COBS_NO_SPACE;
        for (size_t i = 0; i < count; ++i) {
            if (src[input] == 0) return COBS_MALFORMED;
            dst[output++] = src[input++];
        }
        if (code != 255 && input < src_len) {
            if (output == dst_capacity) return COBS_NO_SPACE;
            dst[output++] = 0;
        }
    }
    *written = output;
    return COBS_OK;
}
