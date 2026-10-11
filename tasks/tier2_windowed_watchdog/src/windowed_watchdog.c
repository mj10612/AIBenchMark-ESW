/* AIBENCHMARK_ESW_CANARY_V1_tier2_windowed_watchdog */
#include "windowed_watchdog.h"
/* Implement the public contract without allocation or hidden global state. */
bool watchdog_init(watchdog_t *m,uint32_t low,uint32_t high,uint32_t now,watchdog_refresh_t refresh,void *ctx){(void)m;(void)low;(void)high;(void)now;(void)refresh;(void)ctx;return false;}
int watchdog_register(watchdog_t *m,uint8_t id){(void)m;(void)id;return WATCHDOG_ARGUMENT;}
int watchdog_checkin(watchdog_t *m,uint8_t id){(void)m;(void)id;return WATCHDOG_ARGUMENT;}
int watchdog_service(watchdog_t *m,uint32_t now){(void)m;(void)now;return WATCHDOG_ARGUMENT;}
