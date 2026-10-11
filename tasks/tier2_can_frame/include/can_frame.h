#ifndef CAN_FRAME_H
#define CAN_FRAME_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#define CAN_QUEUE_MAX_CAPACITY 16U
enum { CAN_OK=0, CAN_ARGUMENT=-1, CAN_EMPTY=-2, CAN_ERR_OVERRUN=-3, CAN_FILTERED=-4 };
/* Virtual receive registers: standard ID bits 31:21 or extended ID bits 31:3;
 * IDE bit 2, RTR bit 1, reserved bit 0. Control low nibble is DLC. */
typedef struct { uint32_t identifier, control, data_low, data_high; } can_mailbox_t;
typedef struct { uint32_t id; bool extended, remote; uint8_t dlc, data[8]; } can_frame_t;
typedef struct { uint32_t id, mask; bool extended; } can_filter_t;
typedef struct { can_frame_t *storage; size_t capacity, head, tail, count; bool overrun, initialized; } can_queue_t;
int can_decode(const can_mailbox_t *raw, can_frame_t *frame);
bool can_filter_matches(const can_frame_t *frame, const can_filter_t *filter);
int can_queue_init(can_queue_t *queue, can_frame_t *storage, size_t capacity);
int can_queue_push(can_queue_t *queue, const can_frame_t *frame);
int can_queue_pop(can_queue_t *queue, can_frame_t *frame);
int can_queue_clear_overrun(can_queue_t *queue);
int can_dispatch(can_queue_t *queue, const can_mailbox_t *raw, const can_filter_t *filter);
#endif
