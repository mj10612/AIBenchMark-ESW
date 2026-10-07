<!-- AIBENCHMARK_ESW_CANARY_V1_tier2_tick_timer -->
# Rollover-Safe Tick Timer

Implement the API in `tick_timer.h` using portable C99. A caller supplies
monotonic elapsed ticks reduced modulo 2^32 as `uint32_t now`; the counter may
wrap from UINT32_MAX to zero. Tick units are chosen by the caller.

Use only the caller-owned `esw_timer_t`. No blocking waits, callbacks, dynamic
allocation, floating point, or mutable global/static state. Do not change the
header or provide a main function.

## Contract

- `esw_timer_init(timer)` resets all fields to zero/false. Calling it again
  cancels any running timer.
- `esw_timer_start(timer, now, interval, periodic)` starts or restarts a timer:
  set `started_at = now`, the requested interval/mode, and `active = true`.
  Return true on success. Every interval from 1 through UINT32_MAX is valid;
  interval zero returns false and leaves every field unchanged.
- `esw_timer_cancel(timer)` clears only `active`. Repeated cancellation is safe.
- `esw_timer_is_active(timer)` reports the active flag.
- `esw_timer_poll(timer, now)` returns zero for an inactive timer or before its
  interval has elapsed. Reaching a deadline exactly counts as an expiration.
  For a one-shot timer, return 1 once and clear only `active`, even if polling
  was delayed by several intervals.
- For a periodic timer, return the number of whole intervals elapsed since
  `started_at`. Advance `started_at` by exactly that many intervals modulo
  2^32; keep the timer active and retain the original phase. For example, start
  at 100 with interval 10, poll at 135: return 3, then poll at 140: return 1.
  Resetting the origin to the polling time would introduce drift.
- All functions accept NULL: init/cancel do nothing, start/is_active return
  false, and poll returns zero. Valid timer objects are initialized or started
  before use. The caller does not otherwise modify their fields.

## Observation limit

Real elapsed time from the stored `started_at` to each poll must be less than
2^32 ticks. The caller must poll frequently enough to maintain that bound;
periodic polling retains a partial-interval remainder, so it is not sufficient
merely to bound time since the previous poll. Backward clock adjustments and
elapsed times of a full 2^32 ticks or more are outside the contract, since a
32-bit counter cannot distinguish them. Do not impose a half-range restriction:
intervals and valid elapsed values above INT32_MAX must work.

Use unsigned 32-bit elapsed arithmetic so wrap is handled without signed
overflow or implementation-defined signed conversions. The implementation must
also work on targets with 16-bit int. The host object budget is 1536 bytes Flash
and zero static RAM; caller storage and stack are not included in that RAM metric.
