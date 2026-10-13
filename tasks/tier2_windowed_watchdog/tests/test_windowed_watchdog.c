/* AIBENCHMARK_ESW_CANARY_V1_tier2_windowed_watchdog */
#include "unity.h"
#include "windowed_watchdog.h"
#include <string.h>
static watchdog_t m;
static int kicks;
static int context_sentinel;
static void kick(void *ctx){TEST_ASSERT_TRUE(ctx==&context_sentinel);TEST_ASSERT_EQUAL_UINT(m.registered,m.seen);++kicks;}
void setUp(void){memset(&m,0,sizeof(m));kicks=0;}
void tearDown(void){}
static void ready(uint32_t origin){TEST_ASSERT_TRUE(watchdog_init(&m,8,12,origin,kick,&context_sentinel));TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_register(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_register(&m,2));}
static void beat(void){TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_checkin(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_checkin(&m,2));}
void test_initialization_validation(void){TEST_ASSERT_FALSE(watchdog_init(NULL,8,12,0,kick,NULL));TEST_ASSERT_FALSE(watchdog_init(&m,0,12,0,kick,NULL));TEST_ASSERT_FALSE(watchdog_init(&m,8,8,0,kick,NULL));TEST_ASSERT_FALSE(watchdog_init(&m,8,UINT32_C(0x80000000),0,kick,NULL));TEST_ASSERT_FALSE(watchdog_init(&m,8,12,0,NULL,NULL));TEST_ASSERT_FALSE(m.initialized);TEST_ASSERT_EQUAL(0,kicks);}
void test_unique_registration_and_all_eight_slots(void){TEST_ASSERT_TRUE(watchdog_init(&m,8,12,0,kick,&context_sentinel));for(uint8_t id=0;id<8;++id)TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_register(&m,id));TEST_ASSERT_EQUAL_UINT(255,m.registered);TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_register(&m,3));TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_register(&m,8));TEST_ASSERT_EQUAL_UINT(255,m.registered);}
void test_no_tasks_never_refreshes(void){TEST_ASSERT_TRUE(watchdog_init(&m,8,12,0,kick,&context_sentinel));TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_service(&m,10));TEST_ASSERT_EQUAL(0,kicks);TEST_ASSERT_EQUAL(WATCHDOG_OK,m.fault);}
void test_all_tasks_refresh_once_and_clear_seen(void){ready(100);beat();TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_service(&m,110));TEST_ASSERT_EQUAL(1,kicks);TEST_ASSERT_EQUAL_UINT(0,m.seen);TEST_ASSERT_EQUAL_UINT(110,m.origin);}
void test_early_fault_latches(void){ready(100);beat();TEST_ASSERT_EQUAL(WATCHDOG_EARLY,watchdog_service(&m,107));TEST_ASSERT_EQUAL(WATCHDOG_EARLY,watchdog_service(&m,110));TEST_ASSERT_EQUAL(WATCHDOG_EARLY,watchdog_checkin(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_EARLY,watchdog_register(&m,1));TEST_ASSERT_EQUAL(0,kicks);}
void test_late_fault_latches(void){ready(100);beat();TEST_ASSERT_EQUAL(WATCHDOG_LATE,watchdog_service(&m,113));TEST_ASSERT_EQUAL(WATCHDOG_LATE,watchdog_service(&m,110));TEST_ASSERT_EQUAL(0,kicks);}
void test_starvation_latches_and_cannot_be_cleared_by_checkin(void){ready(0);TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_checkin(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_STARVED,watchdog_service(&m,8));TEST_ASSERT_EQUAL(WATCHDOG_STARVED,watchdog_checkin(&m,2));TEST_ASSERT_EQUAL(WATCHDOG_STARVED,watchdog_service(&m,12));TEST_ASSERT_EQUAL(0,kicks);}
void test_window_endpoints_are_inclusive(void){ready(0);beat();TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_service(&m,8));beat();TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_service(&m,20));TEST_ASSERT_EQUAL(2,kicks);}
void test_rollover_uses_unsigned_elapsed(void){ready(UINT32_MAX-5U);beat();TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_service(&m,2));TEST_ASSERT_EQUAL(1,kicks);TEST_ASSERT_EQUAL_UINT(2,m.origin);}
void test_duplicate_heartbeat_does_not_satisfy_other_task(void){ready(0);TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_checkin(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_checkin(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_STARVED,watchdog_service(&m,9));TEST_ASSERT_EQUAL(0,kicks);}
void test_heartbeats_do_not_carry_into_next_window(void){ready(0);beat();TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_service(&m,8));TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_checkin(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_STARVED,watchdog_service(&m,16));TEST_ASSERT_EQUAL(1,kicks);}
void test_invalid_calls_have_no_side_effects(void){TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_service(NULL,0));TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_register(&m,0));TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_checkin(&m,0));ready(0);TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_checkin(&m,1));TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_checkin(&m,8));TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_checkin(NULL,0));TEST_ASSERT_EQUAL_UINT(0,m.seen);TEST_ASSERT_EQUAL(0,kicks);}
void test_explicit_restart_and_failed_reinitialization(void){ready(0);TEST_ASSERT_EQUAL(WATCHDOG_EARLY,watchdog_service(&m,1));TEST_ASSERT_FALSE(watchdog_init(&m,0,12,0,kick,&context_sentinel));TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT,watchdog_service(&m,9));ready(100);beat();TEST_ASSERT_EQUAL(WATCHDOG_OK,watchdog_service(&m,108));TEST_ASSERT_EQUAL(1,kicks);}
static const uint32_t legal_windows[][2] = {
    {1U, 2U}, {100U, 1000U}, {UINT32_C(0x7ffffffe), UINT32_C(0x7fffffff)},
    {1U, UINT32_C(0x7fffffff)}
};
static void ready_window(uint32_t low, uint32_t high, uint32_t origin) {
    TEST_ASSERT_TRUE(watchdog_init(&m, low, high, origin, kick, &context_sentinel));
    TEST_ASSERT_EQUAL_UINT(low, m.window_min);
    TEST_ASSERT_EQUAL_UINT(high, m.window_max);
    TEST_ASSERT_EQUAL_UINT(origin, m.origin);
    TEST_ASSERT_EQUAL(WATCHDOG_OK, watchdog_register(&m, 0));
    TEST_ASSERT_EQUAL(WATCHDOG_OK, watchdog_register(&m, 2));
}
void test_legal_window_domain_endpoints_and_rollover(void) {
    for (size_t i = 0; i < sizeof(legal_windows)/sizeof(legal_windows[0]); ++i) {
        uint32_t low = legal_windows[i][0], high = legal_windows[i][1];
        uint32_t origin = UINT32_MAX;
        kicks = 0;
        ready_window(low, high, origin);
        beat();
        TEST_ASSERT_EQUAL(WATCHDOG_OK, watchdog_service(&m, origin + low));
        TEST_ASSERT_EQUAL_UINT(origin + low, m.origin);
        TEST_ASSERT_EQUAL_UINT(0, m.seen);
        beat();
        TEST_ASSERT_EQUAL(WATCHDOG_OK, watchdog_service(&m, origin + low + high));
        TEST_ASSERT_EQUAL(2, kicks);
    }
}
void test_legal_window_domain_faults_latch(void) {
    for (size_t i = 0; i < sizeof(legal_windows)/sizeof(legal_windows[0]); ++i) {
        uint32_t low = legal_windows[i][0], high = legal_windows[i][1];
        kicks = 0;
        ready_window(low, high, UINT32_MAX);
        beat();
        TEST_ASSERT_EQUAL(WATCHDOG_EARLY, watchdog_service(&m, UINT32_MAX + low - 1U));
        TEST_ASSERT_EQUAL(WATCHDOG_EARLY, watchdog_service(&m, UINT32_MAX + high));
        TEST_ASSERT_EQUAL(WATCHDOG_EARLY, watchdog_checkin(&m, 0));
        ready_window(low, high, UINT32_MAX);
        beat();
        TEST_ASSERT_EQUAL(WATCHDOG_LATE, watchdog_service(&m, UINT32_MAX + high + 1U));
        TEST_ASSERT_EQUAL(WATCHDOG_LATE, watchdog_service(&m, UINT32_MAX + low));
        TEST_ASSERT_EQUAL(WATCHDOG_LATE, watchdog_checkin(&m, 0));
        TEST_ASSERT_EQUAL(0, kicks);
        TEST_ASSERT_FALSE(watchdog_init(&m, high, low, 0, kick, &context_sentinel));
        TEST_ASSERT_FALSE(m.initialized);
        TEST_ASSERT_EQUAL(WATCHDOG_ARGUMENT, watchdog_service(&m, low));
        TEST_ASSERT_EQUAL(0, kicks);
    }
}
int main(void){UNITY_BEGIN();RUN_TEST(test_legal_window_domain_endpoints_and_rollover);RUN_TEST(test_legal_window_domain_faults_latch);RUN_TEST(test_initialization_validation);RUN_TEST(test_unique_registration_and_all_eight_slots);RUN_TEST(test_no_tasks_never_refreshes);RUN_TEST(test_all_tasks_refresh_once_and_clear_seen);RUN_TEST(test_early_fault_latches);RUN_TEST(test_late_fault_latches);RUN_TEST(test_starvation_latches_and_cannot_be_cleared_by_checkin);RUN_TEST(test_window_endpoints_are_inclusive);RUN_TEST(test_rollover_uses_unsigned_elapsed);RUN_TEST(test_duplicate_heartbeat_does_not_satisfy_other_task);RUN_TEST(test_heartbeats_do_not_carry_into_next_window);RUN_TEST(test_invalid_calls_have_no_side_effects);RUN_TEST(test_explicit_restart_and_failed_reinitialization);return UNITY_END();}
