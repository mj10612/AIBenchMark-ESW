/* AIBENCHMARK_ESW_CANARY_V1_tier1_ring_buffer */
#include "ring_buffer.h"

void ring_buffer_init(ring_buffer_t* rb, uint8_t* buffer, size_t capacity) {
    (void)rb;
    (void)buffer;
    (void)capacity;
}

bool ring_buffer_push(ring_buffer_t* rb, uint8_t byte) {
    (void)rb;
    (void)byte;
    return false;
}

bool ring_buffer_pop(ring_buffer_t* rb, uint8_t* byte) {
    (void)rb;
    (void)byte;
    return false;
}

bool ring_buffer_is_empty(const ring_buffer_t* rb) {
    (void)rb;
    return true;
}

bool ring_buffer_is_full(const ring_buffer_t* rb) {
    (void)rb;
    return false;
}

size_t ring_buffer_count(const ring_buffer_t* rb) {
    (void)rb;
    return 0;
}
