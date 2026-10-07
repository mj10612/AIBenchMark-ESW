/* AIBENCHMARK_ESW_CANARY_V1_tier2_debounce_fsm */
#include "debounce_fsm.h"

void debounce_fsm_init(button_fsm_t* fsm, uint16_t debounce_threshold, uint16_t hold_threshold) {
    (void)fsm;
    (void)debounce_threshold;
    (void)hold_threshold;
}

button_event_t debounce_fsm_update(button_fsm_t* fsm, uint8_t raw_pin_level) {
    (void)fsm;
    (void)raw_pin_level;
    return BUTTON_EVENT_NONE;
}

button_state_t debounce_fsm_get_state(const button_fsm_t* fsm) {
    (void)fsm;
    return BUTTON_STATE_RELEASED;
}
