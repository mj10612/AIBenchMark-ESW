/* AIBENCHMARK_ESW_CANARY_V1_tier1_ring_buffer */
#include "ring_buffer.h"

void ring_buffer_init(ring_buffer_t* rb, uint8_t* buffer, size_t capacity) {
    if (rb == NULL) {
        return;
    }
    rb->buffer = buffer;
    rb->capacity = (buffer != NULL && capacity <= SIZE_MAX / 2U) ? capacity : 0U;
    rb->head = 0;
    rb->tail = 0;
}

bool ring_buffer_push(ring_buffer_t* rb, uint8_t byte) {
    if (rb == NULL || rb->buffer == NULL || rb->capacity == 0) {
        return false;
    }
    size_t head = rb->head;
    size_t tail = rb->tail;
    size_t count = (head >= tail) ? head - tail : (2U * rb->capacity) - (tail - head);
    if (count >= rb->capacity) {
        return false; /* Full */
    }
    rb->buffer[(head >= rb->capacity) ? head - rb->capacity : head] = byte;
    rb->head = (head == (2U * rb->capacity) - 1U) ? 0U : head + 1U;
    return true;
}

bool ring_buffer_pop(ring_buffer_t* rb, uint8_t* byte) {
    if (rb == NULL || rb->buffer == NULL || rb->capacity == 0 || byte == NULL) {
        return false;
    }
    size_t head = rb->head;
    size_t tail = rb->tail;
    if (head == tail) {
        return false; /* Empty */
    }
    *byte = rb->buffer[(tail >= rb->capacity) ? tail - rb->capacity : tail];
    rb->tail = (tail == (2U * rb->capacity) - 1U) ? 0U : tail + 1U;
    return true;
}

bool ring_buffer_is_empty(const ring_buffer_t* rb) {
    if (rb == NULL || rb->capacity == 0) {
        return true;
    }
    return (rb->head == rb->tail);
}

bool ring_buffer_is_full(const ring_buffer_t* rb) {
    if (rb == NULL || rb->capacity == 0) {
        return false;
    }
    return (ring_buffer_count(rb) >= rb->capacity);
}

size_t ring_buffer_count(const ring_buffer_t* rb) {
    if (rb == NULL || rb->capacity == 0) {
        return 0;
    }
    size_t head = rb->head;
    size_t tail = rb->tail;
    return (head >= tail) ? head - tail : (2U * rb->capacity) - (tail - head);
}
