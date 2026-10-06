#include "unity.h"
#include "debounce_fsm.h"

static button_fsm_t btn;

void setUp(void) {
    debounce_fsm_init(&btn, 3, 10);
}

void tearDown(void) {}

void test_initial_state(void) {
    TEST_ASSERT_EQUAL(BUTTON_STATE_RELEASED, debounce_fsm_get_state(&btn));
}

void test_glitch_rejection_on_press(void) {
    /* 1 or 2 high pulses when threshold is 3 must not cause state to reach PRESSED */
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    TEST_ASSERT_TRUE(debounce_fsm_get_state(&btn) != BUTTON_STATE_PRESSED);

    /* Glitch drops to 0 */
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 0));
    TEST_ASSERT_TRUE(debounce_fsm_get_state(&btn) != BUTTON_STATE_PRESSED);

    /* The threshold must be accumulated from scratch after the glitch. */
    for (uint8_t tick = 0; tick < 2; tick++) {
        TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
        TEST_ASSERT_TRUE(debounce_fsm_get_state(&btn) != BUTTON_STATE_PRESSED);
    }
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    TEST_ASSERT_EQUAL(BUTTON_STATE_PRESSED, debounce_fsm_get_state(&btn));
}

void test_clean_click_event(void) {
    /* 3 consecutive 1s to reach pressed */
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    TEST_ASSERT_EQUAL(BUTTON_STATE_PRESSED, debounce_fsm_get_state(&btn));

    /* Hold for 2 ticks (total press < 10) */
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));

    /* A release glitch must not emit an event or confirm RELEASED. */
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 0));
    TEST_ASSERT_TRUE(debounce_fsm_get_state(&btn) != BUTTON_STATE_RELEASED);
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    TEST_ASSERT_TRUE(debounce_fsm_get_state(&btn) != BUTTON_STATE_RELEASED);

    /* Release still requires 3 consecutive 0s after the glitch. */
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 0));
    TEST_ASSERT_TRUE(debounce_fsm_get_state(&btn) != BUTTON_STATE_RELEASED);
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 0));
    TEST_ASSERT_TRUE(debounce_fsm_get_state(&btn) != BUTTON_STATE_RELEASED);
    button_event_t evt = debounce_fsm_update(&btn, 0);
    
    TEST_ASSERT_EQUAL(BUTTON_EVENT_CLICK, evt);
    TEST_ASSERT_EQUAL(BUTTON_STATE_RELEASED, debounce_fsm_get_state(&btn));
}

void test_hold_and_release_event(void) {
    /* Press for 3 ticks */
    debounce_fsm_update(&btn, 1);
    debounce_fsm_update(&btn, 1);
    debounce_fsm_update(&btn, 1);
    TEST_ASSERT_EQUAL(BUTTON_STATE_PRESSED, debounce_fsm_get_state(&btn));

    uint8_t hold_events = 0;
    for (int i = 0; i < 15; i++) {
        button_event_t e = debounce_fsm_update(&btn, 1);
        if (e == BUTTON_EVENT_HOLD) {
            ++hold_events;
        }
    }
    TEST_ASSERT_EQUAL_UINT(1, hold_events);

    /* A release glitch cannot re-arm HOLD for the current press. */
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 0));
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    for (uint16_t tick = 0; tick < 1000; ++tick) {
        TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(&btn, 1));
    }

    /* Release */
    debounce_fsm_update(&btn, 0);
    debounce_fsm_update(&btn, 0);
    button_event_t rel_evt = debounce_fsm_update(&btn, 0);
    TEST_ASSERT_EQUAL(BUTTON_EVENT_RELEASE, rel_evt);
    TEST_ASSERT_EQUAL(BUTTON_STATE_RELEASED, debounce_fsm_get_state(&btn));

    hold_events = 0;
    for (uint8_t tick = 0; tick < 25; ++tick) {
        if (debounce_fsm_update(&btn, 1) == BUTTON_EVENT_HOLD) ++hold_events;
    }
    TEST_ASSERT_EQUAL_UINT(1, hold_events);
}

void test_null_safety(void) {
    TEST_ASSERT_EQUAL(BUTTON_EVENT_NONE, debounce_fsm_update(NULL, 1));
    TEST_ASSERT_EQUAL(BUTTON_STATE_RELEASED, debounce_fsm_get_state(NULL));
}

int main(void) {
    UNITY_BEGIN();
    RUN_TEST(test_initial_state);
    RUN_TEST(test_glitch_rejection_on_press);
    RUN_TEST(test_clean_click_event);
    RUN_TEST(test_hold_and_release_event);
    RUN_TEST(test_null_safety);
    return UNITY_END();
}
