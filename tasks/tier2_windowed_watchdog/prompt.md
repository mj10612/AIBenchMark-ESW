# Windowed Watchdog and Heartbeat Coordinator

Implement windowed_watchdog.c using the supplied public header. All state belongs
to the caller; use no allocation or hidden globals. Up to eight IDs (0..7) register
unique heartbeat bits. Duplicate or unregistered IDs are argument errors.

Initialization requires a callback, 0 < window_min < window_max < 2^31, and records
the origin tick. Failed reinitialization disables the old manager. Registration
may add tasks while healthy; duplicate check-ins are idempotent and do not stand
in for another task. Service without registrations is an argument error.

Service computes unsigned uint32_t elapsed time across rollover. A valid window
includes both endpoints. Earlier service latches WATCHDOG_EARLY, later service
latches WATCHDOG_LATE, and service inside the window without every registered
heartbeat latches WATCHDOG_STARVED. Fault priority is early, late, then starvation.
Latched faults propagate and block registration, check-ins, and refresh until a
successful explicit initialization. Invalid arguments never clear a fault.

Only a healthy, fully synchronized service invokes refresh(context), exactly once.
After the callback, clear the heartbeat mask and set origin to now; every new
window requires fresh check-ins. Assume real elapsed time between service attempts
is less than 2^32 ticks. No wall-clock, hardware register, or provider access is used.
