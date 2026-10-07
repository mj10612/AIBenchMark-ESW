/* AIBENCHMARK_ESW_CANARY_V1_tier4_dma_buffer */
#ifndef DMA_BUFFER_H
#define DMA_BUFFER_H
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
typedef void (*dma_guard_fn)(void *ctx);
typedef void (*dma_cache_fn)(void *ctx, uint8_t *data, size_t length);
typedef struct { void *ctx; dma_guard_fn enter, leave; dma_cache_fn invalidate, clean; } dma_hal_t;
enum { DMA_OWNED=0, DMA_READY=1, DMA_READING=2 };
typedef struct { uint8_t *storage; size_t half_size; dma_hal_t hal; volatile uint8_t owner[2]; volatile uint32_t overruns; bool initialized; } dma_buffer_t;
bool dma_buffer_init(dma_buffer_t *, uint8_t *, size_t, const dma_hal_t *);
bool dma_buffer_complete(dma_buffer_t *, uint8_t half);
bool dma_buffer_acquire(dma_buffer_t *, uint8_t half, const uint8_t **data, size_t *length);
bool dma_buffer_release(dma_buffer_t *, uint8_t half);
#endif
