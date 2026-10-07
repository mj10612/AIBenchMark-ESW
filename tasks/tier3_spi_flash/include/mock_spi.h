/* AIBENCHMARK_ESW_CANARY_V1_tier3_spi_flash */
#ifndef MOCK_SPI_H
#define MOCK_SPI_H
#include <stddef.h>
#include <stdint.h>
/* One complete chip-select frame; zero means success, otherwise IO failure. */
typedef int (*spi_transaction_fn)(void *ctx,const uint8_t *tx,size_t tx_len,uint8_t *rx,size_t rx_len);
typedef struct { void *ctx; spi_transaction_fn transaction; } spi_hal_t;
#endif
