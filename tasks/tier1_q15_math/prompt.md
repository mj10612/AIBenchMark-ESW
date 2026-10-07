<!-- AIBENCHMARK_ESW_CANARY_V1_tier1_q15_math -->
# Saturating Q1.15 Arithmetic

Implement the three functions declared in `q15_math.h` using portable C99.
Each `int16_t` is a raw signed Q1.15 value: divide by 32768 to obtain its
real value. The representable range is -1 through 1 - 2^-15.

- `q15_add_sat(a, b)`: add the raw integers exactly, then clamp to
  [-32768, 32767].
- `q15_sub_sat(a, b)`: subtract the raw integers exactly, then clamp to
  [-32768, 32767].
- `q15_mul_sat(a, b)`: compute the exact raw product, divide by 32768
  **truncating toward zero**, then clamp to [-32768, 32767]. Do not round to
  nearest or toward negative infinity. For example, `q15_mul_sat(-3, 16384)`
  is -1, and `q15_mul_sat(-1, 1)` is 0. Multiplying -32768 by -32768 must
  return 32767, since positive 1 is not representable.

All pairs of input values are valid. Avoid signed overflow and narrowing
before saturation. The code must also be correct on targets with a 16-bit
`int`; widen operands before arithmetic where needed. Do not depend on
right-shifting negative signed integers. Use fixed-width integer arithmetic,
no floating point, dynamic allocation, or mutable global/static storage.
Do not change the public header or include a `main` function.

The host implementation object has a 1024-byte Flash budget and a zero-byte
static RAM budget. Stack usage is not measured by this benchmark.
