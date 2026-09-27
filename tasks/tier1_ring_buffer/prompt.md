# Task: Lock-free SPSC Ring Buffer

You are an expert embedded software engineer. Implement a Single-Producer Single-Consumer (SPSC) circular byte ring buffer in C99.

## Requirements
1. Implement all functions declared in `ring_buffer.h`:
   - `void ring_buffer_init(ring_buffer_t* rb, uint8_t* buffer, size_t capacity);`
   - `bool ring_buffer_push(ring_buffer_t* rb, uint8_t byte);`
   - `bool ring_buffer_pop(ring_buffer_t* rb, uint8_t* byte);`
   - `bool ring_buffer_is_empty(const ring_buffer_t* rb);`
   - `bool ring_buffer_is_full(const ring_buffer_t* rb);`
   - `size_t ring_buffer_count(const ring_buffer_t* rb);`
2. **Safety & Robustness**:
   - Return `false` gracefully if any required pointer argument is `NULL`.
   - Never overflow or corrupt the underlying storage buffer.
   - Do NOT use dynamic memory allocation (`malloc`, `free`).
   - Follow MISRA-C guidelines: use fixed-width integers (`stdint.h`), avoid undefined behavior.
3. Write clean, portable C99 code in `src/ring_buffer.c`.
