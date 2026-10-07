/* AIBENCHMARK_ESW_CANARY_V1_tier4_uart_frame_fix */
#ifndef UART_FRAME_FIX_H
#define UART_FRAME_FIX_H
#include <stdint.h>
#include <stddef.h>
typedef int (*uart_read_fn)(void *,uint8_t *);
typedef void (*uart_reset_fn)(void *);
typedef struct {void *ctx;uart_read_fn read_byte;uart_reset_fn reset;} uart_hal_t;
enum {UART_OK=0,UART_ARGUMENT=-1,UART_IO=-2,UART_TIMEOUT=-3,UART_FRAME=-4,UART_SPACE=-5};
int uart_receive(const uart_hal_t *,uint8_t *output,size_t capacity,size_t *length,uint32_t max_polls);
#endif
