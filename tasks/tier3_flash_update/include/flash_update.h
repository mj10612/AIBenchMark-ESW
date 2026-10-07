/* AIBENCHMARK_ESW_CANARY_V1_tier3_flash_update */
#ifndef FLASH_UPDATE_H
#define FLASH_UPDATE_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
typedef int (*update_erase_fn)(void *,uint8_t slot);
typedef int (*update_write_fn)(void *,uint8_t slot,size_t offset,const uint8_t *,size_t);
typedef int (*update_read_fn)(void *,uint8_t slot,size_t offset,uint8_t *,size_t);
typedef int (*update_commit_fn)(void *,uint8_t slot,uint16_t crc,size_t length);
typedef struct {void *ctx;update_erase_fn erase;update_write_fn write;update_read_fn read;update_commit_fn commit;} update_hal_t;
enum {UPDATE_IDLE=0,UPDATE_ERASE=1,UPDATE_WRITE=2,UPDATE_VERIFY=3,UPDATE_COMMIT=4,UPDATE_DONE=5,UPDATE_ERROR=6};
enum {UPDATE_OK=0,UPDATE_ARGUMENT=-1,UPDATE_IO=-2,UPDATE_CRC=-3};
typedef struct {update_hal_t hal;const uint8_t *data;size_t length,offset;uint16_t crc,verified;uint8_t target,state;bool initialized;} flash_update_t;
uint16_t flash_update_crc(const uint8_t *,size_t);
bool flash_update_begin(flash_update_t *,const update_hal_t *,uint8_t active_slot,const uint8_t *,size_t);
int flash_update_step(flash_update_t *);
#endif
