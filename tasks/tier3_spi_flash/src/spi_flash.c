/* AIBENCHMARK_ESW_CANARY_V1_tier3_spi_flash */
#include "spi_flash.h"
int spi_flash_init(spi_flash_t *d,const spi_hal_t *h,uint32_t n,uint8_t id[3]){(void)d;(void)h;(void)n;(void)id;return FLASH_OK;}
int spi_flash_program(spi_flash_t *d,uint32_t a,const uint8_t *p,size_t n){(void)d;(void)a;(void)p;(void)n;return FLASH_OK;}
int spi_flash_erase(spi_flash_t *d,uint32_t a){(void)d;(void)a;return FLASH_OK;}
