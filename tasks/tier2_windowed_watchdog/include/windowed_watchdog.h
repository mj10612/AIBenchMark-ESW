/* AIBENCHMARK_ESW_CANARY_V1_tier2_windowed_watchdog */
#ifndef WINDOWED_WATCHDOG_H
#define WINDOWED_WATCHDOG_H
#include <stdbool.h>
#include <stdint.h>
#define WATCHDOG_MAX_TASKS 8U
enum { WATCHDOG_OK=0, WATCHDOG_ARGUMENT=-1, WATCHDOG_EARLY=-2, WATCHDOG_LATE=-3, WATCHDOG_STARVED=-4 };
typedef void (*watchdog_refresh_t)(void *context);
typedef struct {
    uint32_t window_min, window_max, origin;
    uint16_t registered, seen;
    watchdog_refresh_t refresh;
    void *context;
    int fault;
    bool initialized;
} watchdog_t;
bool watchdog_init(watchdog_t *manager, uint32_t window_min, uint32_t window_max,
                   uint32_t now, watchdog_refresh_t refresh, void *context);
int watchdog_register(watchdog_t *manager, uint8_t task_id);
int watchdog_checkin(watchdog_t *manager, uint8_t task_id);
int watchdog_service(watchdog_t *manager, uint32_t now);
#endif
