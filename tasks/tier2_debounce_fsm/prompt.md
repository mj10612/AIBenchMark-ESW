# Task: Digital Input Debounce & Button Event FSM

You are an embedded software engineer. Implement a robust button debouncing Finite State Machine in C99.

## Specifications
Mechanical buttons experience contact bouncing (noise) when pressed or released. A periodic sampling routine filters out glitches and generates clean user events.

### Events:
- `BUTTON_EVENT_NONE`: No event occurred in this tick.
- `BUTTON_EVENT_CLICK`: Triggered when the button is pressed and released before reaching `hold_threshold` ticks. (Fired upon release).
- `BUTTON_EVENT_HOLD`: Triggered once when the button has remained continuously pressed for `hold_threshold` ticks.
- `BUTTON_EVENT_RELEASE`: Triggered upon button release if it was previously held.

### Logic:
- Button is considered active/pressed when `raw_pin_level == 1`, released when `raw_pin_level == 0`.
- Transition to pressed state requires `debounce_threshold` consecutive ticks of active level.
- Transition to released state requires `debounce_threshold` consecutive ticks of inactive level.
- If raw level flips before reaching `debounce_threshold`, counter resets (glitch rejection).

## Functions to implement in `src/debounce_fsm.c`:
1. `void debounce_fsm_init(button_fsm_t* fsm, uint16_t debounce_threshold, uint16_t hold_threshold);`
2. `button_event_t debounce_fsm_update(button_fsm_t* fsm, uint8_t raw_pin_level);`
3. `button_state_t debounce_fsm_get_state(const button_fsm_t* fsm);`
