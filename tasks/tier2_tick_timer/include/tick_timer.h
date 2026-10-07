/* AIBENCHMARK_ESW_CANARY_V1_tier2_tick_timer */
#ifndef TICK_TIMER_H
#define TICK_TIMER_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t started_at;
    uint32_t interval;
    bool periodic;
    bool active;
} esw_timer_t;

void esw_timer_init(esw_timer_t *timer);
/* interval must be nonzero. Failure leaves an existing timer unchanged. */
bool esw_timer_start(esw_timer_t *timer, uint32_t now, uint32_t interval, bool periodic);
void esw_timer_cancel(esw_timer_t *timer);
/* One-shot: 0 or 1. Periodic: elapsed expirations, preserving phase.
 * Real elapsed time from started_at must remain less than 2^32 ticks.
 */
uint32_t esw_timer_poll(esw_timer_t *timer, uint32_t now);
bool esw_timer_is_active(const esw_timer_t *timer);

#endif
