/* AIBENCHMARK_ESW_CANARY_V1_tier2_debounce_fsm */
#include "debounce_fsm.h"
#include <stddef.h>

void debounce_fsm_init(button_fsm_t* fsm, uint16_t debounce_threshold, uint16_t hold_threshold) {
    if (fsm == NULL) {
        return;
    }
    fsm->state = BUTTON_STATE_RELEASED;
    fsm->debounce_threshold = (debounce_threshold == 0U) ? 1U : debounce_threshold;
    fsm->hold_threshold = hold_threshold;
    fsm->debounce_counter = 0;
    fsm->press_duration = 0;
    fsm->hold_emitted = false;
}

button_event_t debounce_fsm_update(button_fsm_t* fsm, uint8_t raw_pin_level) {
    if (fsm == NULL) {
        return BUTTON_EVENT_NONE;
    }

    bool pressed = (raw_pin_level != 0U);
    button_event_t event = BUTTON_EVENT_NONE;

    switch (fsm->state) {
        case BUTTON_STATE_RELEASED:
            if (pressed) {
                fsm->debounce_counter = 1;
                if (fsm->debounce_counter >= fsm->debounce_threshold) {
                    fsm->state = BUTTON_STATE_PRESSED;
                    fsm->press_duration = 0;
                    fsm->hold_emitted = false;
                } else {
                    fsm->state = BUTTON_STATE_DEBOUNCE_PRESS;
                }
            }
            break;

        case BUTTON_STATE_DEBOUNCE_PRESS:
            if (pressed) {
                fsm->debounce_counter++;
                if (fsm->debounce_counter >= fsm->debounce_threshold) {
                    fsm->state = BUTTON_STATE_PRESSED;
                    fsm->press_duration = 0;
                    fsm->hold_emitted = false;
                }
            } else {
                fsm->state = BUTTON_STATE_RELEASED;
                fsm->debounce_counter = 0;
            }
            break;

        case BUTTON_STATE_PRESSED:
            fsm->press_duration++;
            if (!pressed) {
                fsm->debounce_counter = 1;
                if (fsm->debounce_counter >= fsm->debounce_threshold) {
                    fsm->state = BUTTON_STATE_RELEASED;
                    event = fsm->hold_emitted ? BUTTON_EVENT_RELEASE : BUTTON_EVENT_CLICK;
                } else {
                    fsm->state = BUTTON_STATE_DEBOUNCE_RELEASE;
                }
            } else {
                if ((fsm->hold_threshold > 0U) && 
                    (fsm->press_duration >= fsm->hold_threshold) && 
                    (!fsm->hold_emitted)) {
                    fsm->hold_emitted = true;
                    event = BUTTON_EVENT_HOLD;
                }
            }
            break;

        case BUTTON_STATE_DEBOUNCE_RELEASE:
            if (!pressed) {
                fsm->debounce_counter++;
                if (fsm->debounce_counter >= fsm->debounce_threshold) {
                    fsm->state = BUTTON_STATE_RELEASED;
                    event = fsm->hold_emitted ? BUTTON_EVENT_RELEASE : BUTTON_EVENT_CLICK;
                }
            } else {
                fsm->state = BUTTON_STATE_PRESSED;
                fsm->debounce_counter = 0;
            }
            break;

        default:
            fsm->state = BUTTON_STATE_RELEASED;
            fsm->debounce_counter = 0;
            break;
    }

    return event;
}

button_state_t debounce_fsm_get_state(const button_fsm_t* fsm) {
    if (fsm == NULL) {
        return BUTTON_STATE_RELEASED;
    }
    return fsm->state;
}
