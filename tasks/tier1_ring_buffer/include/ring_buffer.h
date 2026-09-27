#ifndef RING_BUFFER_H
#define RING_BUFFER_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t* buffer;
    size_t capacity;
    volatile size_t head;
    volatile size_t tail;
} ring_buffer_t;

void ring_buffer_init(ring_buffer_t* rb, uint8_t* buffer, size_t capacity);
bool ring_buffer_push(ring_buffer_t* rb, uint8_t byte);
bool ring_buffer_pop(ring_buffer_t* rb, uint8_t* byte);
bool ring_buffer_is_empty(const ring_buffer_t* rb);
bool ring_buffer_is_full(const ring_buffer_t* rb);
size_t ring_buffer_count(const ring_buffer_t* rb);

#ifdef __cplusplus
}
#endif

#endif /* RING_BUFFER_H */
