<!-- AIBENCHMARK_ESW_CANARY_V1_tier2_cobs_codec -->
# Bounded COBS Packet Codec

Implement `cobs_encode` and `cobs_decode` in portable C99 using `cobs_codec.h`.
Consistent Overhead Byte Stuffing (COBS) encodes arbitrary bytes as a packet
body without zero bytes. Transport delimiters are outside both functions.
Algorithm reference: Stuart Cheshire and Mary Baker,
https://www.stuartcheshire.org/papers/COBSforSIGCOMM/.

## Encoding and decoding contract

A code byte in [1, 254] precedes `code - 1` nonzero payload bytes. Decoding
inserts a zero after this group only when another group follows. Code 255
precedes exactly 254 nonzero bytes and never inserts a zero.

The encoder emits maximal nonzero groups of up to 254 bytes and the shortest
canonical encoding: a terminal full 255-code group has no extra trailing
code byte. The decoder also accepts an equivalent trailing empty 1-code group
after a terminal full group. For example:

- empty input encodes as `[1]`; `[1]` decodes to empty output;
- `[0]` encodes as `[1, 1]`;
- `[17, 0, 34]` encodes as `[2, 17, 2, 34]`;
- 254 nonzero bytes encode as `[255, <254 bytes>]`;
- 254 nonzero bytes followed by zero encode as
  `[255, <254 bytes>, 1, 1]`.

Do not emit or accept a transport delimiter. Decode returns `COBS_MALFORMED`
for empty encoded input, a zero code, a zero inside payload, or a code whose
payload extends beyond `src_len`.

## Buffer and error contract

- Inputs and outputs use caller-owned, non-overlapping buffers; overlap is
  outside the contract. The `written` object also must not overlap either buffer.
- `written` is required. If non-NULL, set it to zero before validation and leave
  it zero on every failure. On success it is the exact output length.
- `src == NULL` is valid only for `src_len == 0`; `dst == NULL` is valid only
  for `dst_capacity == 0`. Invalid pointer/length combinations return
  `COBS_INVALID_ARGUMENT` before examining bytes.
- Insufficient capacity returns `COBS_NO_SPACE`, without accessing beyond the
  given capacity. A NULL, zero-capacity destination can successfully decode
  `[1]` because it writes no bytes; encoding empty input needs one output byte.
- On other failures, bytes within the destination capacity may have been
  modified; bytes outside that capacity and all source bytes must be unchanged.
  When malformed encoding and insufficient capacity both occur, either error
  status is allowed. Never read beyond `src_len`.

Use no dynamic allocation, floating point, mutable global/static state, or
`main` function. Use fixed-width bytes and overflow-safe `size_t` indexing.
The host object budget is 2048 bytes Flash and zero static RAM; caller storage
and stack usage are outside the RAM metric.
