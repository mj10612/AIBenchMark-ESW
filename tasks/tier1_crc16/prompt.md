# Task: CRC-16/CCITT-FALSE Checksum Engine

You are an embedded software engineer. Implement the CRC-16/CCITT-FALSE algorithm in C99.

## Specifications
- **Polynomial**: `0x1021` ($x^{16} + x^{12} + x^5 + 1$)
- **Initial Value**: `0xFFFF`
- **Input Reflected**: No (MSB first)
- **Output Reflected**: No (MSB first)
- **XOR Output**: `0x0000`
- **Known Test Vector**: ASCII string `"123456789"` (9 bytes: `0x31, 0x32, ..., 0x39`) MUST produce `0x29B1`.

## Functions to Implement (in `src/crc16.c`):
1. `uint16_t crc16_update(uint16_t current_crc, uint8_t byte);`
   - Updates the 16-bit CRC with one incoming byte.
2. `uint16_t crc16_ccitt(const uint8_t* data, size_t length);`
   - Computes the full CRC-16 over `data` of given `length` starting with `0xFFFF`.
   - Returns `0` if `data == NULL` and `length > 0`. If `length == 0`, returns `0xFFFF`.

Follow MISRA-C best practices (explicit integer types, no undefined bit shifts).
