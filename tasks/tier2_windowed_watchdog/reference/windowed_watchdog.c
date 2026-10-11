/* AIBENCHMARK_ESW_CANARY_V1_tier2_windowed_watchdog */
#include "windowed_watchdog.h"
#include <stddef.h>

bool watchdog_init(watchdog_t *m, uint32_t low, uint32_t high, uint32_t now,
                   watchdog_refresh_t refresh, void *context) {
    if (m == NULL) return false;
    m->initialized = false;
    if (low == 0 || high <= low || high >= UINT32_C(0x80000000) || refresh == NULL) return false;
    m->window_min=low; m->window_max=high; m->origin=now;
    m->registered=0; m->seen=0; m->refresh=refresh; m->context=context;
    m->fault=WATCHDOG_OK; m->initialized=true;
    return true;
}
int watchdog_register(watchdog_t *m, uint8_t id) {
    if (m == NULL || !m->initialized || id >= WATCHDOG_MAX_TASKS) return WATCHDOG_ARGUMENT;
    if (m->fault != WATCHDOG_OK) return m->fault;
    uint16_t bit=(uint16_t)(UINT16_C(1) << id);
    if ((m->registered & bit) != 0) return WATCHDOG_ARGUMENT;
    m->registered |= bit;
    return WATCHDOG_OK;
}
int watchdog_checkin(watchdog_t *m, uint8_t id) {
    if (m == NULL || !m->initialized || id >= WATCHDOG_MAX_TASKS) return WATCHDOG_ARGUMENT;
    if (m->fault != WATCHDOG_OK) return m->fault;
    uint16_t bit=(uint16_t)(UINT16_C(1) << id);
    if ((m->registered & bit) == 0) return WATCHDOG_ARGUMENT;
    m->seen |= bit;
    return WATCHDOG_OK;
}
int watchdog_service(watchdog_t *m, uint32_t now) {
    if (m == NULL || !m->initialized) return WATCHDOG_ARGUMENT;
    if (m->fault != WATCHDOG_OK) return m->fault;
    if (m->registered == 0) return WATCHDOG_ARGUMENT;
    uint32_t elapsed=now-m->origin;
    if (elapsed < m->window_min) m->fault=WATCHDOG_EARLY;
    else if (elapsed > m->window_max) m->fault=WATCHDOG_LATE;
    else if (m->seen != m->registered) m->fault=WATCHDOG_STARVED;
    if (m->fault != WATCHDOG_OK) return m->fault;
    m->refresh(m->context);
    m->seen=0;
    m->origin=now;
    return WATCHDOG_OK;
}
