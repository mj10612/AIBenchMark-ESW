<!-- AIBENCHMARK_ESW_CANARY_V1_tier4_uart_frame_fix -->
# Task: UART Framing and Recovery Bug Fix

Repair the starter. Receive `[0xA5,length,payload,xor]`, length 1..32, checksum XOR of length and payload (excluding sync). read_byte returns 1 for a byte, 0 for temporarily unavailable, negative for IO error. Skip bytes before sync. max_polls is a single budget for the whole call, including successful bytes and noise; consume at most that many HAL reads. On timeout, IO, malformed length/checksum, or insufficient capacity invoke reset exactly once and preserve caller output and length. On success publish only validated payload and length. Validate all pointers/callbacks and nonzero budget before touching HAL; invalid arguments do not reset. Capacity zero is valid and returns SPACE once length is known. No hidden persistent parser state; each call starts seeking sync.

Implement `src/uart_frame_fix.c` using the public header. No allocation, host I/O, floating point, or unbounded loops. Caller owns all state and storage. The tests are public host fixtures, not hardware certification.
