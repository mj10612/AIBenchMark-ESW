/* AIBENCHMARK_ESW_CANARY_V1_tier2_can_frame */
#include "can_frame.h"
/* Implement caller-owned parsing, filtering and FIFO state. */
int can_decode(const can_mailbox_t *r,can_frame_t *f){(void)r;(void)f;return CAN_ARGUMENT;}
bool can_filter_matches(const can_frame_t *f,const can_filter_t *a){(void)f;(void)a;return false;}
int can_queue_init(can_queue_t *q,can_frame_t *s,size_t n){(void)q;(void)s;(void)n;return CAN_ARGUMENT;}
int can_queue_push(can_queue_t *q,const can_frame_t *f){(void)q;(void)f;return CAN_ARGUMENT;}
int can_queue_pop(can_queue_t *q,can_frame_t *f){(void)q;(void)f;return CAN_ARGUMENT;}
int can_queue_clear_overrun(can_queue_t *q){(void)q;return CAN_ARGUMENT;}
int can_dispatch(can_queue_t *q,const can_mailbox_t *r,const can_filter_t *f){(void)q;(void)r;(void)f;return CAN_ARGUMENT;}
