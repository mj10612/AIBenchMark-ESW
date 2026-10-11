# CAN 2.0 Frame Parser, Acceptance Filter and Mailbox FIFO

Implement can_frame.c with no allocation or hidden mutable globals. This benchmark
defines virtual receive-register words; vendor-specific timestamp/FMI fields and
CAN-FD are outside the contract. Identifier bits 31:21 hold an 11-bit standard ID;
for IDE=1 (bit 2), bits 31:3 hold a 29-bit extended ID. RTR is bit 1. Bit 0 and,
for standard frames, bits 20:3 are reserved and must be zero. Control's low nibble
is DLC (0..8); every other control bit is reserved and must be zero.

Decode data_low then data_high least-significant byte first, copying only DLC
bytes and zeroing unused bytes. RTR keeps its requested DLC but has zero payload.
Reject NULL, reserved fields and DLC > 8, preserving the entire caller output.

Filters require matching IDE and (frame.id & mask)==(filter.id & mask). Validate
both filter ID and mask against the corresponding 11/29-bit range. RTR frames
are eligible by ID; a zero mask accepts every ID of the chosen frame format.

The caller supplies 1..16 frame slots for the FIFO. Invalid reinitialization
disables the queue. Validate frame ID/DLC and initialized queue bounds. A full
push returns CAN_ERR_OVERRUN, latches overrun and preserves queued data/indices.
Pops preserve FIFO across wrap; empty or invalid pops leave output unchanged.
Only can_queue_clear_overrun explicitly clears a healthy queue's overrun flag.
Remote frames pushed directly also store zero payload. can_dispatch validates,
decodes, filters, then enqueues; rejected frames never modify the queue. All APIs
are synchronous caller-owned operations; inter-thread synchronization is external.
