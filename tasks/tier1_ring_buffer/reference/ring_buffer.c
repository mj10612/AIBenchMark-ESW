#include "ring_buffer.h"

void ring_buffer_init(ring_buffer_t* rb, uint8_t* buffer, size_t capacity) {
    if (rb == NULL) {
        return;
    }
    rb->buffer = buffer;
    rb->capacity = capacity;
    rb->head = 0;
    rb->tail = 0;
}

bool ring_buffer_push(ring_buffer_t* rb, uint8_t byte) {
    if (rb == NULL || rb->buffer == NULL || rb->capacity == 0) {
        return false;
    }
    if ((rb->head - rb->tail) >= rb->capacity) {
        return false; /* Full */
    }
    rb->buffer[rb->head % rb->capacity] = byte;
    rb->head++;
    return true;
}

bool ring_buffer_pop(ring_buffer_t* rb, uint8_t* byte) {
    if (rb == NULL || rb->buffer == NULL || rb->capacity == 0 || byte == NULL) {
        return false;
    }
    if (rb->head == rb->tail) {
        return false; /* Empty */
    }
    *byte = rb->buffer[rb->tail % rb->capacity];
    rb->tail++;
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
    return ((rb->head - rb->tail) >= rb->capacity);
}

size_t ring_buffer_count(const ring_buffer_t* rb) {
    if (rb == NULL || rb->capacity == 0) {
        return 0;
    }
    return (rb->head - rb->tail);
}
