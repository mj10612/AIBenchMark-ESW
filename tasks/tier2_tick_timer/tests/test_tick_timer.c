#include "unity.h"
#include "tick_timer.h"
#include <stddef.h>

void setUp(void) {}
void tearDown(void) {}

void test_init_resets_all_state(void) {
    esw_timer_t timer = {7, 8, true, true};
    esw_timer_init(&timer);
    TEST_ASSERT_EQUAL_HEX32(0, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(0, timer.interval);
    TEST_ASSERT_FALSE(timer.periodic);
    TEST_ASSERT_FALSE(esw_timer_is_active(&timer));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, UINT32_MAX));
}

void test_null_arguments(void) {
    esw_timer_init(NULL);
    esw_timer_cancel(NULL);
    TEST_ASSERT_FALSE(esw_timer_start(NULL, 1, 1, true));
    TEST_ASSERT_FALSE(esw_timer_is_active(NULL));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(NULL, 100));
}

void test_start_records_configuration(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 100, 10, true));
    TEST_ASSERT_EQUAL_HEX32(100, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(10, timer.interval);
    TEST_ASSERT_TRUE(timer.periodic);
    TEST_ASSERT_TRUE(esw_timer_is_active(&timer));
}

void test_zero_interval_preserves_existing_timer(void) {
    esw_timer_t timer;
    esw_timer_init(&timer);
    TEST_ASSERT_FALSE(esw_timer_start(&timer, 77, 0, true));
    TEST_ASSERT_EQUAL_HEX32(0, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(0, timer.interval);
    TEST_ASSERT_FALSE(timer.periodic);
    TEST_ASSERT_FALSE(esw_timer_is_active(&timer));
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 100, 10, true));
    TEST_ASSERT_FALSE(esw_timer_start(&timer, 105, 0, false));
    TEST_ASSERT_EQUAL_HEX32(100, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(10, timer.interval);
    TEST_ASSERT_TRUE(timer.periodic);
    TEST_ASSERT_TRUE(esw_timer_is_active(&timer));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 110));
}

void test_one_shot_exact_deadline_fires_once(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 100, 10, false));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 100));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 109));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 110));
    TEST_ASSERT_FALSE(esw_timer_is_active(&timer));
    TEST_ASSERT_EQUAL_HEX32(100, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(10, timer.interval);
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 110));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 120));
}

void test_delayed_one_shot_returns_one(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 50, 10, false));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 99));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 100));
}

void test_one_shot_across_counter_wrap(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, UINT32_MAX - 4, 10, false));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, UINT32_MAX));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 0));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 4));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 5));
}

void test_periodic_exact_and_repeated_poll(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 10, 5, true));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 14));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 15));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 15));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 20));
    TEST_ASSERT_TRUE(esw_timer_is_active(&timer));
}

void test_periodic_retains_missed_count_and_phase(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 100, 10, true));
    TEST_ASSERT_EQUAL_HEX32(3, esw_timer_poll(&timer, 139));
    TEST_ASSERT_EQUAL_HEX32(130, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 139));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 140));
}

void test_periodic_phase_across_wrap(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, UINT32_MAX - 4, 3, true));
    TEST_ASSERT_EQUAL_HEX32(3, esw_timer_poll(&timer, 4));
    TEST_ASSERT_EQUAL_HEX32(4, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 5));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 7));
}

void test_unit_interval_handles_maximum_expiration_count(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 7, 1, true));
    TEST_ASSERT_EQUAL_HEX32(UINT32_MAX, esw_timer_poll(&timer, 6));
    TEST_ASSERT_EQUAL_HEX32(6, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 6));
}

void test_full_range_intervals_are_supported(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 13, UINT32_MAX, false));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 11));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 12));
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 12, UINT32_C(0x80000001), true));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, UINT32_C(0x8000000c)));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, UINT32_C(0x8000000d)));
}

void test_cancel_is_idempotent_and_retains_configuration(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 100, 10, true));
    esw_timer_cancel(&timer);
    esw_timer_cancel(&timer);
    TEST_ASSERT_FALSE(esw_timer_is_active(&timer));
    TEST_ASSERT_EQUAL_HEX32(100, timer.started_at);
    TEST_ASSERT_EQUAL_HEX32(10, timer.interval);
    TEST_ASSERT_TRUE(timer.periodic);
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 150));
}

void test_restart_changes_origin_interval_and_mode(void) {
    esw_timer_t timer;
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 100, 10, true));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 110));
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 111, 20, false));
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 130));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&timer, 131));
    TEST_ASSERT_FALSE(esw_timer_is_active(&timer));
    TEST_ASSERT_TRUE(esw_timer_start(&timer, 150, 5, true));
    TEST_ASSERT_EQUAL_HEX32(2, esw_timer_poll(&timer, 160));
    esw_timer_init(&timer);
    TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&timer, 170));
}

void test_timer_instances_are_independent(void) {
    esw_timer_t first, second;
    TEST_ASSERT_TRUE(esw_timer_start(&first, 0, 7, true));
    TEST_ASSERT_TRUE(esw_timer_start(&second, 0, 10, false));
    TEST_ASSERT_EQUAL_HEX32(3, esw_timer_poll(&first, 21));
    TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&second, 21));
    TEST_ASSERT_TRUE(esw_timer_is_active(&first));
    TEST_ASSERT_FALSE(esw_timer_is_active(&second));
}

void test_interval_origin_boundary_matrix(void) {
    const uint32_t intervals[] = {1, 3, 255, 65535, 65536, UINT32_C(0x80000000), UINT32_MAX};
    const uint32_t origins[] = {0, 1, 65535, UINT32_C(0x7fffffff), UINT32_MAX - 3};
    size_t i, j;
    for (i = 0; i < sizeof(intervals) / sizeof(intervals[0]); ++i) {
        for (j = 0; j < sizeof(origins) / sizeof(origins[0]); ++j) {
            esw_timer_t exact, delayed;
            uint32_t interval = intervals[i], origin = origins[j];
            uint32_t expected_count = (uint32_t)((uint64_t)UINT32_MAX / interval);
            uint32_t expected_origin = (uint32_t)((uint64_t)origin + UINT32_MAX - ((uint64_t)UINT32_MAX % interval));
            TEST_ASSERT_TRUE(esw_timer_start(&exact, origin, interval, true));
            TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&exact, origin + interval - 1));
            TEST_ASSERT_EQUAL_HEX32(1, esw_timer_poll(&exact, origin + interval));
            TEST_ASSERT_EQUAL_HEX32(0, esw_timer_poll(&exact, origin + interval));
            /* Independent delayed-poll scenario; all elapsed values satisfy the observation limit. */
            TEST_ASSERT_TRUE(esw_timer_start(&delayed, origin, interval, true));
            TEST_ASSERT_EQUAL_HEX32(expected_count, esw_timer_poll(&delayed, origin + UINT32_MAX));
            TEST_ASSERT_EQUAL_HEX32(expected_origin, delayed.started_at);
        }
    }
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_init_resets_all_state);
    RUN_TEST(test_null_arguments);
    RUN_TEST(test_start_records_configuration);
    RUN_TEST(test_zero_interval_preserves_existing_timer);
    RUN_TEST(test_one_shot_exact_deadline_fires_once);
    RUN_TEST(test_delayed_one_shot_returns_one);
    RUN_TEST(test_one_shot_across_counter_wrap);
    RUN_TEST(test_periodic_exact_and_repeated_poll);
    RUN_TEST(test_periodic_retains_missed_count_and_phase);
    RUN_TEST(test_periodic_phase_across_wrap);
    RUN_TEST(test_unit_interval_handles_maximum_expiration_count);
    RUN_TEST(test_full_range_intervals_are_supported);
    RUN_TEST(test_cancel_is_idempotent_and_retains_configuration);
    RUN_TEST(test_restart_changes_origin_interval_and_mode);
    RUN_TEST(test_timer_instances_are_independent);
    RUN_TEST(test_interval_origin_boundary_matrix);
    return UNITY_END();
}
