/* AIBENCHMARK_ESW_CANARY_V1_tier2_debounce_fsm */
#ifndef DEBOUNCE_FSM_H
#define DEBOUNCE_FSM_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    BUTTON_STATE_RELEASED = 0,
    BUTTON_STATE_DEBOUNCE_PRESS,
    BUTTON_STATE_PRESSED,
    BUTTON_STATE_DEBOUNCE_RELEASE
} button_state_t;

typedef enum {
    BUTTON_EVENT_NONE = 0,
    BUTTON_EVENT_CLICK,
    BUTTON_EVENT_HOLD,
    BUTTON_EVENT_RELEASE
} button_event_t;

typedef struct {
    button_state_t state;
    uint16_t debounce_threshold;
    uint16_t hold_threshold;
    uint16_t debounce_counter;
    uint16_t press_duration;
    bool hold_emitted;
} button_fsm_t;

void debounce_fsm_init(button_fsm_t* fsm, uint16_t debounce_threshold, uint16_t hold_threshold);
button_event_t debounce_fsm_update(button_fsm_t* fsm, uint8_t raw_pin_level);
button_state_t debounce_fsm_get_state(const button_fsm_t* fsm);

#ifdef __cplusplus
}
#endif

#endif /* DEBOUNCE_FSM_H */
