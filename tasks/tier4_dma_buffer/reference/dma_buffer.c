/* AIBENCHMARK_ESW_CANARY_V1_tier4_dma_buffer */
#include "dma_buffer.h"
#include <limits.h>

#ifdef __TINYC__
/* TCC 0.9.27 accepts -std=c11 but lacks _Static_assert syntax. */
typedef char dma_octet_check[CHAR_BIT == 8 ? 1 : -1];
#else
_Static_assert(CHAR_BIT == 8, "DMA bytes must be octets");
#endif

bool dma_buffer_init(dma_buffer_t *b, uint8_t *storage, size_t length, const dma_hal_t *hal) {
    if (b == NULL) return false;
    b->initialized = false;
    if (storage == NULL || length == 0 || length % 8U != 0 ||
        (uintptr_t)storage % 4U != 0 || hal == NULL || hal->enter == NULL ||
        hal->leave == NULL || hal->invalidate == NULL || hal->clean == NULL) return false;
    b->storage = storage;
    b->half_size = length / 2U;
    b->hal = *hal;
    b->owner[0] = DMA_OWNED;
    b->owner[1] = DMA_OWNED;
    b->overruns = 0;
    b->initialized = true;
    return true;
}

bool dma_buffer_complete(dma_buffer_t *b, uint8_t half) {
    if (b == NULL || !b->initialized || half >= 2U) return false;
    b->hal.enter(b->hal.ctx);
    bool ok = b->owner[half] == DMA_OWNED;
    if (ok) {
        b->hal.invalidate(b->hal.ctx, b->storage + half * b->half_size, b->half_size);
        b->owner[half] = DMA_READY;
    } else {
        b->overruns++;
    }
    b->hal.leave(b->hal.ctx);
    return ok;
}

bool dma_buffer_acquire(dma_buffer_t *b, uint8_t half, const uint8_t **data, size_t *length) {
    if (b == NULL || !b->initialized || half >= 2U || data == NULL || length == NULL) return false;
    b->hal.enter(b->hal.ctx);
    bool ok = b->owner[half] == DMA_READY;
    if (ok) {
        b->owner[half] = DMA_READING;
        *data = b->storage + half * b->half_size;
        *length = b->half_size;
    }
    b->hal.leave(b->hal.ctx);
    return ok;
}

bool dma_buffer_release(dma_buffer_t *b, uint8_t half) {
    if (b == NULL || !b->initialized || half >= 2U) return false;
    b->hal.enter(b->hal.ctx);
    bool ok = b->owner[half] == DMA_READING;
    if (ok) {
        b->hal.clean(b->hal.ctx, b->storage + half * b->half_size, b->half_size);
        b->owner[half] = DMA_OWNED;
    }
    b->hal.leave(b->hal.ctx);
    return ok;
}
