/* AIBENCHMARK_ESW_CANARY_V1_tier3_spi_flash */
#ifndef SPI_FLASH_H
#define SPI_FLASH_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "mock_spi.h"
typedef struct { spi_hal_t hal; uint32_t poll_limit; bool initialized; } spi_flash_t;
enum { FLASH_OK=0, FLASH_ARGUMENT=-1, FLASH_IO=-2, FLASH_TIMEOUT=-3 };
int spi_flash_init(spi_flash_t *,const spi_hal_t *,uint32_t poll_limit,uint8_t jedec[3]);
int spi_flash_program(spi_flash_t *,uint32_t address,const uint8_t *,size_t);
int spi_flash_erase(spi_flash_t *,uint32_t address);
#endif
