#include "tick_timer.h"

void esw_timer_init(esw_timer_t *timer) {
    (void)timer; /* TODO: initialize caller-owned state. */
}

bool esw_timer_start(esw_timer_t *timer, uint32_t now, uint32_t interval, bool periodic) {
    (void)timer;
    (void)now;
    (void)interval;
    (void)periodic;
    return false;
}

void esw_timer_cancel(esw_timer_t *timer) {
    (void)timer;
}

uint32_t esw_timer_poll(esw_timer_t *timer, uint32_t now) {
    (void)timer;
    (void)now;
    return 0;
}

bool esw_timer_is_active(const esw_timer_t *timer) {
    (void)timer;
    return false;
}
