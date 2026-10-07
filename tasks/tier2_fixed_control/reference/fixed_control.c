/* AIBENCHMARK_ESW_CANARY_V1_tier2_fixed_control */
#include "fixed_control.h"
#include <stddef.h>
#include <limits.h>

bool fixed_pid_init(fixed_pid_t *p, int16_t kp, int16_t ki, int16_t kd, int16_t minimum, int16_t maximum) {
    if (p == NULL) return false;
    p->ready = false;
    if (minimum > maximum) return false;
    p->kp = kp; p->ki = ki; p->kd = kd;
    p->minimum = minimum; p->maximum = maximum;
    p->integral = 0; p->previous = 0; p->ready = true;
    return true;
}

int16_t fixed_pid_step(fixed_pid_t *p, int16_t error) {
    if (p == NULL || !p->ready) return 0;
    int64_t accumulated = (int64_t)p->integral + error;
    if (accumulated > INT32_MAX) accumulated = INT32_MAX;
    if (accumulated < INT32_MIN) accumulated = INT32_MIN;
    int64_t numerator = (int64_t)p->kp * error + (int64_t)p->ki * accumulated +
        (int64_t)p->kd * ((int32_t)error - p->previous);
    int64_t value = numerator / 256;
    bool windup = (value > p->maximum && error > 0) || (value < p->minimum && error < 0);
    if (!windup) p->integral = (int32_t)accumulated;
    p->previous = error;
    if (value > p->maximum) return p->maximum;
    if (value < p->minimum) return p->minimum;
    return (int16_t)value;
}

int16_t fixed_filter_step(int16_t previous, int16_t sample, uint16_t alpha) {
    int32_t a = alpha > 256U ? 256 : (int32_t)alpha;
    int32_t numerator = (int32_t)previous * (256 - a) + (int32_t)sample * a;
    return (int16_t)(numerator / 256);
}
