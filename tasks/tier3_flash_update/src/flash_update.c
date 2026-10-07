/* AIBENCHMARK_ESW_CANARY_V1_tier3_flash_update */
#include "flash_update.h"
uint16_t flash_update_crc(const uint8_t *p,size_t n){(void)p;(void)n;return 0;}
bool flash_update_begin(flash_update_t *u,const update_hal_t *h,uint8_t s,const uint8_t *p,size_t n){(void)u;(void)h;(void)s;(void)p;(void)n;return true;}
int flash_update_step(flash_update_t *u){(void)u;return UPDATE_OK;}
