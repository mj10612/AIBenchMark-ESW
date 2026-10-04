#include "tick_timer.h"
#include <stddef.h>

void esw_timer_init(esw_timer_t *timer) {
    if (timer != NULL) {
        timer->started_at = 0;
        timer->interval = 0;
        timer->periodic = false;
        timer->active = false;
    }
}

bool esw_timer_start(esw_timer_t *timer, uint32_t now, uint32_t interval, bool periodic) {
    if (timer == NULL || interval == 0) {
        return false;
    }
    timer->started_at = now;
    timer->interval = interval;
    timer->periodic = periodic;
    timer->active = true;
    return true;
}

void esw_timer_cancel(esw_timer_t *timer) {
    if (timer != NULL) {
        timer->active = false;
    }
}

uint32_t esw_timer_poll(esw_timer_t *timer, uint32_t now) {
    uint32_t elapsed;
    uint32_t count;
    if (timer == NULL || !timer->active) {
        return 0;
    }
    elapsed = now - timer->started_at;
    if (elapsed < timer->interval) {
        return 0;
    }
    if (!timer->periodic) {
        timer->active = false;
        return 1;
    }
    count = elapsed / timer->interval;
    timer->started_at += count * timer->interval;
    return count;
}

bool esw_timer_is_active(const esw_timer_t *timer) {
    return timer != NULL && timer->active;
}
