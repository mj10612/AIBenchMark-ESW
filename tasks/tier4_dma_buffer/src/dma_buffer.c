/* AIBENCHMARK_ESW_CANARY_V1_tier4_dma_buffer */
#include "dma_buffer.h"
/* BUGS: ownership is never transferred; initialization accepts invalid descriptors. */
bool dma_buffer_init(dma_buffer_t *b,uint8_t *p,size_t n,const dma_hal_t *h){(void)b;(void)p;(void)n;(void)h;return true;}
bool dma_buffer_complete(dma_buffer_t *b,uint8_t i){(void)b;(void)i;return false;}
bool dma_buffer_acquire(dma_buffer_t *b,uint8_t i,const uint8_t **p,size_t *n){(void)b;(void)i;(void)p;(void)n;return false;}
bool dma_buffer_release(dma_buffer_t *b,uint8_t i){(void)b;(void)i;return false;}
